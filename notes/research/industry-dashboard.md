# 持仓监控：业界现成做法调研

> 目的：搞清楚**真实产品里常规在用的**持仓监控指标、看板区块、告警类型和阈值惯例，为 Portfolio Watch Skill 的设计提供外部参照。
>
> 与 `platform-capability.md` 的分工：那份是 **Alva 内部能力**（数据层、现成 skill、官方阈值），这份是**外部业界实践**。

---

## 一、参考产品谱系

调研下来，持仓监控产品分三层，能力和取向差别很大：

| 层 | 代表 | 取向 |
|---|---|---|
| **机构级** | Bloomberg PORT / MAC3 · IBKR PortfolioAnalyst · FactSet | 因子暴露、事前风险、跟踪误差、归因 |
| **专业零售 / 顾问** | Koyfin · Guardfolio · Morningstar | 敞口分析、持仓重叠、回撤、再平衡漂移 |
| **零售 App / 券商** | Fidelity · Schwab · Yahoo Finance · TradingView · Stock Alarm | 价格/百分比/均线/52周 告警 |
| **加密专属** | CoinStats · Delta · Zerion · DeBank | 多链聚合、鲸鱼追踪、上币提醒 |
| **AI Agent 级**（新） | Stock Alarm AI agent 等 | **重要性判断 + 降噪** ← 与本作业最接近 |

---

## 二、看板：标准区块清单

### IBKR PortfolioAnalyst —— 最完整的一份（19 个区块）

这是我找到的最系统的看板结构，可以直接当 checklist 用：

| # | 区块 | 内容 |
|---|---|---|
| 1 | **Key Statistics** | 核心指标概览 |
| 2 | **Investment Themes** | 主题敞口 + 每个主题下的公司 ⭐ |
| 3 | **Holdings** | 持仓价值与表现 |
| 4 | **Change in NAV** | 净值与收益，含出入金 |
| 5 | **Performance** | 累计与分期收益，**多空拆分** |
| 6 | **Portfolio Movers** | 个股表现（谁在推动组合）⭐ |
| 7 | **Allocation** | 价值与权重，多空拆分 |
| 8 | **ESG** | ESG 评级 |
| 9 | **Allocation Goals** | **当前 vs 目标**配置 ⭐ |
| 10 | **Attribution vs. Benchmark** | 板块配置效应 + 个券选择效应 |
| 11 | **Performance by Sector** | 分板块表现 |
| 12 | **Risk Measures** | 最大回撤、Sortino、Sharpe、Calmar、Alpha、Beta |
| 13 | **Concentration** | 集中度（按价值和权重） |
| 14 | **Activity** | 交易、出入金、利息、费用、分红 |
| 15 | **Projected Income** | 未来一年预计分红与利息 |
| 16 | **Fixed Income** | 平均久期、票息 |
| 17 | **Value at Risk** | 历史法 + 方差法 VaR |
| 18 | **Greeks** | Delta / Gamma / Theta / Vega |
| 19 | **Interest Rate Sensitivity** | 利率敏感度 |

**注意 #2 主题敞口** —— 和 Alva 官方 SDK 的 `themeExposure` 是同一个概念，说明这是行业共识而非 Alva 独创。

### Koyfin —— 顾问向的补充区块

| 区块 | 说明 |
|---|---|
| **Exposure Analysis** | 按资产类别 / 板块 / 国家 / 债券信用等级拆解 |
| **Holdings Contribution** | 个股对组合表现的贡献度 |
| **持仓重叠分析** ⭐ | 同一只票**直接持有 + 通过基金间接持有**的合计敞口 |
| **Top Drawdowns** | 历史最大几次回撤 |
| **Stress Test** | 在历史压力时段的表现 |
| **Allocation Drift** | 相对目标的漂移 |

**持仓重叠**这一项零售产品普遍没有，但对"我以为分散了其实没有"这个真实痛点很关键。

### Bloomberg PORT / MAC3 —— 机构级独有

