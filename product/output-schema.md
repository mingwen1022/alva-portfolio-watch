# Playbook 数据契约

> Skill 跑完之后落在 Alva FS 上的文件，以及每个文件的字段。
> **前端只读这些文件，不做计算** —— 所有派生量在管线里算完。
> 信号定义见 [`signal-spec.md`](signal-spec.md)，本文只定数据形状。

---

<!-- toc:start -->
**目录**（自动生成，改标题后重跑 `backtest/scripts/add_toc.py`）

- [一、文件布局](#一文件布局)
  - [`state.json` · 告警生命周期的唯一存放处](#statejson-告警生命周期的唯一存放处)
- [二、`data/signals.json` · 信号清单](#二datasignalsjson-信号清单)
- [三、`data/findings.json` · 今日 findings](#三datafindingsjson-今日-findings)
  - [`attribution` 是这七个文件里唯一不可复算的字段](#attribution-是这七个文件里唯一不可复算的字段)
  - [`scan` 是全部持仓的当轮读数](#scan-是全部持仓的当轮读数)
  - [三个字段值得单独说](#三个字段值得单独说)
  - [界面按 `(symbol, episodeId)` 分组，一组一张卡](#界面按-symbol-episodeid-分组一组一张卡)
  - [优先级打平时谁做主卡](#优先级打平时谁做主卡)
  - [按信号类型的差异](#按信号类型的差异)
- [四、`data/portfolio.json`](#四dataportfoliojson)
- [五、`data/series.json`](#五dataseriesjson)
- [六、`data/baselines.json` · 逐标的基线](#六databaselinesjson-逐标的基线)
  - [`m23` 是运行时唯一能发现「方法论不适用」的守卫](#m23-是运行时唯一能发现方法论不适用的守卫)
  - [`distributionBar.slots[].top` 让运行期算得出名次](#distributionbarslotstop-让运行期算得出名次)
  - [`slotBaselines` 是盘中的逐槽位基线](#slotbaselines-是盘中的逐槽位基线)
  - [`producedSignals` 说这一轮真的产出了哪几条信号](#producedsignals-说这一轮真的产出了哪几条信号)
  - [`signalGrades` 是逐标的的投递上限，与阈值无关](#signalgrades-是逐标的的投递上限与阈值无关)
- [六·二、`data/market.json` · Tab 3](#六二datamarketjson-tab-3)
- [六·三、`data/symbols/<SYMBOL>.json` · Tab 2 逐标的页](#六三datasymbolssymboljson-tab-2-逐标的页)
  - [`intraday` 是给盘中告警卡画图用的，不是给盘中基线用的](#intraday-是给盘中告警卡画图用的不是给盘中基线用的)
- [七、`config/alerts.json` · 唯一可写文件](#七configalertsjson-唯一可写文件)
  - [三层权限](#三层权限)
- [八、`meta.json`](#八metajson)
- [九、eval 断言挂在哪](#九eval-断言挂在哪)
- [十、更新节奏](#十更新节奏)
  - [`data/news.json` · Tab 1 底部的今日相关新闻](#datanewsjson-tab-1-底部的今日相关新闻)
  - [新闻取数按需，不轮询](#新闻取数按需不轮询)
  - [哪些端点免费](#哪些端点免费)
- [十一、初始化与增量](#十一初始化与增量)
  - [初始化做什么](#初始化做什么)
  - [阈值只在初始化时定，增量不重解](#阈值只在初始化时定增量不重解)
  - [σ 滚动，θ 不动](#σ-滚动θ-不动)
  - [增量做什么](#增量做什么)
  - [三个边界](#三个边界)
  - [净值序列的起点是接入日，不是开仓日](#净值序列的起点是接入日不是开仓日)

<!-- toc:end -->

## 一、文件布局

```
~/playbooks/<name>/
  config/
    alerts.json          用户配置 · 唯一可写文件
  data/
    signals.json         信号清单 · 由 signal-spec 生成
    findings.json        今日 findings · 每次 cron 覆盖
    portfolio.json       持仓 · KPI · 分配
    series.json          净值序列 · 当日盈亏 · 触发日
    news.json            今日相关新闻
    baselines.json       逐标的基线
    market.json          Tab 3 市场数据 · 指数 · 国债 · 商品 · 加密情绪 · 本周财报
    symbols/<SYM>.json   Tab 2 逐标的页 · K 线 · 内部人 · 财报 · 资金费率 · 52 周区间
    state.json           ⭐ 跨轮状态 · 去重 · 冷却 · 状态型信号的开关位
    meta.json            运行时间 · 数据新鲜度 · 版本
```

**只有 `config/alerts.json` 是用户可写的**，其余每次运行覆盖。

⚠️ **`scan[].asOf` 是这一行的读数来自哪一根 bar，不是这一轮的时刻。**

混合账本在周末有**两个**「最近收盘」：美股停在周五，加密每天都有。
一个 `asOf` 说不了这两件事 —— 把周五的 −0.98% 摆在「周六 20:00」的时间戳下面，
读者会以为那是周六发生的。实测第一次真跑就撞上：12 行来自 08-21、3 行来自 08-22。

跨日时 `meta.gaps` 追加 `holdings_span_multiple_sessions:<日期,日期>`，
让页面能说出来，而不是替它圆过去。

⚠️ **`meta.json` 在 `data/` 里，不在 playbook 根目录。**
契约原先写在根目录，而页面 fetch 的是 `data/meta.json`、管线也写在那儿 ——
两边从来没对过，因为这一条在本地静态服务下不会报错。
统一到 `data/`：页面要读的东西全在一个目录下，`config/` 是唯一的例外（它是可写的那个）。

⚠️ **`state.json` 是唯一「读-改-写」的文件，其余七个都是整体覆盖。**
它必须先读回上一轮的内容再合并，直接覆盖会丢掉去重键和冷却时点。

### `state.json` · 告警生命周期的唯一存放处

```json
{
  "asOf": "2026-08-21T16:00:00-04:00",
  "keys": {
    "MSTR:US1": { "on": true,  "since": "2026-08-19T14:22:00-04:00",
                  "lastPush": "2026-08-19T14:22:00-04:00", "clearedAt": null },
    "SOUN:US3": { "on": false, "since": "2026-08-14T16:00:00-04:00",
                  "lastPush": "2026-08-14T16:00:00-04:00",
                  "clearedAt": "2026-08-21T16:00:00-04:00" },
    "NVDA:EV1": { "on": false, "since": null, "lastPush": "2026-07-08T16:00:00-04:00",
                  "clearedAt": null }
  }
}
```

```
键        "<symbol>:<signalId>"
on        这一轮该条件是否成立。仅状态型有意义，事件型恒为 false
since     本次连续成立的起点。反转后清空
lastPush  上次真的推过手机的时刻 —— 去重与冷却窗口都读它
clearedAt 反转发生的时刻。写上之后再保留一个周期，然后整条删掉
armedFor  这一条武装时的用户线值。⚠️ 值一变即重置整条 ——
          用户改了线就是一条新规则，旧的「已经推过了」不该压住新线的第一次触发
```

⚠️ **`lastPush` 记的是「推过手机」不是「算出来过」。** 被投递上限压到 L2 的信号
每天都算得出来，但从没推过 —— 拿它当去重依据会让升级到 L1 后的第一次推送被吞掉。

⚠️ **裁剪规则**：`clearedAt` 非空且已过一个周期 → 删除该键。
`lastPush` 早于最长冷却窗（EV 族 45 日历日）→ 删除。
**没有裁剪规则这个文件会单调增长。**

---

## 二、`data/signals.json` · 信号清单

**由 `signal-spec.md` 生成，不手写。** 前端所有类型名从这里取，findings 里只带 `signalId`。
产出脚本 `pipeline/build_signals.py`。

⚠️ **`assetClass` 有三个取值：`us_equity` · `crypto` · `other`。**
`other` 是「未验证类别」—— ETF、商品 ETF、债券 ETF 等在美国交易所上市、
kline 端点能返回日线的标的。它的阈值走池级反解（`thresholdSource: "fallback_solved"`）。

```
适用于 other 的     PV1 · PV3 · PV4 · US1 · US2 · US3
不适用             PV5   盘中阈值没有兜底反解规则
                  EV1 · EV4 · EV6   ETF 没有内部人、财报、公司新闻
                  DR1   仅加密
```

⚠️ **这个文件原来是手写的，没有任何脚本产出它** —— 于是往账本里加第三个资产类别时，
十一条信号的 `assetClass` 一条都没跟着动。后果不是报错：ETF 会拿到反解出的 θv、
算出 findings，然后每一条都因为「本条信号不适用于该资产类别」而在界面上不显示。

⚠️ **兜底阈值封的是证据标记，不是投递层级。**
界面上该标的带 `UNVALIDATED`，而它的 `delivery` 仍由三处上限决定 ——
其中 `symbol_grade` 是**在这只标的自己的历史上、用它自己那条反解出的 θv** 跑出来的，
那比类别级验证更直接。两件事不要合并。

```json
{
  "generatedFrom": "signal-spec.md@427f4f8",
  "signals": {
    "PV1": {
      "name":       { "zh": "价量异动 · 日线", "en": "Price-volume move · daily" },
      "type":       "alert",
      "assetClass": ["us_equity", "crypto"],
      "granularity":"daily",
      "evidence":   "green",
      "severity":   "critical",
      "maxDelivery":"L1",
      "pushable":   true
    }
  }
}
```

<sub>`type`：`alert` 进告警流 · `display` 只在界面 · `record` 记录 · `calendar` 日历 · `attribution` 归因源</sub>
<sub>`evidence`：`green` 已验证 · `amber` 已测未达判据 · `red` 已证伪 · `blue` 引用未自测 · `yellow` 待验证 · `white` 无法验证 · `na` 不适用</sub>

⚠️ **这一个文件同时服务三处**：界面类型名 · 界面 ID 白名单自查 · eval 的信号白名单断言。
名字只写一次，三边不会漂移。**前端不得自行编写任何类型名。**

---

## 三、`data/findings.json` · 今日 findings

```json
{
  "asOf": "2026-08-21T16:05:00-04:00",
  "findings": [{
    "id":          "2026-08-21:NVDA:PV1",
    "symbol":      "NVDA",
    "assetClass":  "us_equity",
    "signalId":    "PV1",
    "unit":        "session",
    "severity":    "critical",

    "triggeredAt": "2026-08-21T16:05:00-04:00",
    "knownAt":     "2026-08-21T16:05:00-04:00",
    "episodeId":   "2026-08-21:NVDA",
    "novelty":     1.0,
    "priority":    0.723,

    "measured":    { "z": -4.12, "rvol": 3.4, "move": -0.062 },

    "trigger": {
      "unit":            "session",
      "moveAt":          "2026-08-21T16:05:00-04:00",
      "thresholdSource": "validated",
      "barSlot":         null,
      "barClose":        null
      // bar 档： "barSlot": "09:00", "barClose": 0.08344
    },

    "delivery": { "level": "L1", "cappedBy": null },
    // 被压时： { "level": "L2", "cappedBy": "symbol_grade" }
    //          其余取值 "signal_evidence" · "degraded"


    "context": {
      "sizeRank":  { "rank": 7, "of": 502, "unit": "sessions" },
                   // bar 档： { "rank": 1, "of": 135, "unit": "bars" }
                   // 时刻不在这里重复存，取 trigger.barSlot
      "benchmark": { "symbol": "SPY", "benchmarkMove": -0.003,
                     "symbolMove": -0.062, "applicable": true },
                   // 不适用： { "symbol": null, "benchmarkMove": null,
                   //           "symbolMove": null, "applicable": false }
      "pnl":       { "today": -968, "shares": 124, "lifetime": 2180 },

      "attribution": {
        "notRun":  null,
        "timing":  "before",
        "summary": "两家媒体报道下一代加速器机架出货排期放缓，发生在这次移动前 25 分钟",
        "sources": [{ "title": "…", "url": "https://…", "publishedAt": "2026-08-21T13:40:00-04:00",
                       "source": "reuters.com", "summary": "…", "origin": "chain" }],
                   // origin:"model" 的条目 publishedAt · source · summary 均为 null ——
                   // 模型自搜只报得出链接，发布时刻无从核实
        "model":   "gpt-5.6-luna",
        "generatedAt": "2026-08-21T16:05:31-04:00"
      }
    }
  }],

  "scan": [
    { "symbol": "NVDA", "state": "quiet", "unit": "session", "asOf": "2026-08-21",
      "price":  { "today": -0.0098, "line": 0.03837, "usual": 0.02558 },
      "volume": { "rvol": 0.689, "line": 2.0, "partial": false },
      "bar":    { "z": 1.33, "rvol": 0.6, "slot": "15:00", "state": "quiet",
                  "line": 0.01329, "volumeLine": 2.0, "bars": 25 } },
    { "symbol": "NEWCO",
      "price": null, "volume": null,
      "state": "insufficient_baseline", "baselineDays": 41 }
  ]
}
```

⚠️ **`barClose` 是这根 bar 自己的收盘价，session 档为 null。**

盘中卡要印价格，就必须有这个字段 —— **不能拿当日收盘顶替**：
DOGE 09:00 那根收在 $0.0834，而当天收盘是 $0.0916，差 9.6%，方向还相反。
此前契约没有这个字段，页面于是只能不印，结果同一列表里日线卡带价、盘中卡不带，
读起来像两种不同的对象。

⚠️ **`attribution.notRun` 与 `timing` 说的是两件事，不能合并。**

```
timing: "none"      找过了，今天没有相关报道
notRun: "daily_cap" 没去找 —— 今天的归因配额用完了
notRun: null        真的找过了

summary: null       找过了（含模型自检索），移动之前没有任何报道
summary: "…"        找到了，这是根据它们写的
```

⚠️ **有解释就必须有来源：`summary` 非空 ⟹ `sources` 非空。**
读者打不开任何东西的解释不是解释。实测两次：材料为空时模型分别写出
「广泛的加密上涨与逼空」「X 上的贴文提到杠杆引发的波动」，`sources` 都是空的 ——
读起来像解释，却没有任何可核实的东西支撑，比一句「没找到」更坏。
这条同时写在提示词规则 8 和管线的硬门里：只写提示词，模型会去填那个空；
只写代码，模型不知道自己为什么被丢掉。

⚠️ **`summary: null` 是正常结局，不是故障。** 取材只收**早于**移动的报道，
一条都没有时模型按规则 8 返回 null，页面显示「未找到发布于这次移动之前的报道」。
晚于移动的条目照常进 `sources` 供阅读，但不进模型输入 ——
否则模型只能对它表态，而唯一能说的话是否定句。

⚠️ **「问过没有」的判据是 `generatedAt`，不是 `model`。**
`model` 按本契约恒为 null（ask() 不返回模型名），拿它做判据的分支会整条塌掉，
把「问过了没找到」并进「压根没问」——两者对读者是两句不同的话。

把「没去找」塞进 `timing: "none"`，页面就会说「今天没找到相关报道」——
那是一句假话，而它完全合法、不会报错。

⚠️ **配额按「卡」计，不按信号计。** 共现合并之后一张卡调一次，
三条 PV5 合并成一张卡算一次。按 **UTC 日**重置 —— 与 cron 同一个时区，
否则会出现「配额重置了但当天的 cron 还没跑」的错位。

⚠️ **先到先得。** 告警是一整天陆续来的，等收盘再挑最重要的十条会让推送迟到一天。
代价要说清楚：波动大的日子里，早盘那批会吃掉配额，晚来的只能显示「已到上限」。
上限在 `config/alerts.json` 的 `attribution.dailyCap`，用户可调 —— 界面同时要说
调高就是多花 credits。

⚠️ **`delivery` 是投递的结果，不是又一次判定。**

```
level     这条 finding 实际到达的投递层
cappedBy  被谁压下来的。null = 没被压
            "symbol_grade"     baselines[sym].signalGrades[sig].maxDelivery
            "signal_evidence"  signals.json[sig].maxDelivery（证据等级）
            "degraded"         baselines[sym].degraded → 上限 **L2**
```

⚠️ **`degraded` 的上限是 L2，且不适用于 US1–3。**

```
L2 不是 L3    spec 说的是「不推手机」。L3 是持仓页 —— 压到 L3 等于连告警流都不进，
              比「不推手机」多砍一层，而没有任何一条规则要求那样
US 豁免        signal-spec §US「US 从不降级」。degraded 说的是我们那套阈值背后的历史
              不够硬，而用户线一个字都没借它：US1/US2 是用户填的价位，
              US3 量的是这只票自己的高点
```

⚠️ 这两条曾经在管线（`'L3'`，且对 US 照压）与页面自检（`'L2'`，US 也照压）里
各写一份且互相矛盾 —— 实测把三条用户亲手设的止损/止盈线拦在了手机之外，
**理由是「这只标的波动大」，而波动大正是用户设它的原因。**

**它必须落盘，不能让界面自己 join 三处再取 min。** 界面要说的是
「两条线都过了，但手机没响，因为这只标的自己的历史不支持推送」——
那句话依赖的是**结果加原因**，而不是三个上限值。

⚠️ **`cappedBy` 是「过线了但手机没响」那段说明的唯一数据来源。**
没有它，界面只能说「没推」，说不出为什么。

⚠️ **`findings[]` 的键就是上面这些，多一个少一个都要先改契约。**

已经删掉的几个，理由记在这里，免得下次又加回来：

```
direction          move 的符号就是方向，两处存必然漂
move（顶层）       它是一次读数，归在 measured 里。顶层再放一份是第二个副本
positionWeight     排序的中间量，engine 内部用，不落盘。页面要权重去 portfolio.json 取
trigger.thresholds 阈值的唯一存放处是 baselines[sym].thresholds 与 triggerLine
context.news       来源与档位现在全在 attribution.sources / timing 里
```

⚠️ **`assetClass` 必须落在 finding 上。** 卡片要按资产类别决定显示哪几块，
让它去 `portfolio.json` 里 join 一次，等于同一个事实两处取。

⚠️ **`severity` 决定卡片的颜色与排序里的第一项**，不是可选。

### `attribution` 是这七个文件里唯一不可复算的字段

其余每个数字都能从原始行情重新算出来。这一个不能 —— 它是 `ask()` 的输出，
同一条告警跑两次措辞会不同。所以它**必须带署名**：

```
model         平台可用清单内的串。传清单外的值不报错、静默回落到 Sonnet 5，
              所以写一个平台不认的名字等于没署名
generatedAt   生成时刻，与 triggeredAt 不同
```

**两条轴，都不由模型产出：**

```
轴 A · 材料      严链 + 宽链 + 模型自搜，三者都进 sources[]
                有材料 → 界面列出（标题 · 摘要 · 来源 · 时刻 · 链接）
                无材料 → 不显示材料块

轴 B · timing    由 sources[].publishedAt 与移动时刻比出来，**只读 origin:"chain" 的那些**
                before   有 chain 来源，且存在 publishedAt ≤ moveAt 的
                after    有 chain 来源，全都晚于
                untimed  没有 chain 来源，但模型自搜到了 —— 找到了报道，时点未核实
                none     一条来源都没有
```

⚠️ **模型只写 `explanation` 与它自搜到的来源。** 徽章全部由代码算 ——
「有没有报道」「在移动之前还是之后」是事实主张，不接受在两次运行之间跳变。

⚠️ **`after` 不是失败档,渲染上不得弱于 `before`。** 要区别的是它与 `none`：
一个有内容，一个没有。

⚠️ **取不出可点开链接的来源整条不渲染。** 「读者能不能点开」是关于这一页收到了什么。

⚠️ **`explanation` 是两三句不是一句。** 一句话的格式逼模型断言；
一小段才有地方说「时点对得上但指向不对」。调用规格见 [data-pipeline §九](data-pipeline.md)。

⚠️ **EV4 的 finding 没有这个字段。** 日历条目没有「这次移动」可解释。

⚠️ **它不影响任何投递决定。** 富化层在排序之后，`ask()` 失败时该字段缺省为
`{state: "none"}`，告警照发。链路见 [data-pipeline §零](data-pipeline.md)。

### `scan` 是全部持仓的当轮读数

`findings` 只装触发了的，`scan` 装**每一只**，触发与否都在。

零告警那天，Tab 1 的告警区展示的就是这个数组 —— 「今天没有异动」下面那张表
（见 [content-spec §⑦·五](content-spec.md)）逐行对应 `scan[i]`。
有告警的日子它让位给告警卡，但**数组照常产出**：
它是「引擎跑过了每一只」的唯一证据，也是 eval 判「有没有漏扫」的依据。

```
price.move      当日涨跌幅。与 line 同单位，用户能直接比
price.z         当日 M2 稳健 z。引擎判的是它，界面显示的是 move
price.line      = θz × σ_rob，取自 baselines[sym].triggerLine.price
volume.rvol     当日 M3 相对量
volume.line     = θv，取自 baselines[sym].triggerLine.volume
state           quiet / triggered / insufficient_baseline
```

⚠️ **`volume.rvol` 在盘中是残缺的。** 分子是当日累计成交量，分母是过去 90 日的
**全日**中位数 —— 14:30 跑出来的 1.1× 被系统性低估。

**处理方式是标注，不是折算。** 折算需要一条盘中成交量曲线（U 型分布），
我们没验过，凭空造一条等于制造一个未验证的量。所以：

```
盘中    partial = true   · asOfSession = "14:30"   界面写「1.1× 截至 14:30」
收盘后  partial = false  · asOfSession = null      界面写「1.1×」
```

⚠️ **`price.z` 与 `price.move` 都给，因为两者用途不同。**
引擎判的是 `z`（稳健 z 才有跨标的可比性），但用户读的是 `move`（涨跌幅）。
界面只显示 `move`，`z` 留给方法页和 eval 复算。

⚠️ **`state = insufficient_baseline` 时 `price` 与 `volume` 一律为 `null`。**
基线不足 60 日算不出可信的 σ 和 90 日量中位（PV4 覆盖不足），
给一个数比不给更坏 —— 用户没法从数字本身看出它不可信。

### 三个字段值得单独说

**`knownAt` ≠ `triggeredAt`。** EV 族有申报滞后，事件发生日不等于可知日 ——
内部人申报中位 2 日、P90 4–13 日、最大 464 日。**排序和去重一律用 `knownAt`**，
否则会把「今天才知道的旧事」排到「今天发生的事」前面。

**`unit` 决定这条 finding 的量纲，值本身不存在这里。**

```
session   PV1 · 日线。measured.z 是日 σ_rob 单位，measured.rvol 是全日量比
bar       PV5 · 15 分钟。measured.z 是 bar σ 单位，measured.rvol 是 bar 量比
```

⚠️ **`measured.rvol` 也随 `unit` 变。** PV5 卡上的量比是**那根 bar 的**，
不是当日累计的 —— 用当日 RVOL 去判 PV5 卡该显示什么，会得到
「量能只有 0.9 倍、低于 2.0 倍线、被当作低量噪音过滤」，
而它刚刚在 bar 上跑了 2.6 倍。**渲染一律读 finding 自己的 `measured`，不要现算。**

**`thresholdSource` 是证据链的锚点。**

```
validated         该资产类别在样本池上验证过（美股 92 只 · 加密 25 个）
fallback_solved   未验证资产类别，按兜底规则反解得到
user_set          US 族，用户自己设的值
```

⚠️ **界面显示证据等级时必须看这个字段。** 阈值来自兜底反解的标的，
不能显示 `green` —— 那是拿已验证配置的背书去担保一个没测过的配置。

**它存在两处，分工不同**：

```
baselines[sym].thresholds.source    真值所在。逐标的，建基线时写定，之后锁定
findings[].trigger.thresholdSource  渲染副本。卡片据此决定证据等级怎么显示
```

⚠️ **它不进 `config/alerts.json`。** 那个文件是用户可写的，而
`thresholdSource` 是系统判定的结果 —— 让用户能改它等于让用户自己声明
「我这套阈值是验证过的」。同理**它也不进 `signals.json`**：那份按信号 ID
组织，而这是逐标的属性，同一条 PV1 在美股上是 `validated`、在港股上是
`fallback_solved`。

⚠️ **约束的是引擎与告警卡，不是配置面。** 配置面回答「哪些规则开着、我的线在哪」，
它不逐标的列举，所以没有承载这个字段的位置。逐标的的证据降级显示在**持仓表**
和**告警卡**上。

**`context` 的四个键一一对应告警卡的四块**：`sizeRank`→③ · `benchmark`→① ·
`pnl`→④ · `news`→②。收起态是这四项的摘要，展开是详情。
**多一个键或少一个键都说明界面与数据分工没理清。**

### 界面按 `(symbol, episodeId)` 分组，一组一张卡

**findings 保持扁平** —— 每条信号是一条 finding，这是诚实的数据模型。
**分组是渲染层的事**，键是 `(symbol, episodeId)`。

依据 registry §6.4：同 `anomalyEpisodeId` 的延续**更新状态，不重复推送**；
盘中与日线同 episode，PV5 先触发推送、PV1 收盘时**更新同一张卡片而非新推**。
US 族的豁免是「绕过重要性判断」，**但明确参与去重**。

```
NVDA  −6.2%  [价量异动 · 日线] [止损线]      ← 一张卡，两个 pill
```

同一次价格移动导致两条信号，列表里出现两行「NVDA −6.2%」是重复不是信息。

**这条同时决定了告警条数的上界**：合并之后一个标的一天基本只产生一张卡，
所以**告警数被持仓数封顶** —— 「5 只持仓 12 条告警」在结构上不可能出现，
不是概率低。演示溢出态必须配足够多的持仓。

⚠️ **EV4 不参与合并。** 它是日历不是异动，没有 `anomalyEpisodeId`。
「AAPL 明天发财报」和「AAPL 今天价量异动」回答的是不同时态的问题，
合并会让「明天」和「今天」挤在同一张卡上。

⚠️ **卡片的排序取组内最高优先级**，不是各信号分别参与排序 ——
否则同一个标的会在列表里影响两个位置。

### 优先级打平时谁做主卡

`priority = severity × position_weight × novelty` 在同一标的上经常打平 ——
权重相同、都是 Critical、都是首次。按**来源**决断，不按时间：

```
① 你设的线    US1 · US2 · US3
② 我们判的    PV1 · PV5
③ 日历        EV4（不参与合并，此处不适用）
同族之内再比 knownAt，早的做主卡
```

⚠️ **不要用「谁先触发谁做主卡」。** 那会在 PV5 早于 US 线时把止损命中埋进
一张「价量异动」卡里 —— 而 US 是**决策触发器**（用户预先承诺过要在这条线上做什么），
PV 是**注意力触发器**（值得看一眼）。把决策触发器降为副标签，等于让用户
自己去卡片里翻找他唯一预先在乎的那件事。

这跟 registry §6.2 给 US 族的豁免同源：用户自己设的线不该被系统的判断压制 ——
不该被重要性判断压掉，也不该被我们的信号挤到副位。

### 按信号类型的差异

| signalId | 特有字段 |
|---|---|
| PV5 | `trigger.barIndex` · `trigger.isOpeningBar`（开盘那根量能腿几乎不起作用） |
| EV4 | `event.date` · `event.session`（`bmo`/`amc`）· `event.multiple` 2.58 |
| US1–3 | `trigger.userLine`（用户设的值，US1/US2 是价格、US3 是分数）· 无 `context.sizeRank` · 无 `attribution` |
| EV6 | 不是独立 finding，挂在 `context.news.items[]` |
| DR1 | `trigger.measured.fundingRate` · 仅加密 |

⚠️ **`context.benchmark.applicable = false` 用于 BTC** —— BTC 占全加密市值一半以上，
基准与标的重合，界面要显示「基准与本资产重合」而不是一个数。

---

## 四、`data/portfolio.json`

```json
{
  "linked": true,
  "asOf": "2026-08-21T16:00:00-04:00",
  "cash": 3200.00,
  "kpi": {
    "totalValue": 60876.00,
    "totalPnl":   { "abs": 1865, "pctOnCost": 0.0330 },
    "todayPnl":   { "abs": -379, "pct": -0.0062 },
    "fromHigh":   { "pct": -0.0506, "high": 64120, "sessionsAgo": 19 }
  },
  "holdings": [{
    "symbol": "NVDA", "name": "NVIDIA", "assetClass": "us_equity",
    "logo": "https://storage.googleapis.com/arrays-public-assets/logos/NVDA.svg",
    "last": 118.20, "todayPct": -0.062, "fiveDayPct": -0.096,
    "shares": 60, "avgCost": 150.00,
    "value": 14656.80, "weight": 0.241, "lifetimePnl": 2180,
    "vol30d": 0.0255, "fromHighPct": -0.138,
    "spark": [113.2, 114.0, 118.9, ...],
    "notes": ["PV3"]
  }],
  "allocation": {
    "byHolding":    [{ "key": "NVDA", "value": 14656.80, "weight": 0.241 }],
    "byAssetClass": [{ "key": "us_equity", "value": 46108.00, "weight": 0.758 }],
    "byTheme":      [{ "key": "AI", "value": 36424.00, "weight": 0.497,
                       "members": ["AMD", "NVDA", "SOUN"] }]
  },
  "checks": [{ "signalId": "PF2", "value": 0.598, "detail": { "theme": "AI", "holdings": 3 } }]
}
```

⚠️ **`linked = false` 时**：`kpi` 只保留 `fromHigh`，`holdings[].value` / `lifetimePnl` /
`shares` / `avgCost` / `allocation.byHolding[].value` 全部为 `null`，
`weight` 走等权假设并置 `"weightSource": "equal"`。
**`allocation.byAssetClass` 不依赖金额，未连接时仍然完整。**

⚠️ **`byTheme[].members` 必须给。** 没有成员，界面就无法把这一栏按当前账本重算 ——
实测纯加密账本里这一栏列着五只美股，合计 $46.8K 而账本只有 $18.4K。
**界面不该去猜哪只标的属于哪个主题，数据要把它说出来。**

⚠️ **`weight` 的分母是整个账户**（与 `byHolding` 一致）。
界面在过滤账本里按可见总额重标，那是界面的事；文件里始终是账户口径。

⚠️ **三条恒等式必须成立，缺 `cash` 会让它们全部对不上。**

```
Σ holdings[].value + cash        = kpi.totalValue
Σ holdings[].weight + cash/总额   = 1
Σ holdings[].lifetimePnl         = kpi.totalPnl.abs
```

`weight` 的分母是**含现金的账户总额**，所以持仓权重之和小于 1。
**`cash` 缺省时页面无法显示它，读者看到的总额跟下面的行对不上，而且看不出差额是什么。**
没有现金就写 `0`，不要省略这个键。

⚠️ **`shares` 与 `avgCost` 是输入,`value` 与 `lifetimePnl` 是它们算出来的结果。**
持仓表里给结果不给输入，读者无法核对 —— 成本价是券商持仓表的标准列。

⚠️ **`fromHighPct` 不进持仓表。** 它结构上恒 ≤ 0，在一张要横向比较的表里没有分辨力；
它的位置在逐标的页的「价格与幅度」，那里有区间轴配合。
**只有设了 US3 回撤线的标的**才在告警依据那组显示「距高点 / 你的线」，
与另外两条腿并列；没设线的标的该格缺省。

⚠️ **`logo` 覆盖不全** —— 实测美股个股有，加密与 ETF 无。取不到时该字段为 `null`，
界面走首字母色块，**失败必须静默，不能出现裂图**。

---

## 五、`data/series.json`

```json
{
  "unit": "USD",
  "points": [{ "d": "2026-08-21", "value": 60876.00, "dayPnl": -379, "cumReturn": 0.0330 }],
  "benchmark": { "symbol": "SPY", "points": [{ "d": "2026-08-21", "cumReturn": 0.0912 }],
                 "coverage": "us_equity_only" },
  "high": { "d": "2026-08-02", "value": 64120 }
}
```

⚠️ **`benchmark` 两支必须同一个形状。** 适用与不适用只差 `applicable` 与三个值是不是 null，
**不要给适用那支另起一套键名** —— 一个键两种形状，下一个读它的人会挑错一支。

⚠️ **`move` 这个名字不够，因为有两个 move。** 用 `benchmarkMove` 与 `symbolMove`，
读的人不用去猜哪个是谁的。

⚠️ **`benchmark.coverage`** 说明这条基准覆盖了组合的哪部分。含加密的组合上它只能是
`us_equity_only` —— 加密没有市场基准。界面必须把这一点写出来，不能默默把加密算进去跟 SPY 比。

⚠️ **本文件不带告警日，不要加 `alertDays[]`,也不要把标记画在净值图上** ——
组合净值是多只加权的结果，在它上面标某一只的告警日，读者只能读出一个不存在的因果。
当时的补救（标在轴上不标在线上、加类型过滤器）是在给一个错位的想法打补丁。

**复发次数改挂在告警卡上**（`findings[].recurrence`），因为它是逐标的的事实：

```json
"recurrence": { "countThisMonth": 3, "lastAt": "2026-08-12T16:05:00-04:00" }
```

这样 `novelty` 系数（首次 1.0 · 同 episode 延续 0.5 · 重复 0）在界面上可见，
而读者不必从组合曲线反推是哪只票。

---

## 六、`data/baselines.json` · 逐标的基线

```json
{
  "NVDA": {
    "sigmaRobust": 0.0255, "sigmaAnn": 0.405,
    "baselineDays": 502, "usable": true,
    "m23": { "rho": 0.187, "verdict": "pass", "n": 504 },
    "distribution": {
      "p50": 0.0098, "p95": 0.0412, "p99": 0.0688,
      "histogram": { "from": -0.11, "binWidth": 0.0055, "counts": [1,0,2,3,7,14,...] }
    },
    "thresholds": { "theta_z": 1.5, "theta_v": 2.0, "source": "validated" },
    "signalGrades": {
      "PV1": { "maxDelivery": "L1", "verdict": "usable",
               "multiple": 2.31, "ci": [1.46, 3.12], "blocks": 11, "days": 3292 },
      "PV5": { "maxDelivery": "L2", "verdict": "insufficient_sample",
               "multiple": 1.61, "ci": [1.34, 2.46], "blocks": 3, "days": 3292 }
    },
    "triggerLine": {
      "session": { "price": 0.033, "volume": 2.0 },
      "bar":     { "price": 0.014, "volume": 2.0 }
    },
    "historicalTriggers": { "PV1": 14, "PV5": 31, "windowSessions": 502,
                            "last7": { "PV1": 1, "PV5": 0 } },
    "//": "PV1 与 PV5 一律是【触发天数】，不是根数。见下方说明",
    "degraded": null
  }
}
```

### `m23` 是运行时唯一能发现「方法论不适用」的守卫

稳健标准差里的 1.4826 是**按正态分布校准的常数**。分布形状偏离正态时，
$z^{\mathrm{rob}}$ 的量纲就变了 —— 均匀分布下 $\max\lvert z\rvert = 1.35 < 1.5$，
**PV1 永远不会触发，而且是静默的**：不报错、不告警、看起来一切正常。

$\rho = P(\lvert z^{\mathrm{rob}} \rvert \ge 1.5)$，近 2 年滚动窗。

```
verdict
  pass                 0.02 ≤ ρ ≤ 0.60
  too_tight            ρ < 0.02   分布过窄，固定阈值几乎不可能触发
  too_loose            ρ > 0.40   分布过宽，阈值形同虚设
  insufficient_sample  有效样本 < 250 日 → ρ = null，该标的走 PV4 覆盖标注
```

⚠️ **每次 baseline 重算时更新**，标的的分布形状会随制度和流动性变化。

⚠️ **界面不得自己算 ρ。** 它的定义是「价格腿单独达到 1.5 的日子占比」，
而 PV1 的触发数是两条腿都过的 —— **拿后者当前者实测低 3–5 倍**，
会把正常标的判成「分布过窄，监控已暂停」。

⚠️ **`verdict = insufficient_sample` 时不出 ρ 行，也不出两条界的判定**，覆盖卡只报基线长度。

### `distributionBar.slots[].top` 让运行期算得出名次

每个槽位存**绝对幅度最大的 20 根**，降序。

⚠️ 运行期的盘中 producer 手里只有当天的 bar，没有这个槽位的历史总体 ——
没有它就算不出「135 根里第 1」。存全量是每标的 96 槽 × 135 根，太大；
而排名只在很靠前时才有意义。**掉出前 20 就返回 `sizeRank: null`**，
界面说「不在这个时刻的前 20」，不编一个名次出来。

⚠️ **全部槽位都要落盘，不只今天触发过的那几个。** 哪个槽位会触发，
要到触发那一刻才知道 —— 实测 SOL 在 00:30 触发而落盘的只有 09:00，
卡上「这个幅度算大吗」整块变成「本次运行没有这个时刻的基线」。

### `slotBaselines` 是盘中的逐槽位基线

**盘中的线是「同一时刻」的**：09:45 那根的线来自过去 90 天所有 09:45。
全天 26 根混排会被开盘和收盘那两根结构性地压制。

```json
"slotBaselines": {
  "13:45": { "med": -0.00051668, "sigma": 0.00561752, "vmed": 6960881.75, "n": 90 }
}
```

<sub>槽位键是 **UTC 的 `HH:MM`**，是连接键不是显示值。`med` / `sigma` 用于 z，
`vmed` 是量比的分母，`n` 是这个槽位攒到了多少天（<30 不出读数，该槽位不落盘）。</sub>

⚠️ **它属于初始化，不属于运行期。** 没有它，盘中 producer 每 15 分钟都得重拉
135 天分钟线去重建 —— 那是错的架构：基线算一次，运行期只取当天。

⚠️ **槽位数按资产类别差很多**：美股限 RTH 约 25 个，加密全天 96 个，ETF 为空（不启用 PV5）。

### `barCoverage` 说这把尺子站在多少历史上

```json
"barCoverage": { "askedSamples": 90, "samplesMin": 90, "slots": 96,
                 "askedDays": 95, "chunks": 4, "failedChunks": 0, "spanDays": 94.9 }
```

<sub>`askedSamples` 是意图，`samplesMin` 是实际攒到最少的那个槽位，`slots` 是出了读数的槽位数；
`askedDays` / `spanDays` / `chunks` / `failedChunks` 描述取数本身。</sub>

⚠️ **没有这个字段时，取短了和取够了在产物里长得一模一样。** 实测过一次：
`limit=3000` 是行数上限，加密一天 96 根，所以一次请求最多装 31 天 ——
而代码请求的是 150 天（spec 说 90，这本身是第三个值），
美股一天约 26 根 RTH，同一个请求就能装满。
后果是同一个 skill 给加密账本一把一个月的尺子、给美股账本一把五个月的，
两边都不报错，`n` 也诚实地写着 31。**只有把两本账并排看才看得出来。**

⚠️ **窗口长短不是精度问题，是读数问题。** 同一根 bar 在 31 天窗口下 |z| = 16.6，
在 90 天窗口下是 7.3 —— 一个远超阈值，一个远不到。
⚠️ **窗口的单位是同槽位样本数，不是日历天。** θz_bar（4.75 美股 / 10.0 加密）是在
signal-spec §PV5 的「前 90 天同一时刻」基线上反解出来的，而反解用的是 90 个**样本**。
对 24 小时市场两个说法一样；对美股不一样 —— 实测 90 个日历日只给出每槽 61–62 个样本。
所以取数按日历天（加密 95 / 美股 140，够就行），落基线时按 `slice(-90)` 截。
取更多历史不是更好：换了窗口，阈值就不再对应它被验证时的那把尺子。

`samplesMin < askedSamples` 时 `meta.gaps` 里有 `intraday_history_short`。
**报最少的那个槽位，不报平均** —— 平均会把一个空槽位摊平到看不见，
而正是那个槽位决定某个时刻能不能出读数。

### `producedSignals` 说这一轮真的产出了哪几条信号

```json
"producedSignals": ["PV1", "US1", "US2", "US3"]
```

⚠️ **「开着」和「有人在算」是两件事。** `config/alerts.json` 的 `enabled` 只说用户没关掉它；
这个字段说这一轮到底有没有东西在生产它。两者混在一起的后果实测过：
设置面板把盘中、财报、内部人全显示成 `on`，而当时只有日线有 producer ——
**面板在对读者撒谎**。界面对不在这个列表里的信号显示「尚未启用」，不是 `off`。

⚠️ **各 producer 只声明自己那几条，并进去而不是整体覆盖** ——
日线与盘中是两个 cronjob，整体覆盖会互相抹掉。

### `signalGrades` 是逐标的的投递上限，与阈值无关

**阈值回答「什么算过线」，`signalGrades` 回答「过线之后推不推手机」。** 两者独立：

```
thresholds     查表得到，全类别统一，建基线时锁死，之后不重解
signalGrades   在这只标的自己的全历史上现算一次，写死，之后不重算
```

**算法**（$r_t$ 是简单收益 $c_t/c_{t-1}-1$，$W=90$，$F=5$，$B=20000$）：

```
① 触发日      在全历史上逐日重跑 PV1，得 T = { t : |z_t| ≥ θz  ∧  RVOL_t ≥ θv }
                 z_t    = (r_t − med(r_{t−W..t−1})) / (1.4826 · MAD(r_{t−W..t−1}))
                 RVOL_t = V_t / median(V_{t−W..t−1})
              ⚠️ 两个分母都取**前 W 天，不含当日**

② 后 5 日波动   A_t = pstdev(r_{t+1}, …, r_{t+F})          总体标准差，先减这 5 天自己的均值

③ 基准         typ = median{ A_t : t ∈ 全部可评估日 }        ⚠️ 分母是全部日子，不是「非触发日」

④ 相对基准倍数  m_t = A_t / typ ,  t ∈ T

⑤ 自助区间     重采样 m（有放回，样本量不变）B 次，每次取中位数
              CI = [ 第 2.5% 分位 , 第 97.5% 分位 ]

⑥ 独立块       blocks = |{ t ∈ T : t − prev(t) ≥ F }|      相邻触发间隔 < F 算同一块
```

可评估区间是 $t \in [W+1,\ n-F)$ —— 头 90 天没有基线，尾 5 天没有前瞻窗。

```
区间下界 > 1.0 ∧ 块数 ≥ 5   →  maxDelivery "L1"   verdict "usable"
区间跨 1.0                  →  maxDelivery "L2"   verdict "effect_unclear"
块数 < 5                    →  maxDelivery "L2"   verdict "insufficient_sample"
```

`days` 是**这次实际用了多少根日线** —— 界面不显示，但它是「这个档位可不可信」的唯一凭据。

⚠️ **自助必须逐标的独立播种，且 B 要大到噪声远小于「到 1.0 的距离」。**

```
共用一条随机流   每只票的抽样取决于它前面处理了哪些票。实测把两只新标的挪到队首，
                TSLA 的下界从 1.011 掉到 0.970 —— 它自己一个数没变，
                只是别人插了队，告警就从推手机降成只留页面
B = 2000        TSLA 的下界在 10 个种子间落在 0.9702–1.0153，**跨着 1.0**，
                20% 的种子把它判成 L2 —— 那个档位是随机数定的，不是数据定的
B = 20000       10 个种子全部给出 1.0115，噪声消失
```

判据卡在 1.0 这条硬线上，**抽样噪声就必须远小于估计值到 1.0 的距离**。
现行实现：`random.Random(7)` 每次调用新建，`B = 20000`。
正序与完全倒序跑出的十只标的区间**逐只一致**。

⚠️ **必须用全历史,不能截到 502 根。** 官方回测用的是全历史；
截短窗口会把「这只票最近安静」误判成「这条规则在它身上不成立」——
实测 BTC 与 SOL 在 502 根窗口下块数不足，在全历史下都通过。**换窗口结论就翻。**

⚠️ **`verdict` 不是「证伪」。** `insufficient_sample` 说的是样本不够下结论，
不是效应不存在 —— BTC 的倍数 2.31、下界 1.46，效应看着是真的，只是块数曾经不够。
界面措辞必须写成「暂不评估」，不能写成「无效」。

⚠️ **界面必须解释「过线了但手机没响」。** 这是这个机制最容易被读错的地方 ——
两条腿都过、扫描表有触发标记、而手机没动静，不加说明就是系统坏了。见
[content-spec](content-spec.md) §「过线但不推送时必须说清楚」。

⚠️ **`historicalTriggers` 的 `PV1` / `PV5` 一律是「触发天数」,不是根数。**
PV5 一天可能触发多根 —— 实测 20% 的触发日是多根，BTC 与 SOL 各有一天 5 根。
**用天数是为了与 PV1 可比**：界面上 `5 │ 10` 那两个数必须是同一个单位，
否则「日线 5 次、盘中 10 次」会被读成日线更安静，而实际可能是盘中根数被当成了天数。

**逐根的明细在 `symbols/<SYM>.json` 的 `alertHistory[]` 里**：

```json
{ "d": "2026-08-21", "signalId": "PV5",
  "bars": [ { "slot": "09:00", "z": 21.15, "rvol": 21.4 },
            { "slot": "09:15", "z": 12.30, "rvol":  8.9 } ] }
```

⚠️ **`bars[].slot` 是 UTC。** 加密没有 RTH，触发可以落在任何时刻。
**界面按标的所在市场的本地时区显示，并且要标出时区** ——
五根不标时区列出来，读者会以为是盘中五个不同时段，而实际可能横跨一整天。

⚠️ **`historicalTriggers.PV5` 必须等于 `alertHistory` 里 PV5 条目的条数。**
两处不一致就是单位跑偏了，这是一条应当被断言的等式。

⚠️ **盘中的分位另存一份 `distributionBar`，不能复用日线那份。**

```json
"distributionBar": { "unit": "15min", "tz": "UTC",
                     "slots": { "21:30": { "n": 135, "p50": 0.00137, "p95": 0.00544,
                                           "histogram": { … } } } }
```

**分位必须取同一时刻**（[data-pipeline §九](data-pipeline.md)）——
全天 26 根混排会被开盘和收盘那两根结构性地压制。

⚠️ **只落今天真正触发过的那几个时刻。** 加密一天 96 个时刻，全存等于 95 个白存
（实测 19 KB/标的，只存触发的那个是 0.3 KB）。这不违反「分布不进 findings」——
它仍然按 symbol 存一份，只是不存用不到的时刻。

⚠️ **`trigger.barSlot` 是连接键，不是给人看的字符串。**
它是 UTC（跟 `distributionBar.tz` 一致），而界面一律 ET。
**要显示时刻就格式化 `triggeredAt`**，它带偏移量。
禁止切字符串取 `HH:MM` 再拼时区名 —— 加密 24 小时交易，
`08:45` 和 `04:45` 都讲得通，这个错在画面上看不出来。

⚠️ **算 `rank` 要用总体里的原值，不能用 `measured.move`。**
后者已四舍五入到 5 位，跟总体比时**那根 bar 自己会掉出去，`rank` 变成 0**。
`rank ≥ 1` 是恒等式，应当断言 —— 这是一条零成本自检，比任何统计都先发现问题。

⚠️ **`histogram` 是「幅度分位」那一块的画图数据。**

`findings[].context.sizeRank` 给的是**答案**（第 7 大 / 共 502 根），
`baselines[sym].distribution.histogram` 给的是**形状**（分布长什么样）。
卡片两样都要 —— 只给答案画不出直方图，只给形状读者得自己数。

**它不进 findings。** 分布是逐标的的属性、每日重算一次；塞进每条 finding
等于同一份数据随每次告警复制一遍。**findings 按 symbol 引用 baselines。**

40 个 bin 的计数数组每标的不到 200 字节，日频重算没有成本压力
（基线全部走免费端点）。

⚠️ **扫描行分 `price` / `volume` / `bar` 三块，`bar` 是同一行的盘中档。**

```
price.today    今日涨跌幅          price.line   过价格腿要动多少（θz × σ）
price.usual    σ_rob，「平时」那一列
volume.rvol    今日量 / 中位量      volume.line  θv 原样
volume.partial 盘中未收盘时为 true

bar.z / bar.rvol       该标的最近一根 15 分钟 bar 的两条腿
bar.slot               那根 bar 的时刻（UTC，连接键）
bar.line / volumeLine  盘中两条腿各自的线 —— 与 session 档量纲不同，不可混用
bar.bars               当日已成的 bar 数
```

⚠️ **`bar` 块的两条线叫 `line` / `volumeLine`，session 块叫 `price.line` / `volume.line`。**
两套命名并存是历史遗留。**取值时按块取，不要跨块猜名字。**

⚠️ **`state` 有两个：行上的那个描述日线，`bar.state` 描述盘中。**
一行两个粒度，用一个 `state` 表达必然对其中一个说谎 ——
实测同一天 BTC 盘中触发而日线安静。**按当前粒度取对应的那个。**

⚠️ **`thresholds` 里有四个阈值，两两成对，不可跨对取。**

```
theta_z       PV1 价格腿   1.5，全类别统一
theta_v       PV1 量能腿   美股 2.0 / 加密 3.0
theta_z_bar   PV5 价格腿   美股 4.75 / 加密 10.0
theta_v_bar   PV5 量能腿   美股 2.0 / 加密 3.0
```

**`theta_z` 与 `theta_z_bar` 量纲不同，差三倍以上，取错不会报错、只会静默放出十倍告警。**

⚠️ **加密的 `theta_v_bar` 在实测中一根都没剔除过。**
$\theta_z = 10.0$ 已经极端到「能过价格腿的 bar 成交量必然远超中位」——
146 根过价格腿的加密 bar 里 0 根被量能腿挡下（美股是 6.8–25.4%）。
**界面上不能对加密盘中说「两条线都要过」**，那句话在加密上恒真。
数据见 [results-pv](../backtest/results-pv.md)。

⚠️ **`market.json` 的四块**：`indices[]`（`change` 是点数、`changePct` 是比例，两个都有）·
`treasury` · `commodities` · `crypto`（`fearGreed` · `btcMarketCap` · `btcDominance`）·
`earningsWeek`。**`context.market` 与 `meta.market` 目前恒为 null** ——
加密无市场基准（能力边界），美股这一块尚未接线。

⚠️ **`triggerLine` 是把阈值翻译成用户能读的量。**

```
price   θz × σ —— 价格要动多少才过价格腿
volume  θv 原样 —— 量能要到中位的几倍
```

⚠️ **两档不同量纲，不能混用。**

```
session   PV1  θz 1.5                    × 日线 σ_rob        0.033 = ±3.3%
bar       PV5  θz 4.75 美股 / 10.0 加密   × 15 分钟 bar 的 σ   0.014 = ±1.4%
```

⚠️ **bar 档的 θz 分资产类别，session 档不分。** θz = 1.5 是全类别统一的（决策 #2），
但盘中两类差一倍多 —— 美股 4.75、加密 10.0，都是 8 种口径反解出来的。
**拿美股的 4.75 去判加密的 PV5，会放出约十倍的告警量。**

θz 本身就不同（1.5 vs 4.75），σ 的窗口也不同。**把日线的线套给 PV5**
会让弹窗上两条信号显示同一个数，读者以为它们用同一条线。

⚠️ **这是这条线的唯一存放处。** `findings[].trigger` 只带 `unit`，
渲染时按 `(symbol, unit)` 到这里取值 —— 与 `histogram` 同一条理由：
逐标的的属性不随每次告警复制一遍。**存两份必然漂**（实测漂过：
同一天 BTC 在扫描表上是 ±2.7%、在告警卡上是 2.8%）。

⚠️ **两条线都要过，缺一不可。** 界面上不能只说「超过 ±3.8% 就会提醒你」——
BTC 出现过日线 z = 4.64（价格腿超阈值三倍）而 RVOL 1.88 < 3.0，
**PV1 静默**。只讲价格线会让用户以为漏报。

⚠️ **`historicalTriggers` 必须与 `findings` 同源。**

它是「这条规则在这只标的上历史触发过几次」，而今天的 finding 就是其中最新的一次。
**两者各自计算就会打架** —— 实测过一次：告警卡上 BTC 今天触发 PV1，
而同一天的两年图上那一天没有标记。

```
正确    一份逐日触发历史 → 今日切片写 findings.json · 全窗口计数写 baselines.json
错误    findings 由当日行情算 · historicalTriggers 由回溯扫描算，两条路各走各的
```

⚠️ **Tab 2 的图标记也从这份历史来**，不要另算。判据、窗口、口径三样只要有一样不同，
同一天就会在一处有点、另一处没有。

**可机检**：`findings` 里每条 PV 类 finding，其 `(symbol, 日期)` 必须出现在
该标的的触发历史中；`historicalTriggers[sig]` 必须等于历史中该信号的条数。

⚠️ **`historicalTriggers` 是冷启动那天唯一能给的信号侧内容。**
新建的 playbook 第一天没有告警、没有净值历史、没有复发次数 ——
但两年基线是建仓时就算好的，「这只票过去两年响过 14 次」直接回答
新用户最想知道的「这东西多久吵我一次」。

它在建基线时顺带算出（那一遍本来就要扫完两年来建分位分布），零额外成本。

`degraded` 取值：`null` · `"high_vol"`（σ_ann 超界，PV1 降 Warning）·
`"m23_loose"`（ρ > 40%）· `"m23_strict"`（ρ < 2%，停用）· `"short_baseline"`（< 60 日）。

⚠️ **高波边界按资产类别定**：美股 σ_ann > 50% · 加密 > 92.8%。
用同一条界会让加密 L1 永久为空（25/25 都超 50%）。

---

## 六·二、`data/market.json` · Tab 3

**九个宏观端点的落盘,每小时一次。** 逐块自带时间戳 —— 商品 24 小时交易、美股不是，
统一一个时间戳必然对其中两个说谎。

```json
{
  "indices":    [{ "symbol": "SPX", "name": "S&P 500", "price": 7641.16,
                   "changePct": 0.0031, "asOf": "2026-08-21T20:04:57Z" }],
  "treasury":   { "asOf": "…", "curve": [{ "tenor": "1M", "yield": 0.0469 }],
                  "spread2y10y": 28 },
  "commodities":[{ "symbol": "GCUSD", "name": "Gold", "price": 4590.20,
                   "changePct": 0.0044, "asOf": "…" }],
  "crypto":     { "asOf": "…", "fearGreed": 31,
                  "totalMarketCap": 3.02e12, "btcDominance": 0.440 },
  "earningsWeek": { "asOf": "…",
                  "days": [{ "d": "2026-08-24", "beforeOpen": 118, "afterClose": 89, "unknown": 12 }] }
}
```

⚠️ **`earningsWeek` 带自己的 `asOf`。** 同层的 indices · treasury · commodities · crypto
四块全都带，早先只有它不带 —— 页面这一格于是没有时刻可显示，
而页面上唯一一个「财报时刻」是 `freshness.earningsCalendar`，那属于 producer-context
的**逐标的**日历，与这份**全市场**周历不是同一个数据集。
实测后果：Tab 3 列着 08-24–28，而能查到的时刻停在 08-21。**标签的主语不是它旁边的数据。**
形状照 `treasury` 的 `{asOf, …}`，不照 indices 的逐行 asOf —— 这一周是一次取回的。
⚠️ 旧形状（裸数组）消费方要继续认，落盘一律用新形状。

⚠️ **`days[]` 三列都必填，`unknown` 是 0 也要写出来。**
端点的 `time` 偶有空值。「盘前」与「不知道盘前还是盘后」是两件事，并进任一侧都是替它做判断。
省掉零值那一列的后果实测过：消费方看不出「这天没有时间未知的」和
「这份数据里没有这个概念」的区别，于是把日总数算成 `beforeOpen + afterClose`，
**每天少掉 2–12 家**，而少掉的方向恰好让「本周财报压力」看起来更轻。
**字段在不在，本身就是一句话。**

⚠️ **区间到本周日 23:59:59 为止。** 端点的 `end_time` 是闭区间，
写成「周一 + 7 天」就把下周一那天也算进「本周」—— 实测多出第六天 41 家。

⚠️ **`crypto` 块里的数字全是全市场,不是持仓派生。** 界面必须加「全市场」限定词 ——
在一个持仓产品里「BTC 占比 44%」会被读成「我的加密里 44% 是 BTC」。

⚠️ **按持仓的资产类别裁剪显示,不是裁剪文件。** 文件照常全量落盘（成本相同），
界面按 `portfolio.allocation.byAssetClass` 决定显示哪几块。见
[content-spec §六](content-spec.md)。

---

## 六·三、`data/symbols/<SYMBOL>.json` · Tab 2 逐标的页

**一只一份,每日收盘后重算。** 这里装的是 Tab 2 那一页要画的东西，
与 `baselines.json`（阈值）和 `findings.json`（今天触发了什么）分开 ——
它们三个的刷新节奏与生命周期都不同。

```json
{
  "symbol": "NVDA",
  "kline":  [{ "d": "2026-08-21", "o": 126.1, "h": 127.0, "l": 117.9,
               "c": 118.20, "v": 102864553 }],
  "intraday": { "unit": "15min", "tz": "UTC", "sessions": 3,
                "bars": [{ "t": "2026-08-21T13:30", "o": 126.1, "h": 126.8,
                           "l": 125.4, "c": 125.9, "v": 3810422 }] },
  "range52w": { "low": 103.90, "high": 174.57, "asOf": "2026-08-21" },
  "alertHistory": [{ "d": "2026-06-17", "signalId": "PV1", "z": -2.85 }],
  "insider": { "windowDays": 30, "filedInWindow": 71, "codeFilter": ["P","S"],
               "buys":  { "people": 2, "filings": 3, "signalId": "EV1",
                          "items": [{ "filingDate": "2026-06-22", "owner": "LE PHONG",
                                      "code": "P", "shares": null }] },
               "sells": { "people": 4, "filings": 12, "signalId": null,
                          "items": [{ "filingDate": "…", "owner": "…",
                                      "code": "S", "shares": 4200 }] } },
  "earnings": { "next": "2026-09-09", "time": "amc",
                "past": [ { "d": "2026-07-30", "time": "amc" },
                          { "d": "2026-04-28", "time": "amc" } ] },
  "funding":  { "asOf": "…", "unit": "8h", "threshold": 0.0005,
                "normalized": true, "normalizeNote": "…",
                "points": [{ "t": "…", "rate": 0.0004 }],
                "extremeDays": ["2026-08-19", "2026-08-20"] },
  "news":     [{ "title": "…", "url": "https://…", "publishedAt": "…", "source": "…",
                 "summary": "…", "sentiment": 0.41, "relevance": 1.0 }],
  "coverage": { "pv5From": "2024-05-02" }
}
```

⚠️ **`coverage.pv5From` 是盘中基线的起始日**，不是日线的。
盘中要满 90 天同一时刻才有 σ，所以它总是晚于日线基线起点。
**界面上说「盘中从哪天起可判」必须用它，用日线的起点会多说一段其实没在盯的日子。**

⚠️ **`funding.extremeDays` 与 `funding.points` 覆盖的窗口不是同一个。**
`points` 是近 60 天的读数，`extremeDays` 是全历史里越过阈值的日子 ——
**「近 90 天 N 次极端」这种说法两头都对不上**。界面要么说「上图范围内 N 次」，
要么说「记录中最近一次在 X」，不要给一个两边都不成立的窗口。

⚠️ **`funding.normalized` 记的是费率单位在历史中变过一次**（2025-12，量级差约 90 倍）。
`normalizeNote` 说明怎么归一的。**不归一会让 DR1 在那之前的读数全部越界。**

⚠️ **美股恒有 `insider` 键，空是空态不是缺省。**

```
键不在      这个资产类别没有内部人这回事   加密
键在 items 空  这只票本期没有公开市场买入    美股，五只里四只是这个情况
```

**合并成「键不在」会让页面留一个洞**，而读者只能把洞读成「数据没取到」。

⚠️ **`filedInWindow` 与 `filings` 差得很远，界面必须同时给。**
实测 AMD 窗口内 100 条申报、**公开市场买入 0 条**；NVDA 25 条申报、买入 0 条。
只印 `filings: 0` 会被读成「这只票没有内部人活动」——
实际是「有一百条活动，没有一条是买入」。`codeFilter` 说明筛的是哪一类。

⚠️ **买入与卖出分两组，只有买入带 `signalId`。**

```
buys.signalId  = "EV1"    记录类信号
sells.signalId = null     没有信号 —— EV2 已移出已定案 13 条（🔴 已证伪）
```

**卖出不只是「没信息」，它在大盘股上是反向的**（56 只里 6 只反向显著超随机，见
[results-ev](../backtest/results-ev.md)）。**当预警展示会指错方向。**
展示它是因为只列买入会让读者以为这只票没有内部人活动 ——
**展示与信号是两件事，`signalId` 就是那条界线。**

⚠️ **界面按 `signalId` 判，不要按 `code === "S"` 判** —— 后者是在页面上重做一次分类。

⚠️ **只取 `P` 与 `S`。** `A` 授予 · `G` 赠与 · `F` 缴税扣股 · `M` 期权行权
都是薪酬机制的产物，两边都不进。

⚠️ **`earnings.past` 是图上那一层的数据源。** 告警历史图跨 502 根，
每只美股在这个窗口里有 6–8 个财报日 —— **只给 `next` 的话图上只有一个点，
而那个点还常常是空的**（日历只向前覆盖约 30 天）。
`past` 按日期倒序，覆盖与 `kline` 相同的窗口。

⚠️ **`insider.people` 在 `filings` 前面,不是排版偏好。** EV1 的判据是人数
（$\lvert\{\text{owner\_name}\}\rvert \ge 2$），笔数单独看会误导 ——
NVDA 20 笔只有 2 人。**界面第一个数字必须是人数。**

⚠️ **`funding` 仅加密,`insider` / `earnings` 仅美股。** 不适用时整个键缺省，
不要给 `null` —— 界面按「键在不在」决定显示不显示，与告警图例同一条规则。

⚠️ **`kline` 与 `series.json` 不是一回事。** 前者是这一只的价量，
后者是整个组合的净值。**不要在 `series.json` 上画逐标的的东西。**

### `intraday` 是给盘中告警卡画图用的，不是给盘中基线用的

**一张 PV5 卡必须画 15 分钟图。** 用日线图承载一根 15 分钟的触发，
读者看到的是一根跟这次告警无关的日 K —— 那张图回答不了「当时长什么样」。

```
覆盖    最近 3 个交易日（美股约 78 根 · 加密约 288 根）
        够画出触发那根前后的形状，不够就没有上下文
用途    只画图。PV5 的基线用的是 90 天同一时刻的 bar，那批数据不进契约
tz      UTC。加密没有 RTH，触发可以落在任何时刻
        ⚠️ 界面按标的所在市场的本地时区显示，并且要标出时区
```

⚠️ **不要用它算任何东西。** 3 个交易日算不出同时刻基线（那要 90 天），
`triggerLine.bar` 与 `measured` 已经由管线算好写进契约了。**图只是图。**

⚠️ **`kline` 与 `intraday` 的粒度标签必须画在图上。**
同一张卡上如果两种图都可能出现，读者要能一眼看出正在看哪一种。

---

## 七、`config/alerts.json` · 唯一可写文件

```json
{
  "version": 1,
  "userLines": {
    "MSTR": { "US1": 125.0 },
    "AMD":  { "US2": 450.0 },
    "NVDA": { "US3": -0.12 }
  },
  "enabled": { "PV1": true, "PV5": true, "EV4": true, "US1": true, "US2": true, "US3": true },
  "channels": { "push": true, "quietHours": null }
}
```

⚠️ **值的量纲跟着信号走，不是统一的百分比。**

```
US1 止损线   价格      触发式是「现价 ≤ 用户设定值」
US2 止盈线   价格      「现价 ≥ 用户设定值」
US3 回撤线   分数      「M22 ≤ 用户设定值」，M22 是距高点回撤，本身就是分数
```

见 [signal-spec](signal-spec.md) US 族触发式。

⚠️ **用户说「跌 15% 就提醒我」时，换算在配置那一步做完，不留到运行时。**
运行时契约里 US1/US2 只接受价格 —— 界面拿到一个分数没有基数可以还原成价格，
**猜一个基数就是编**。Skill 在建 Playbook 时按当时价格换算并记下 `basis`：

```json
"MSTR": { "US1": 125.0, "US1_basis": { "pct": -0.15, "from": 147.06, "at": "2026-08-19" } }
```

`_basis` 只是留痕，运行时不读。

⚠️ **`enabled` 缺省视为全开，但不要省略它** —— 「用户关掉了 PV5」与
「这份配置是旧版本没有这个键」在缺省下长得一样。

### 三层权限

| 层 | 内容 | 用户能做什么 |
|---|---|---|
| 你设的 | `userLines` | 改数值 |
| 开关 | `enabled` | 开 / 关 |
| 我们判的 | θz · θv | **不出现在本文件** |

**θz / θv 不放进用户配置**，理由不是保守：这两个值在 92 美股 + 25 加密上验证过，
改了之后「相对基准倍数 95% 区间下界 > 1.0」这条判据不再适用 ——
用户会拿到一套没人验证过的规则，而界面还在显示已验证那套的证据等级。

---

## 八、`meta.json`

```json
{
  "generatedAt": "2026-08-21T16:05:12-04:00",
  "nextRun": "2026-08-21T16:35:00-04:00",
  "specVersion": "signal-spec.md@427f4f8",
  "scanned": { "holdings": 5, "newsItems": 187, "newsPassed": 6 },
  "freshness": { "prices": "2026-08-21T16:00:00-04:00",
                 "news": "2026-08-21T16:03:00-04:00",
                 "earningsCalendar": "2026-08-21T06:00:00-04:00" },
  "gaps": ["crypto_attribution_falsified", "newco_short_baseline"]
}
```

`scanned` 直接喂界面那句「今日扫描 N 只持仓 · M 条新闻」——
**静默日也要说话**，这三个数是唯一的证据。

---

## 九、eval 断言挂在哪

| 层 | 断言 | 依据字段 |
|---|---|---|
| L0 结构 | 七个文件 schema 合法 | 全部 |
| L1 白名单 | `findings[].signalId` ⊆ `signals.json` 且 `evidence ≠ red` | `signalId` |
| L2 参数 | 已验证类别阈值精确等于 spec；未验证类别 `thresholdSource = fallback_solved` 且可复算 | `trigger.thresholds` · `thresholdSource` |
| L3 自洽 | 无信号在给定阈值下恒真 · 降级规则不清空任何投递层 · `baselineDays < 60` 时无 `sizeRank` · 加密无 EV6/PF2/PF3 · 美股无 DR1 · `evidence ≠ green` 时不得 `push` | 跨文件 |
| L3 同源 | 每条 PV finding 的 `(symbol, 日期)` 必须在该标的的触发历史中 · `historicalTriggers[sig]` 必须等于历史中该信号的条数 · Tab 2 图标记与告警来自同一份历史 | `findings` · `baselines.historicalTriggers` |
| L3 量纲 | `unit = session` 的 finding 只出现在 PV1 · `unit = bar` 只出现在 PV5 · 渲染取的线必须是 `baselines[sym].triggerLine[unit]`，findings 内不得另存线值 · `|measured.z| ≥` 该 (unit, 资产类别) 的 θz：session 全类 1.5 · bar 美股 4.75 / 加密 **10.0** | `trigger.unit` · `triggerLine` |
| L2 账目 | `Σ holdings[].value + cash = kpi.totalValue` · `Σ weight + cash/总额 = 1` · `Σ lifetimePnl = kpi.totalPnl.abs`（三条同时成立，差额容限 0.02） | `portfolio.json` |
| L3 归因 | `timing` ∈ {`before`,`after`,`untimed`,`none`} 且**等于 `sources[]` 与 `moveAt` 的那个纯函数**（见 [data-pipeline §九](data-pipeline.md)）· 有 `chain` 来源时 ∈ {`before`,`after`} · 无 `chain` 但 `sources[]` 非空时必须是 `untimed` · `sources[]` 为空时必须是 `none` · 每条 `sources[].origin` ∈ {`chain`,`model`} · 每条 `sources[].url` 可解析 · `timing = none` 时不得有 `model` 署名 · 用户线 US1/2/3 与 EV4 的 finding 无 `attribution` · 合并卡只有一条 `attribution` · **`summary` 里不得出现 `\d{1,2}:\d{2}` 形式的时刻**（见下） | `context.attribution` |
| L3 覆盖 | `scan[].symbol` 集合 **等于** 持仓集合（不漏扫、不多扫）· 每条 `findings` 的 symbol 在 `scan` 中 `state = triggered` · `state = insufficient_baseline` 时 `price` 与 `volume` 为 `null` | `scan` · `portfolio` |
| L4 文案 | 禁止词（中英各一份） | 渲染产物 |
| L5 判断 | 只留真需要判断的，重复 ≥3 次报一致性 | — |

⚠️ **不要在归因解释里出现具体时刻。**

`summary` 是落盘的一个字符串，**它不参与任何时区转换** ——
渲染层能修的时刻它都不在其中。而卡头已经显示了触发时刻，
解释里再写一遍是重复，且重复的那一份没有任何机制保证它对。

```
输出契约里写死    Do not write clock times. The card header already shows when it fired.
断言             summary 里不得出现 \d{1,2}:\d{2}
```

模型逐字引用上下文里给的时刻串，**它不换算，也不会声明自己没换算**。
上下文里的时刻标错时区，解释里就带着错的时区落盘。

```
凡是要给人看的时刻（含递给模型的）  一律走同一个 ET 格式化函数，输入是带偏移量的 ISO
禁止                            切字符串取 HH:MM 再拼时区名
```

⚠️ **「summary 里的时刻必须能在输入上下文里找到」这条断言挡不住它。**
`09:00 ET` 确实逐字出现在输入里 —— **断言会通过，而结果是错的**。
挡它的位置在更上游：**递给模型的时刻由格式化函数产出，不由字符串拼接产出。**

⚠️ **现有 mock 数据里 SOL PV5 那条带着这个错，留着不重跑**，
作为 eval 的已知失败样本（`meta.gaps` 里的 `attribution_time_zone_leak`）。

⚠️ **eval 用录制的 fixture，不现场取数。** `market-news` / `price-target-news` /
`unlock-events` 都是 1 credit/次，一轮 92 只就是几百。本项目已经因为「以为免费」烧掉过 4,052。

⚠️ **同一组合跑两次配置必须逐字节相同。** 兜底规则里有「抽标的池反解 θv」这一步，
抽样不确定就意味着 Skill 不可复现 —— 实测随机 6 个的命中率只有 50%、区间 [2.50, 3.25]，
所以池子选法必须写死（成交额前 12）。

---

## 十、更新节奏

**不是一个 cron 全量重跑。** 各文件的驱动量不同，混成一个要么浪费调用、要么供陈旧数据。

| 文件 | 频率 | 驱动 |
|---|---|---|
| `data/signals.json` | **只在 spec 变时** | 由 signal-spec 生成，不随行情变 |
| `data/findings.json` | **15 分钟**（美股 RTH）· **持续**（加密） | PV5 是 15 分钟粒度，最快的那条决定节奏 |
| `data/portfolio.json` | 15 分钟 | 跟 findings 同批，共用价格 |
| `data/series.json` | **每日收盘后追加一点** | 净值序列是日频 |
| `data/baselines.json` | **每日收盘后重算** | 最短窗口也有 90 个交易日，盘中重算是纯浪费 |
| `data/news.json` | 见下 | 成本敏感，单独讨论 |
| `meta.json` | 每次运行 | |

⚠️ **三个窗口不是一个数，别混。**

```
σ_rob · RVOL 中位   90 个交易日   M2 不含当日
分位分布 · M23      2 年 ≈ 502    直方图与分布可用性检验
最短可用门槛        60 个交易日   低于此 PV1 / PV5 停用（PV4），这是门槛不是窗口
```

⚠️ **加密的 cron 不能只覆盖美股交易时段** —— 加密 24/7，PV5·加密 全时段有效。

⚠️ Alva cron 最小间隔 1 分钟，15 分钟没有平台限制。

### `data/news.json` · Tab 1 底部的今日相关新闻

```json
{
  "asOf": "2026-08-21T16:03:00-04:00",
  "chain": "wide",
  "minRelevance": 0.80,
  "items": [{ "symbol": "TSLA", "title": "…", "url": "https://…",
              "source": "Yahoo Finance", "publishedAt": "…",
              "summary": "…", "sentiment": 0.41, "relevance": 0.93 }]
}
```

⚠️ **这是宽链的输出，与归因的严链目的相反、阈值不共用。**
`chain` 与 `minRelevance` 记的就是这一批是按哪条链、什么门槛筛出来的 ——
**没有这两个字段，用户看到一列新闻却不知道凭什么是这几条。**

⚠️ **`url` 是端点返回的真实链接，界面直接用。**
不要替换成占位域名 —— 一条指向 `example.com` 的「相关新闻」不是免责，是把真数据丢掉了。

⚠️ **`sentiment` 只在 |值| ≥ 0.35 时着色**，其余灰色。着色是展示，不是信号。

⚠️ **`items` 为空是常态**，界面要说出「今天没有过筛的稿件」，不要留空块。

### 新闻取数按需，不轮询

`market-news` 是 **1 credit/次**，而每日额度 3,000。轮询和按需的成本差两个数量级：

```
轮询    5 只 × 26 个 RTH bar = 130 次/天 = 130 credits/天    ≈ 3,900/月
按需    只在 PV5 / PV1 触发时取（EV6 是归因源，没告警就不需要归因）
        PV5  0.422%/bar × 26 bar × 5 只 = 0.55 次/天
        PV1  10.4/年/标的 ÷ 252 × 5 只  = 0.21 次/天
        EV4  4 次/年/标的 ÷ 252 × 5 只  = 0.08 次/天
        合计 ≈ 0.84 次/天
⑥ 今日相关新闻    不要求触发，每日一次 × 5 只 = 5 次/天
                  合计 ≈ 6 credits/天
```

**按需取数的依据是 EV6 的定位**：它是挂在告警卡上的归因源，不是独立信号。
没有告警的 bar 不需要归因，取了也无处显示。

⚠️ **这个结论依赖触发率。** 组合变大或阈值放宽，成本线性上升 ——
10 只组合约 12 credits/天，30 只约 35。**取数前先按触发率估算，不要先跑再看账单。**
本项目已经因为「以为免费」在一次社交语料取数上烧掉 4,052。

⚠️ **计费必须等延迟后核对**，解析 `alva credits items --today` 的 `extras.by_endpoint`
按端点比对调用数。即时读余额会看到「没变」，那是假的 —— 本项目因此记错过三次。

### 哪些端点免费

```
免费   股票日线 · 加密日线 · 盘中 · 宏观 · 内部人 · 议员 · earnings-calendar · funding-rate
计费   market-news · price-target-news · crypto/unlock-events · arrays_x_feed · ask（含 MCP）
未知   stocks/company/detail（logo · sector · ipo_date）—— 用前须核对
```

**基线重算全部走免费端点**（日线 + 盘中），所以每日重算没有成本压力。
成本只集中在新闻一处。

---

## 十一、初始化与增量

```
初始化   建 playbook 时跑一次，或持仓变化时对新增标的补跑
增量     15 分钟 / 每日两条 cron，只算最新一段
```

### 初始化做什么

| 步骤 | 内容 | 成本 |
|---|---|---|
| ① 拉历史 | 每只标的**全部可得日线**；分位分布只取最近 502 sessions | 免费端点 |
| ② 建基线 | σ_rob · 分位分布 · M23 分布可用性检验 | 纯计算 |
| ③ **定阈值** | 已验证资产类别直接取 spec；未验证类别跑兜底反解 | 免费端点 |
| ④ 写盘 | `baselines.json` · `series.json` 起点 | |

**日线是免费端点，所以初始化是时间成本不是 credits 成本。**

### 阈值只在初始化时定，增量不重解

这是这套设计里最容易踩的坑。

```
❌ 每次增量重跑兜底反解    θv 随市场漂移，用户看到阈值无声变化
                        「同一组合两次运行配置逐字节相同」这条断言直接挂掉
✅ 初始化定阈值并写进 baselines.json 锁定
   只在两种情况重解：持仓新增标的 · 用户显式重建
```

### σ 滚动，θ 不动

两者节奏不同，但不矛盾：

```
σ_rob · 分位分布    每日滚动更新   「这只票现在的常态是什么」  会变
θz · θv            锁定           「多少倍常态算异常」        不变
```

**这正是整套设计的核心** —— 相对该标的自身常态，而不是固定百分比。
常态本身当然会随时间变，但「几倍算异常」是在样本池上验证过的规则，不该跟着漂。

### 增量做什么

| cron | 内容 |
|---|---|
| **15 分钟**（美股 RTH · 加密全时段） | 拉最新 bar → 算 findings → 触发时才取新闻 → 覆写 `findings.json` · `portfolio.json` |
| **每日收盘后** | `series.json` 追加一点 · `baselines.json` 滚动重算 σ 与分位 |

### 三个边界

**新增持仓** → 对该标的跑一次初始化（②③④），不要整体重建。

**基线不足 60 日** → `baselines.json` 标 `degraded: "short_baseline"`，
findings 不带 `context.sizeRank`，界面走 PV4 覆盖标注。
`company/detail` 的 `ipo_date` 可把这条说成「上市第 41 天」，比抽象天数好懂。

**数据缺口**（停牌 · 假期 · 端点故障）→ 增量要能回填，
`meta.json.freshness` 暴露每类数据的最后更新时刻，界面据此判断是否标注陈旧。

⚠️ **`freshness.prices` 是「自动化最近跑完的时刻」，不是「价格是那一刻的」。**
每个 producer 跑完把它推到 `new Date()`，所以美股收盘之后它照样每 15 分钟往前走，
而价格停在收盘。两个时刻在开盘时段重合，收盘后就分开。

界面上因此念作「最近检查 / checked」，**不念「行情更新于 / prices」** ——
后者会让人以为持仓金额也是那一刻重算的。字段名保留 `prices` 是为了不动契约与四个 producer；
它念什么和它叫什么在这里不是一回事，而**用户只看得见前者**。

### 净值序列的起点是接入日，不是开仓日

`series.json` 只能从 playbook 建立那天开始记 —— 除非 `alva portfolio` 能提供历史持仓快照，
否则我们没有「三个月前你持有什么」的信息，无法回推历史净值。

⚠️ **真要回推（demo 或没有历史快照时），必须自报家门。**

```
basis      "actual" | "backcast"
basisNote  回推的口径。backcast 时必填
```

**`basis = "backcast"` 时 `kpi.fromHigh` 也是回推的** ——
界面上「距高点 −39.23%，420 个交易日前」在回推序列上是一句关于
「如果你一直持有今天这些份额」的话，不是关于这个账户的话。**必须标出来。**
同时进 `meta.gaps`（`nav_series_backcast`）。

**界面必须写明这条**：前几周的净值图会很短，那是数据起点不是组合刚建立。
这属于 `meta.json.gaps` 的一项。
