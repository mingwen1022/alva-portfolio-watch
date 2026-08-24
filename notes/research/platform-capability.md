# Portfolio Watch 方法论调研

> 目的：为 Portfolio Watch Skill 的设计，梳理**可做的监控维度**，并把每个维度对照 Alva 平台的**真实数据可得性、覆盖范围、现成零件**。
>
> 调研信源（全部一手，非二手转述）：
> - Alva Skillhub 全部 **34 个 skill**（`alva skillhub list/get/file`，免认证可读）
> - Arrays 数据层 **19 个 data-skill** 及其端点数（`alva data-skills list`）
> - 官方 `alva/portfolio-watch-setup` 的 SDK 接口与输出 schema
> - 官方 `alva/company-anomaly-read`（16.4KB）——**含已公开的异动检测阈值**
> - 官方 `alva/company-data-aggregate`（13.9KB）——15 类信号的 sourceType 目录
> - 社区 `long-us-10x/portfolio-digest`（12.5KB）与 `watchlist-digest`（11.8KB）

---

## 一、先看数据层：19 个 Arrays Data Skill

方法论的天花板由数据决定。这是平台实际能给的全部：

| 数据域 | Skill | 端点 | 关键内容 |
|---|---|---|---|
| **现货价量** | `spot-market-price-and-volume` | 4 | 美股/非美股 K 线、Binance 现货、Hyperliquid 现货 |
| **股票指标** | `stock-metrics` | 4 | 市值、均线、EMA/SMA、RSI、MACD、布林、VWAP、beta、波动率、PE/PB/PS、股息率、EV/EBITDA、涨跌幅、**暗池 OHLC**、PIT 质量评级 |
| **基本面** | `equity-fundamentals` | 11 | 公司档案（含 `0700.HK`/`000660.KS` 等非美股）、高管薪酬、三大报表、流通股本、财年日期 |
| **预期与目标价** | `equity-estimates-and-targets` | 4 | 分析师目标价新闻/共识/摘要、共识预期（EPS/SALES/EBITDA）、公司指引 |
| **公司事件** | `equity-events` | 10 | 股息、拆股、财报日历、**财报电话会纪要**、SEC 财报发布文件、IPO、并购、增发、众筹 |
| **持股与资金流** | `equity-ownership-and-flow` | 4 | 机构持仓、**内部人交易**、**议员交易**、**做空数据**（做空股数、回补天数、占流通比） |
| **期权** | `options` | 4 | 合约规格、期权 K 线/VWAP、**历史希腊字母**（delta/gamma/theta/vega）+ 隐含波动率、**完整期权链快照**（含未平仓） |
| **ETF** | `etf-fundamentals` | 5 | 持仓、国家/行业权重、**资金流** |
| **宏观** | `macro-and-economics` | 10 | 国债利率、CPI、GDP、失业率、通胀、消费者信心、**外汇**、**大宗商品**（黄金/白银/原油）、指数（^SPX/^DJI/^IXIC）、**VIX** |
| **新闻** | `news` | 1 | 市场新闻 |
| **社交** | `social-feeds` | 6 | 追踪的 X 账号帖子（历史+最新）、按 URL 查帖、**全文检索**、账号元数据、当前追踪列表、**新增追踪账号** |
| **加密衍生品** | `crypto-futures-data` | 6 | 永续 K 线（Binance USDT / Hyperliquid USDC，**含 HIP-3 代币化股票如 AAPL/TSLA**）、**资金费率**、**未平仓量**、多空比、主动买卖量 |
| **加密链上** | `crypto-metrics-and-screener` | 18 | 代币档案、市值、供应量、**恐惧贪婪指数**、MVRV/NUPL/SOPR/实现价格/杠杆率/SSR/**鲸鱼比例**/Puell/矿工转交易所/inflow CDD、**代币解锁日程**、BTC 相关性 |
| **交易所流** | `crypto-exchange-flow` | 1 | 流入/流出/净流 |
| **链上万能通道** | `crypto-analytics-passthrough` | ~245 | 网络数据（费用/算力/UTXO/地址/供应）、矿工流、实体间流、基金数据、eth2、AMM/DEX |
| **预测市场** | `polymarket` | 18 | 市场发现、实时/历史定价、订单簿、持仓与盈亏、成交历史、**未平仓量** |
| **半导体现货** | `semiconductor-price` | 6 | DRAM/NAND 现货与合约价、DXI 指数 |
| **公司持币** | `company-crypto-holdings` | 1 | 上市公司加密持仓 |
| **筛选器** | `stock-screener` | 6 | 基础信息/事件/财务技术指标筛选 |