- **因子暴露**：growth / value / momentum / volatility 等基本面因子
- **事前（ex-ante）风险**：预测风险，而非历史风险
- **Tracking Error**：相对基准的跟踪误差
- 多资产统一因子模型（股 / 债 / 商品 / 另类）

---

## 三、常规在用的指标清单

按用途分组，标注**普及程度**：

### 收益类

| 指标 | 普及度 |
|---|---|
| 时间加权收益（TWR） | 机构标配 |
| 资金加权收益（MWR / IRR） | 机构标配 |
| 累计收益 / 分期收益 | 全层通用 |
| 相对基准超额 | 专业级以上 |
| 日/周/月盈亏贡献分解 | 专业级以上 |

### 风险类

| 指标 | 普及度 |
|---|---|
| **最大回撤（Max Drawdown）** | **全层通用** |
| **波动率（标准差）** | 全层通用 |
| **Beta** | 全层通用 |
| **Sharpe Ratio** | 全层通用 |
| Sortino Ratio | 专业级 |
| Calmar Ratio | 专业级 |
| Alpha | 专业级 |
| **VaR（历史法 / 方差法）** | 机构级 |
| 压力测试 | 机构级 |
| Tracking Error | 机构级 |

### 结构类 ⭐ 与持仓监控最相关

| 指标 | 说明 |
|---|---|
| **单一持仓权重** | 最基础也最重要 |
| **板块权重聚合** | 按 GICS 板块汇总 |
| **国家 / 地域敞口** | — |
| **主题敞口** | 跨板块的叙事级聚合 |
| **持仓重叠**（ETF 穿透） | 把 ETF 拆成成分股，发现隐藏集中 |
| **多账户合并敞口** | 跨券商合并看同一发行人 |
| **相关性结构** | 尤其"压力期相关性"（正常时分散、危机时同涨同跌） |
| **配置漂移** | 相对目标权重的偏离 |
| **现金比例** | 干火药 vs 满仓 |

---

## 四、告警类型：业界通行清单

### 五大类（零售到专业的通行分法）

```
① 价格类告警    ② 技术图形告警    ③ 新闻/事件告警
④ 组合风险告警  ⑤ 券商原生告警
```

### 具体类型与触发条件

| 类别 | 告警 | 典型触发 |
|---|---|---|
| **价格** | 绝对价位 | 触及指定价格 |
| | **百分比变动** | 相对前收盘涨跌 X% |
| | 52 周高/低 | 突破 52 周高点或跌破低点 |
| **技术** | 均线穿越 | **20 / 50 / 200 日 EMA** 上穿或下穿 |
| | RSI | 超买超卖 |
| | **成交量异动** | 放量 / 缩量 |
| **事件** | 财报 | 财报日、业绩发布 |
| | 分红 | 除权除息 |
| | **SEC 文件（EDGAR）** | 8-K、10-Q 等 |
| | **内部人 Form 4** | 内部人买卖 |
| | **分析师动作** | 评级上调/下调、目标价变动 |
| | **预期修正** | 盈利预期上修/下修 |
| | **议员交易披露** | 国会成员申报 |
| | **13F 机构变动** | 季度机构持仓变化 |
| **组合风险** | 集中度 | 单一持仓/板块超阈值 |
| | **配置漂移** | 偏离目标权重 |
| | **相关性结构变化** | 分散度下降 |
| | 波动率飙升 | 组合波动异常 |
| **加密专属** | 鲸鱼转账 | 大额链上转移 |
| | 新交易所上币 | — |
| | （资金费率、解锁等） | 部分产品有 |

### 券商原生告警（Fidelity 的四类，最精简的基线）

1. **价格告警** —— 触及指定价格；文中特别提到"在财报等重大新闻事件前后尤其有用"
2. **百分比变动告警** —— 相对前收盘的百分比变化，"把价格变动放进上下文"
3. **EMA 告警** —— 20 / 50 / 200 日指数均线穿越
4. **52 周高低告警**

