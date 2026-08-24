# 取数来源与逻辑

> **原始数据不进仓库。** 回测拉了约 54 MB（美股与加密日线 · 分钟线 · 内部人申报 ·
> 议员交易 · 分析师目标价 · 资金费率 · 未平仓量 · 社交语料），其中社交语料是
> 第三方平台的帖子全文 —— 既没有必要随交付再分发，也让 `git clone` 变重。
>
> **结论都在 [`results-*.md`](.) 与 [`signal-registry.md`](signal-registry.md) 里**，
> 数据只在有人要重算时才需要。这份文档是重算的入口。

---

## ⚠️ 先纠正一件事：取数不是免费的

这个仓库里关于计费的记载**错过六次**，每一次都写着「取数 0 credits，纯 HTTP，
只有 LLM 调用消耗 credits」。那句话是错的，而且代价具体：一次社交语料取数
**花掉 4,052 credits**，比同日整个 LLM 部分贵三倍。

根因不是算错，是**核账模型里根本没有那一维**：

```
❌  成本 = Σ(端点调用 × 单价)
✅  成本 = Σ(端点调用 × 单价) + Σ(运行时长 × 2/分钟) + Σ(LLM rollup + 检索子条)
```

`playbook` 这一项按脚本**运行时长**计费，与拉什么、调不调模型都无关 ——
拿着已知的几类去账单里找它们，永远撞不见没见过的那一类。

**核账前先把账单 `source` 的取值枚举一遍**，再决定每一类怎么算：

```bash
alva credits items --today | python3 -c "
import sys,json,collections
d=json.load(sys.stdin); by=collections.Counter()
for e in d['items']['edges']:
    ex=json.loads(e['node'].get('extras') or '{}')
    for k,v in (ex.get('by_endpoint') or {}).items(): by[k]+=v.get('calls',0)
    if e['node'].get('source')=='ask': by['[ask]']+=1
[print(f'{k:52s} {v}') for k,v in by.most_common()]"
```

⚠️ **计费有分钟级延迟。跑完立刻查余额会看到「没变」，那是假的** ——
本项目两次因此记错。判断成本必须等几分钟后查 `credits items --today`。

⚠️ **`alva run` 返回的 `credits_used` 字段恒为 0，不可信。**

---

## 逐来源

宿主：`https://data-tools.prd.arrays.org`，脚本在 [`scripts/`](scripts/)，
统一用 `alva run --local-file <脚本> --args '{...}'` 跑在 Alva 的 V8 runtime 上
（可用 `require("net/http")` + `require("secret-manager")` 取 `ARRAYS_JWT`；无 top-level await）。

| 来源 | 端点 | 计费 | 字段 | 脚本 |
|---|---|---|---|---|
| 美股日线 | `/api/v1/stocks/kline?interval=1d` | ❌ 免费 | `time_period_start` `price_close` `volume_traded` | [`fetch.js`](scripts/fetch.js) |
| 美股 OHLCV | 同上 | ❌ 免费 | 加 `price_open/high/low` | [`fetch2.js`](scripts/fetch2.js) |
| 美股分钟线 | `/api/v1/stocks/kline?interval=15min` | ❌ 免费 | 同上 | [`pv-intraday/`](scripts/pv-intraday/) |
| 加密日线 | `/api/v1/crypto/binance/spot/usdt/kline` | ❌ 免费 | `time_open` `price_close` `volume` | [`fetch.js`](scripts/fetch.js) |
| 资金费率 | `/api/v1/crypto/funding-rate` | ❌ 免费 | `time` `funding_rate` | [`dr-expanded/`](scripts/dr-expanded/) |
| 财报日历 | `/api/v1/stocks/earnings-calendar` | ❌ 免费 | `date` `time`(bmo/amc) | [`ev-expanded/`](scripts/ev-expanded/) |
| 宏观 | `/api/v1/macro/economic-indicators` | ❌ 免费 | 34 个指标枚举 | [`ma-expanded/`](scripts/ma-expanded/) |
| 议员交易 | `/api/v1/stocks/congress/recent-trades` | ❌ 免费 | — | [`gov_fetch.js`](scripts/gov_fetch.js) |
| **内部人** | `/api/v1/stocks/insider/transactions` | ✅ **1 credit/次** | `transaction_date` `filing_date` `transaction_code` … | [`ev_fetch.js`](scripts/ev_fetch.js) |
| **市场新闻** | `/api/v1/stocks/market-news` | ✅ **1 credit/次** | `title` `url` `tickers[].relevance_score` | 运行时 |
| **分析师目标价** | `/stocks/company/price-target-news` | ✅ **1 credit/次** | — | universe |
| **代币解锁** | `/crypto/unlock-events` | ✅ **1 credit/次** | — | — |
| **社交语料** | `arrays_x_feed` | ✅ **约 21 credits/次** | `published_at` `full_text` `source.full_text` | [`po_fetch.js`](scripts/po_fetch.js) |
| **LLM（带检索）** | `ask` | ✅ **一次 110–330** | rollup 79–299 + 4–5 条检索子条 | 运行时归因 |
| **脚本运行本身** | `playbook` | ✅ **2 credits/分钟** | 与拉什么无关 | 所有 cronjob |