**读法**：端点数是能力密度的粗略指标。`crypto-metrics-and-screener`（18）和 `polymarket`（18）是覆盖最厚的两块；`news`（1）和 `crypto-exchange-flow`（1）最薄。

---

## 二、监控维度全景（十大类）

每个维度标注：**数据可得性 / 覆盖范围 / 现成零件 / 适合做成什么信号**。

### 1️⃣ 价格与波动（技术面）

| 信号 | 数据可得 | 说明 |
|---|---|---|
| 日内/日线涨跌幅 | ✅ | `spot-market-price-and-volume` |
| 相对自身历史的 z 分数 | ✅ | 需自算，官方用 **90 交易日**滚动 |
| 均线穿越（50MA/200MA） | ✅ | `stock-metrics` 直接给 |
| 52 周高低点突破 | ✅ | — |
| RSI / MACD / 布林 | ✅ | `stock-metrics` 或 `@alva/algorithm` 本地算 |
| 已实现波动率 / beta | ✅ | `stock-metrics` |
| 回撤（距高点） | ✅ | 需自算 |
| 缺口（跳空） | ⚠️ | 需从 OHLC 自算；盘前需注意 move basis |

**现成零件**：`alva/company-anomaly-read`（约 3000 只美股，15 分钟粒度）、`alva/relative-price-performance`

---

### 2️⃣ 成交量与流动性

| 信号 | 数据可得 | 说明 |
|---|---|---|
| 成交量 z 分数 | ✅ | 官方用**同时段累计量 vs 90 日基准**，仅正常交易时段 |
| 异常放量 | ✅ | — |
| 暗池成交 | ✅ | `stock-metrics` 有 darkpool OHLC ⭐ 少见 |
| 换手率 | ⚠️ | 需结合流通股本自算 |
| 加密主动买卖量 | ✅ | `crypto-futures-data` |

**要点**：官方明确**价格类信号必须有成交量确认**——社区版 blueprint 更进一步要求 *move AND volume AND attribution 三者同时*。

---

### 3️⃣ 催化剂与公司事件

| 信号 | 数据可得 | 覆盖 |
|---|---|---|
| 财报日历（即将/最近） | ✅ | `equity-events`；**不含历史**，历史查 fundamentals |
| 财报电话会纪要 | ✅ | ⭐ 全文可得 |
| SEC 财报发布文件 | ✅ | — |
| 股息 / 除权 | ✅ | — |
| 拆股 | ✅ | — |
| 并购 | ✅ | — |
| IPO / 增发 | ✅ | — |
| 评级与目标价变动 | ✅ | `equity-estimates-and-targets`，近 30 天 |
| 指数调整 | ❌ | 数据层无直接端点，需从新闻抓 |
| 解禁 | ⚠️ | 股票无；**加密有**（`crypto-metrics` 的代币解锁日程） |

**现成零件**：`anthropic/catalyst-weekly`（前瞻日历）、`lake/pre-earning-analysis` / `post-earning-analysis`

---

### 4️⃣ 基本面与预期修正

| 信号 | 数据可得 | 说明 |
|---|---|---|
| 共识预期修正（EPS/营收） | ✅ | ⭐ **这是最被低估的信号** |
| 分析师目标价变动 | ✅ | 近 30 天 |
| 公司指引变化 | ✅ | — |
| 估值倍数偏离 | ✅ | `stock-metrics` 给 PE/PB/PS/EV-EBITDA |
| 三大报表变化 | ✅ | 季度粒度，对高频监控意义有限 |
| PIT 质量评级 | ✅ | 字母评级 A+/B/C |

**要点**：财报只有季度粒度，但**预期修正是连续的**——对持仓监控而言，"分析师在悄悄下调"比"上季度营收多少"有用得多。

---

### 5️⃣ 资金流与持仓结构

| 信号 | 数据可得 | 覆盖 |
|---|---|---|
| 内部人交易（Form 4） | ✅ | **仅美股**，近 30 天 |
| 议员交易 | ✅ | **仅美股**，近 30 天 ⭐ |
| 机构持仓 | ✅ | 13F 粒度（季度，滞后） |
| 做空数据 | ✅ | 做空股数、回补天数、占流通比 ⭐ |
| ETF 资金流 | ✅ | `etf-fundamentals` |
| 加密交易所流入流出 | ✅ | — |
| 鲸鱼动向 | ✅ | `crypto-metrics` 鲸鱼比例、矿工转交易所 |

---

### 6️⃣ 衍生品与市场结构