**这四类可以视为最低配基线。** 做不到这四类的产品没有竞争力；只做到这四类的产品也没有差异化。

---

## 五、阈值惯例（最实用的部分）⭐

调研里最有价值的是这些**行业约定俗成的数字**——可以直接作为你的默认值，或作为你偏离时的对照基准。

### 集中度阈值

| 风险类别 | 关注线 | 高风险线 |
|---|---|---|
| **单一股票** | **>5%** | **>15%** |
| **单一板块** | **>20%** | **>35%** |
| 单一国家 | >60% | >80% |
| **ETF 重叠** | >30% | >60% |
| 单一发行人 | >5% | >10% |

**常见经验法则**：

- "单一持仓超过组合 **10%** 一般即视为集中"
- "单一板块不应超过 **25–30%**"
- "板块集中度超过 **25%** 与单股集中同样危险"
- "如果前 5 大持仓占比超过 **40%**，可能存在危险的集中风险"

### 再平衡阈值 —— 5/25 规则

**William Bernstein 提出，业界最通用的漂移触发规则**：

> 当某个资产类别**绝对偏离 5 个百分点**，或**相对目标权重偏离 25%**，两者取先到者，即触发再平衡。

例：目标配置债券 20%
- 升到 **25%**（绝对 +5 个点）→ 触发
- 跌到 **15%**（相对 −25%）→ 触发

**配套惯例**：
- 一般再平衡容忍带：**±5%**
- 多数被动投资者每年**基于漂移触发 3–5 次**再平衡，而非固定按月

### 价格类告警阈值

- 常见的"重大下跌"线：**单日下跌 >10%**
- 监控频率惯例：
  - **每日** —— 重大市场事件与告警
  - **每周** —— 个股表现与新闻（15–20 分钟）
  - **每月** —— 详细指标分析（1–2 小时）
  - **每季** —— 全面复盘（2–3 小时）

---

## 六、AI Agent 时代的关键差异：**重要性判断** ⭐⭐

这是调研里最重要的一条洞察，直接对应作业的核心考点。

传统告警产品的问题是**告警疲劳**——规则触发就推，用户很快关掉通知。

而 AI Agent 类产品的**核心技能被明确定义为「对重要性的判断」**：

> **同一周内三个不同内部人在公开市场卖出**，和**一位高管行权**，是完全不同的事实；
> **一家机构下调评级**，和**两天内四家同时下调**，也是完全不同的事实。

**这就是"什么算噪音"的业界答案：不是看事件类型，而是看事件的模式、密度和一致性。**

### 可复用的重要性判断维度

| 维度 | 例子 |
|---|---|
| **数量与密度** | 1 个内部人卖 vs 3 个内部人同周卖 |
| **一致性** | 1 家下调 vs 4 家两天内同向下调 |
| **交易性质** | 公开市场卖出 vs 期权行权（后者常是例行的） |
| **时间聚集** | 分散发生 vs 集中爆发 |
| **相对历史** | 这个频率在这只票上是否罕见 |

**这一层是纯规则做不到、必须用 LLM 的地方**——也正是 alpi 该介入的位置。

---

## 七、对 Portfolio Watch Skill 的启示

### 业界标配（不做会显得不完整）

```
✅ 单一持仓权重 + 板块权重
✅ 最大回撤 · 波动率 · Beta
✅ 价格 / 百分比 / 均线 / 52周 四类基础告警
✅ 财报 · 分红 · 分析师动作 · 内部人交易
✅ 集中度告警（用上面那张阈值表）
✅ 配置漂移（5/25 规则）
```

### 业界有但 Alva 数据层给不了的（要明确声明不做）

| 项 | 原因 |
|---|---|
| **VaR / 压力测试** | 需要协方差矩阵和历史情景库，Alva 无 |
| **因子暴露**（growth/value/momentum） | 需要因子模型，Alva 无现成 |
| **Tracking Error** | 需要基准成分与权重 |
| **ETF 穿透重叠** | `etf-fundamentals` 有持仓数据，理论可做，但成本高 |
| **ESG** | 无数据 |
| **固定收益久期** | 无数据 |