⚠️ `POST /social-feeds/x/handles`（发现新账号）按 premium unit 计费，**不要调用**。
只读的 `by-handle` / `entities/handles` 可枚举已追踪账号。

⚠️ **MCP 工具调用计费为 `ask`。** 曾有一份验证报告写「`get_company_themes` 免费」，
依据是「探测后等 9 分钟读余额没变」—— 该结论已撤回。

---

## 覆盖范围

```
时间       美股 2018-01-02 → 2026-08-18（满仓 2,168 根，92 只里 76 只取满）
           加密 2018-01-01 → 2026-08-18（最长 3,152 根）
           资金费率 2020-03-30 起 · 未平仓量 2020-02-27 起（早于此无数据）
样本池     美股 92 只（11 个 GICS 部门每部门 ≥4）+ 加密 25 个
           选取规则先写定再执行，含幸存者偏差记录 → universe/universe-rules.md
内部人     92 只 85,051 笔 Form 4
分析师     目标价新闻 4,924 条
社交       官方政策账号 2025-01 起 9,556 条
```

**深度上限**：美股盘中单次查询上限 366 天；官方异动 feed 只有 41.6 天（不用，自己重算）。

---

## 重新拉取

```bash
alva run --local-file backtest/scripts/fetch2.js \
  --args '{"symbol":"NVDA","kind":"stock"}' --timeout-ms 300000
```

样本池那一批走 [`scripts/universe/`](scripts/universe/)，逐族实验各自的取数在对应目录里。

⚠️ **分段取，别指望 `limit` 能兜住。** `limit=3000` 是**行数**上限：加密一天 96 根
十五分钟 bar，一次请求最多装 31.25 天；而美股一天约 26 根 RTH，同一个请求装得下 150 天。
**同一段代码在两个资产类别上取到的历史长度差五倍，而且不报错** ——
这个坑在交付的 skill 里也踩过一次（见 [`../eval/badcases.md`](../eval/badcases.md) BC35）。

---

## 数据陷阱（都是实测踩过的）

| 陷阱 | 说明 |
|---|---|
| **返回按时间倒序** | 脚本里 `reverse()`，落盘的 CSV 是正序 |
| **字段名不统一** | 股票 `time_period_start`/`volume_traded`，加密 `time_open`/`volume` |
| **转推的 `full_text` 恒为空** | 正文在 `source.full_text`。`POTUS` 的 1,816 条里 1,797 条是转推 —— 只读 `full_text` 该账号等于零语料 |
| **`filing_date` 有坏值** | SOFI 双峰：61% 为 0 日 + P90 347 日。保守按不可信处理 |
| **`congress` 的 `offset` 无效** | 一直返回同一页，20,000 行里 19,081 重复。**正确做法是按时间分窗** |
| **议员数据含重复行** | 各标的 7–11% 完全重复。按整行去重是保守选择，可能误删真实的多笔申报 |
| **`limit` 有上限** | `congress/recent-trades` 上限 1000，超过报 400 |
| **探测必须带全参数** | 缺 `start_time`/`end_time` 返回 400 VALIDATION_ERROR，曾被误判为服务故障 |
| **`start_time=0` 报 400** | 端点不收纪元零，用一个真实的早期时刻 |
| **emoji 代理对** | 社交语料要剥 `\uD800-\uDFFF`，否则 UTF-8 编码报错 |
| **前 60 日无基线** | 每只标的开头 60 日算不出 z，其中只有 5 只是真新上市 |
| **logo 不是每只都有** | `arrays-public-assets/logos/<T>.svg` 对美股个股有、**ETF 全部 404**、加密要 CoinMarketCap 数字 id。照 pattern 硬填会给每行 ETF 配一张碎图 |

---

## 一条元规则

**「我算出来了」不等于「我知道了」。** 一个数要成为结论，先问：换个口径还成立吗 ·
有没有不用统计就能发现的矛盾 · n 够不够 · 有没有人复核过。

这份仓库推翻过自己十几次，根因清单在 [`../notes/`](../notes/)。