| 信号 | 数据可得 | 说明 |
|---|---|---|
| 期权链快照（全合约） | ✅ | 含 OHLCV、希腊字母、IV、未平仓 |
| 隐含波动率变化 | ✅ | — |
| Dealer Gamma 敞口（GEX） | ✅ | **现成零件 `alva/gex`**，含 gamma flip、call/put wall、vanna/charm |
| 异常期权活动 | ⚠️ | 需自算；**社区版 blueprint 明确说"no options-sweep"** |
| 加密资金费率 | ✅ | — |
| 加密未平仓量 | ✅ | — |
| 多空比 | ✅ | — |
| 爆仓 | ⚠️ | 社区版提到，数据层无直接端点 |

**注意**：`alva/gex` 明确 **不支持指数**（SPX/NDX/VIX），要用 SPY/QQQ 代理。

---

### 7️⃣ 舆情与叙事

| 信号 | 数据可得 | 说明 |
|---|---|---|
| 追踪账号的帖子 | ✅ | `social-feeds`，**可动态新增追踪账号** ⭐ |
| 全文检索 | ✅ | 跨索引语料 |
| 按 URL 查帖 | ✅ | 用于溯源 |
| 公司新闻 | ✅ | `news` + `company-data-aggregate` 的 `market_news` |
| 行业新闻 | ✅ | `industry_news`（提及本公司或同业） |
| KOL 观点与胜率 | ✅ | **FinTwit Alpha League**，`alva/fintwit-roundtable` |
| 投资者关注度 | ✅ | `alva/what-investors-are-looking-for`，约 **2960** 只 |
| 宏观突发事件 | ✅ | `alva/query-breaking-news-feed`；**不是逐公司新闻流** |

**关键设计点**（来自社区版）：社交发现的突发要携带**原始事件时间** `source_event_time`——**旧事重发要标记为 `resurfaced` 而非 `new`**。

---

### 8️⃣ 宏观与跨市场

| 信号 | 数据可得 |
|---|---|
| CPI / GDP / 失业率 / 通胀 | ✅ |
| 国债利率曲线 | ✅ |
| FOMC / 数据发布日历 | ✅ |
| VIX | ✅ |
| 外汇 | ✅ |
| 大宗商品（金/银/油） | ✅ |
| 三大指数 | ✅ |
| 半导体现货价（DRAM/NAND/DXI） | ✅ ⭐ 极少见，对半导体持仓极有价值 |
| 预测市场概率 | ✅ Polymarket，18 个端点 ⭐ |

**机会点**：**预测市场 + 半导体现货价**这两块几乎没人用在持仓监控里，但对特定持仓（半导体、政策敏感股）是差异化信号。

---

### 9️⃣ 组合层面 ⭐ Portfolio Watch 独有

**这是唯一真正利用了"这是组合而不是自选股"的维度**，也是最容易做出差异化的地方。

| 信号 | 需要什么输入 | 说明 |
|---|---|---|
| 权重集中度 | 仓位权重 | 单一标的或单一主题超配 |
| 主题/行业暴露 | 权重 + 分类 | 官方 snapshot 里有 `theme exposure` |
| 相关性上升 | 仅需标的 | "你的三只票现在都在赌同一件事" |
| 组合 beta 漂移 | 权重 | `stock-metrics` 给个股 beta |
| 再平衡漂移 | 目标权重 | ⚠️ **必须区分价格驱动的漂移 vs 真实配置变化** |
| 现金/购买力状态 | 账户连接 | `portfolio.summary` |
| 止盈/止损线 | 成本价 | 可读用户真实 `trading risk-rules` |
| 距高点回撤 | 持仓历史 | — |
| 归因到组合盈亏 | 权重 | 谁贡献了今天的盈亏 |

**社区版默认值**：止盈 +25% · 止损 −15% · 距高点回撤 −10% · 集中度 30%

---

### 🔟 另类与特殊

| 信号 | 可得 | 备注 |
|---|---|---|
| 上市公司加密持仓 | ✅ | 对 MSTR/COIN 类标的有用 |
| 代币解锁日程 | ✅ | 加密专属，重大稀释事件 |
| 脱锚检测 | ⚠️ | 需自算 |
| 链上万能通道 | ✅ | ~245 个端点，深度链上分析 |

---

## 三、官方已公开的异动检测规则 ⭐

`alva/company-anomaly-read` 里明确写着：**"this is exactly the detection logic to reimplement for a symbol Alva doesn't cover"**（这就是给未覆盖标的重新实现时该用的检测逻辑）。

### 检测规则（任一命中即为异动）