### 差异化机会（业界普遍薄弱，Alva 恰好能做）

| 机会 | Alva 的支撑 |
|---|---|
| **重要性判断降噪** ⭐⭐⭐ | alpi + 官方的 `repetition_context` 结构 |
| **归因到市场/板块/个股三层** ⭐⭐ | `alva/company-move-attribution` 现成 |
| **主题敞口 + 事件映射** ⭐⭐ | 官方 `themeExposure` 带 `searchPhrase`，能捕捉"不点名但影响我"的事件 |
| **加密与股票统一视角** ⭐⭐ | 大部分产品二选一；Alva 两边数据都有 |
| **议员交易 / 暗池 / 做空数据** ⭐ | Arrays 有，零售产品几乎没有 |
| **预测市场概率** ⭐ | Polymarket 18 个端点，无人用于持仓监控 |

---

## 八、一个观察

把三层产品放在一起看，能看出一条清晰的演进：

```
机构级      算得准        因子模型 · VaR · 跟踪误差 —— 但要人去看
零售级      推得快        规则触发即推 —— 但会造成告警疲劳
AI Agent    判断得准 ⭐   全都检测，但只推重要的
```

**Portfolio Watch 作业考的是第三层。** 前两层的指标和告警类型都是公开知识、都能抄；**真正的区分度在"从 118 条候选里选出该说的那 1 条"的判断力**——以及把这个判断**说清楚、可审计、可复现**的能力。

---

## 信源

- [Portfolio Monitoring: Track Risk, Drift & Exposure — Guardfolio](https://www.guardfolio.ai/portfolio-monitoring)
- [How to Monitor Portfolio Performance: Metrics & Alerts — Guardfolio](https://www.guardfolio.ai/blog/portfolio-monitoring)
- [Portfolio Concentration Risk: How to Measure It — Guardfolio](https://www.guardfolio.ai/concentration-risk)
- [When to Rebalance Your Portfolio: 5/25 Rule + Drift Bands — Guardfolio](https://www.guardfolio.ai/blog/rebalancing)
- [PortfolioAnalyst Dashboard — IBKR Guides](https://www.ibkrguides.com/brokerportal/performanceandstatements/pa_viewingaccountperformance.htm)
- [Best Model Portfolio Tools for Financial Advisors — Koyfin](https://www.koyfin.com/blog/best-portfolio-management-software/)
- [Model Portfolios — Koyfin](https://www.koyfin.com/features/model-portfolios/)
- [Multi-Asset Class Factor Risk Modeling (MAC3) — Bloomberg](https://www.bloomberg.com/professional/products/risk/mac3)
- [Portfolio & Risk Analytics (PORT) — Bloomberg](https://data.bloomberglp.com/professional/sites/4/Portfolio_and_Risk_Analytics_Brochure4.pdf)
- [4 ways to use alerts when investing — Fidelity](https://www.fidelity.com/viewpoints/active-investor/4-ways-to-use-alerts)
- [Stock Price Alerts — 15+ Alert Types](https://pro.stockalarm.io/stock-price-alerts)
- [AI Agent for Stocks: What a Real Investing Agent Should Actually Do — Stock Alarm](https://pro.stockalarm.io/blog/ai-agent-for-stocks)
- [Best Stock Alert Apps 2026 — Guardfolio](https://www.guardfolio.ai/best-stock-alert-app)
- [Top 11 Crypto Trackers — CoinStats](https://coinstats.app/blog/best-crypto-portfolio-trackers/)
- [Crypto Whale Tracker — CoinCodex](https://coincodex.com/article/27175/crypto-whale-tracker/)
- [What is the 5/25 Rule — Brimco](https://www.brimco.io/terms/5-25-rule/)