| 规则 | 条件 |
|---|---|
| `price_z1` / `z2` / `z3` | **双侧** `\|z\| ≥ 1 / 1.5 / 2`，`z = (move − mean) / stdev`，基于**过去 90 交易日**的日收益 |
| `volume_z1` / `z2` / `z3` | **单侧** `z ≥ 1 / 1.5 / 2`，今日**同时段累计量** vs 前 90 日基准，**仅正常交易时段** |
| `price_move_abs` | `\|move\| > 5%` 且 `\|z\| < 1` —— 给**高波动标的**的绝对值兜底（它们的 1σ 太大会掩盖真实异动） |
| `insufficient_history_price_move` | `\|move\| > 5%` 且**无 z 可用**（IPO / 历史太短） |

### Move basis（容易踩的坑）

- 盘前 / 正常时段 → 对比**前一收盘**
- 盘后 → **算作新的一天**，对比**当日收盘**

### Episode 状态机

异动不是孤立事件，而是有**连续区间（episode）**的概念：

| `attributionClassKey` | 效果 |
|---|---|
| `new_anomaly` | **开启**新 episode |
| `continued_new_attribution` | 继续，且有新确认的驱动因素 |
| `continued_no_new_attribution` | 继续，LLM 跑了但没通过晋升 |
| `continued_no_info` | 继续，无新材料 |
| `skipped` | 数据质量跳过，保持 episode 开启 |
| `not_triggered` | 无规则命中 → **关闭** episode |
| `insufficient_history` | 低历史标的绝对值未达标 → 关闭 |

**这个设计的价值**：避免同一次异动被反复推送。**"这是同一件事的延续"和"这是新的一件事"是两种状态**，直接决定推不推。

---

## 四、归因方法：beta 加权三层分解 ⭐

官方的归因不是简单相减，而是 **beta 加权**：

```
总涨跌 = 市场层贡献 + 行业层贡献 + 个股特异部分
         (market.layerPct)  (sector.layerPct)  (idiosyncratic.beyondSectorPct)
```

- 市场层和行业层按该标的的 **beta 缩放**，不是朴素相减
- 剩余的个股特异部分 = **相对价格表现 RPP**，再用该标的自身波动率标准化成 z
- 方法对应 `alva/relative-price-performance`

### 降级状态（必须处理）

| 状态 | 含义 |
|---|---|
| `sector.applied: false` | 同业太少 → 只有市场层 + RPP |
| `method: "additive_fallback"` | 无 beta → 朴素相减，`z: null` |

### 核心原则

> **只对"个股特异部分"负责解释。** 市场层和行业层的涨跌不需要找公司自己的原因。

社区版把这条讲得更直白：*decompose macro tape → sector group → name-specific residual; **only owe a driver for the residual***。

---

## 五、社区版的触发规则（对照参考）

`long-us-10x/portfolio-digest` 的分类：

| 类别 | 触发条件 | 能否单独触发 |
|---|---|---|
| **市场类** | 异常波动 ≥2× 30日常态 · 成交量确认 ≥2× 30日 · 技术位（50MA / 52周高低） | ❌ **必须 move AND volume AND attribution 三者同时** |
| **催化剂/新闻** | 财报/指引 · 评级/目标价 · 并购 · 监管/法律 · 8-K · 除权 · 解禁 · 指数调整 · 内部人/议员 · 重大新闻 | ✅ 可单独 |
| **加密专属** | 黑客/漏洞 · 上币 · 监管 · ETF/政策 · 网络升级 · 代币解锁 · 脱锚 · 暂停 · 鲸鱼流 | ✅ |
| **宏观** | CPI / FOMC | ✅ |
| **流动性异常** | 加密主动买卖/净流/资金费率-OI/爆仓 · ETF 资金流 · 股票异常放量 | ✅ |
| **风险线**（仅持仓） | 止盈 / 止损 / 距高点回撤 / 集中度 | ✅ |
| **再平衡与现金**（仅持仓） | 漂移/超配 · 现金状态 | 摘要中呈现，剧烈漂移可告警 |

**注意两套阈值不同**：官方用 90 日 z 分数，社区版用 30 日 2 倍常态。前者更统计化，后者更直观。

---

## 六、降噪与排序方法论

### Token 三层模型（成本控制的关键）

来自社区版，直接解决"高频轮询会烧爆 credits"：

```
第 1 层  每次轮询 · 无 LLM      确定性价量技术 + 风险线检查 + 廉价新闻预筛
                                → 绝大多数轮询静默，近零成本
第 2 层  有候选 · 轻量 LLM      新闻/社交相关性 + 重要性 + KOL 情绪
第 3 层  重大事件 · 完整 LLM    逐标的归因 → 最终分析师筛选/抑制 → 决定推送与措辞
```

### 静默设计

官方 SDK 把 `shouldPush` 做成一等公民，并明确：

> **"Do not treat `shouldPush: false` as a failed run: a healthy quiet run intentionally suppresses a user notification."**

配套三条：
1. 静默运行也**写记录**（skip sentinel），时间序列不留洞
2. **被抑制的发现也存下来，且存抑制原因** → 用户能问"为什么没提醒我"
3. **静默 ≠ 安全** —— 必须能区分"我覆盖不到"和"确实没事"

### 可用的排序维度

| 维度 | 说明 |
|---|---|
| 信号强度 | z 分数绝对值 |
| **仓位权重** | 对用户的实际影响 = 权重 × 涨跌幅 |
| 归因确定性 | 有确认驱动 > 无法解释 |
| 事件类型优先级 | 风险线穿越 > 催化剂 > 单纯波动 |
| 新颖度 | 新 episode > 同一 episode 的延续 |
| 时效 | 事件发生时间 vs 发现时间 |

---

## 七、覆盖矩阵：不同资产类别能拿到什么

| 资产类别 | 价量 | 异动 feed | 归因 | 基本面 | 内部人/议员 | 期权 | 社交 |
|---|---|---|---|---|---|---|---|
| **美股（约 3000 只覆盖）** | ✅ 日内 | ✅ 15 分钟 | ✅ 三层分解 | ✅ | ✅ | ✅ | ✅ |
| **美股（覆盖外）** | ✅ 日内 | ❌ 需自建 | ⚠️ 需自算 | ✅ | ✅ | ✅ | ✅ |
| **加密** | ✅ 实时 | ❌ | ⚠️ | — | — | — | ✅ |
| **非美股**（`0700.HK` 等） | ⚠️ **精选子集**，日内覆盖更窄 | ❌ | ❌ | ✅ 档案 | ❌ 美股专属 | ❌ | ✅ **X 索引支持非美股** |
| **ETF** | ✅ | ❌ | 需看成分股 | ✅ 持仓+资金流 | — | ✅ | ✅ |
| **预测市场** | ✅ Polymarket | — | — | — | — | — | — |

**降级原则**（`ticker-read.md` 原话）：

> **"Method availability is rollout state, not company coverage."**
> 我的方法覆盖不到 ≠ 这只票确实没事。**catalog 404 和"该标的无异动"必须分开报。**

---

## 八、空白与机会

调研下来，几个**基准（官方 SDK + 社区版）都没做好或没做**的地方：

| 机会 | 说明 | 难度 |
|---|---|---|
| **界面** ⭐⭐⭐ | 社区版立场是 *"The message is the product"*，界面只是 8KB 的 companion timeline。而作业**第一条要求就是界面** | 中 |
| **Alert → 界面锚点** ⭐⭐⭐ | 社区版的按钮指向"回频道深聊"，**不是回界面定位**。作业明确要求"点开能顺到对应内容" | 中 |
| **组合层面信号** ⭐⭐ | 相关性上升、主题暴露集中——唯一真正利用"组合"属性的角度，两个基准都只做了浅层 | 高 |
| **预测市场信号** ⭐ | Polymarket 18 个端点，无人用于持仓监控 | 低 |
| **半导体现货价** ⭐ | DXI/DRAM/NAND，对半导体持仓是独特前瞻信号 | 低 |
| **暗池数据** ⭐ | `stock-metrics` 有 darkpool OHLC，几乎无人使用 | 低 |
| **做空数据** ⭐ | 回补天数、占流通比——squeeze 风险预警 | 低 |
| **非美股降级策略** ⭐⭐ | 两个基准都以美股为中心，非美股处理粗糙 | 中 |

---

## 附：关键引用速查

**异动检测**
```
price_z:  |z| ≥ 1/1.5/2,  z=(move−mean)/stdev,  trailing 90 trading days
volume_z: z ≥ 1/1.5/2 (one-sided),  same-slot cumulative vs 90d baseline
abs floor: |move| > 5% while |z| < 1
```

**归因分解**
```
move = market.layerPct + sector.layerPct + idiosyncratic.beyondSectorPct
                                            ↑ = RPP，再标准化为 z
beta 加权，非朴素相减
```

**社区默认风险线**
```
止盈 +25% · 止损 −15% · 距高点回撤 −10% · 集中度 30%
```

**推送长度上限**
```
Telegram 4096 · Discord 4096 · Slack 3000/section · WhatsApp ~10 行
超预算 → 收紧，不截断
```
