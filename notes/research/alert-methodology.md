# 告警方法论调研 — 股票 · 加密 · 告警工程

> 与前两份的分工：
> - `industry-dashboard.md` → 看板与指标（展示层）
> - `platform-capability.md` → Alva 平台能力（数据层）
> - **本文 → 告警本身**：什么触发、什么阈值、什么算强信号、怎么不吵到人
>
> 前提判断：这个 Skill 的核心是**告警决策**。作业里三个"由你的 Skill 决定"——
> 什么算异动、什么是噪音、多信号怎么排序——**全部是告警问题**，界面只是它的显示面。

---

## 一、股票告警

### 1.1 成交量：RVOL 是业界通用尺

**RVOL（相对成交量）= 当前成交量 ÷ N 期平均成交量**

| 阈值 | 含义 | 用途 |
|---|---|---|
| **1.5** | 关注度抬升 | 快速剥头皮 |
| **2.0** | 值得监控的异常 | 日内动量交易 |
| **3.0+** | **通常意味着重大催化剂** | 高确信突破 |

**业界常用的组合筛选**（不是单条件）：

```
RVOL > 2.0  且  价格在 52 周高点 5% 以内  且  日均量 > 50 万股
```

⚠️ **关键实现细节**：RVOL **必须按时段归一化**——盘前比开盘安静，午盘比收盘慢。
拿全天平均量去比盘中某一时刻是错的。

> 这与 Alva 官方异动检测的做法一致：*"今日**同时段**累计量 vs 前 90 日基准"*。

### 1.2 内部人交易：区分「买入」与「行权」是关键 ⭐

**Form 4 交易代码**（这是信号质量的分水岭）：

| 代码 | 含义 | 信号价值 |
|---|---|---|
| **P** | **公开市场买入** | ⭐ **最干净的信号** |
| S | 卖出 | 中等（卖出原因很多：交税、分散、买房） |
| A | 授予 | ❌ 无信号（薪酬） |
| M | **期权行权 / 转换** | ❌ **无信号**（拿既定报酬） |

> *"研究若过滤到交易代码 P、排除期权行权、薪酬授予和 10b5-1 计划交易，结果一致强于使用未过滤 Form 4 数据的研究。"*

**这直接验证了我们前面说的**：3 位内部人同周公开市场卖出 ≠ 1 位高管行权。业界不只是"感觉不同"，是**有代码级的区分标准**。

### 1.3 内部人「簇买」：有量化的超额收益证据

| 结论 | 数字 |
|---|---|
| **簇买**（多位内部人短窗口内买入） | 历史预示 **6–12 个月 4–8% 超额收益** |
| Cohen / Malloy / Pomorski (2012, *Journal of Finance*) | 区分 routine vs **opportunistic** 交易，opportunistic 买入 **6 个月 alpha ≈ 5.2%** |

> *"聚集与簇状的内部人买入比孤立交易携带更多预测内容，**因为它更难被解释掉**。"*

**「更难被解释掉」是判断信号强度的通用心法**——一个人卖有一百种理由，三个人同周卖只有一种。

### 1.4 分析师动作：看变动方向 + 看簇

| 发现 | 说明 |
|---|---|
| **预测力在「变动方向」而非「绝对评级」** | 升级/降级比"当前是买入还是持有"更有信息量 |
| **30 天窗口内的簇远比孤立修订有意义** | 多家同向 ≫ 单家 |
| **估值修订 > 评级标签** | 修订直接反映预期变化，评级只是标签 |
| **滚动 30–90 天净升降级数** | 边际情绪信号 |

**因果链**：正向盈利意外 → 数日至数周内上修 → 形成正循环；负向意外 → **降级级联**，放大下行。

---

## 二、加密告警

加密的特殊性：**衍生品数据是公开的、连续的、且直接反映杠杆情绪**——这是股票没有的。

### 2.1 三个核心指标构成一个反身性回路 ⭐

```
未平仓量（OI）  →  堆积杠杆
      ↓
资金费率        →  揭示杠杆的方向偏好
      ↓
爆仓            →  杠杆不可持续时的重置机制
      ↓
（回到 OI）
```

**理解这个回路，比单看任一指标有用得多。**

### 2.2 具体阈值（业界在用的数字）

| 指标 | 阈值 | 含义 |
|---|---|---|
| **资金费率** | **> 0.05% / 小时** | 过度杠杆，**爆仓级联的前兆** |
| | **> 0.0182%**（8h） | 动量转变信号（中性值约 0.01% 的 1.8 倍） |
| | 年化 > +40% 或 < −20% | 常见的自定义告警配置 |
| **未平仓量** | **> $300 亿**（BTC 期货） | 机构定位、方向性确信 |
| | 高 OI 环境 | **拥挤交易**，市场对小冲击高度敏感 |
| **爆仓** | **> $5 亿**（回调期间） | 过度杠杆定位，标记关键支撑阻力 |

**一个实测案例**：某时点 10% 价格波动窗口内，约 **$81.2 亿空头** 与 **$68.6 亿多头** 面临爆仓风险——这种极端失衡 + 密集爆仓热力图，预示波动与潜在拐点。

### 2.3 对我们的启示

我们 mock 里那条 BTC 信号（*"资金费率转负、未平仓 24h 下降 6.2%"*）**方向是对的**，但缺一个量化锚：

```
❌ 现在：  "资金费率由正转负"                    —— 没说是否达到有意义的幅度
✅ 应该：  "资金费率 −0.021%/8h，跌破中性值      —— 有绝对参照
           且为近 30 日首次"                     —— 有历史参照
```

---

## 三、信号质量：业界怎么判断「强」

从三块研究里提炼出的**通用判据**——这套心法比任何单一阈值都重要：

| # | 判据 | 股票例 | 加密例 |
|---|---|---|---|
| **1** | **难被解释掉** | 3 人同周公开市场买 vs 1 人行权 | 资金费率+OI+价格三者同向 |
| **2** | **簇 > 孤立** | 30 天内 4 家降级 vs 1 家 | 多交易所资金费率同时转向 |
| **3** | **变动 > 水平** | 评级升降 vs 当前评级 | 费率变化率 vs 费率绝对值 |
| **4** | **交叉确认** | 价格异动 + 放量 + 可归因 | 价格 + OI + 爆仓 |
| **5** | **相对自身历史** | RVOL 按时段归一 | 费率 vs 该币近 30 日分布 |

**第 1 条是总纲**：一个信号的强度，取决于**它有多少种无害的解释**。解释越少，信号越强。

---

## 四、告警工程 ⭐ 这块金融产品普遍落后

运维监控行业解决「告警疲劳」已经二十多年，方法论完全成熟。
而金融告警产品**大多还停留在"规则触发即推"**——这是最大的可迁移机会。

### 4.1 严重度分级：只有最高级才打断人

```
Critical      → 打断（推送到手机）
Warning       → 路由到看板
Informational → 排队等业务时段 / 只进报告
```

> *"确保只有 critical 告警会吵醒人，其余应路由到看板或排入业务时段队列。"*

**关键**：不是二元的"推 / 不推"，而是**多档阈值 + 多个投递渠道**。

**映射到我们**：

| 我们的告警 | 建议档位 |
|---|---|
| 止损/止盈线跨越 | **Critical** → 立即推送 |
| 价格异动 + 放量 + 可归因 | **Critical** |
| 集中度突破高风险线 | Warning → 界面高亮，日报汇总 |
| 分析师单家动作 | Informational → 只进记录页 |
| 主题共振 | Warning |

> 现在我们只有"推 / 不推"两档，**丢掉了中间态**。而中间态恰恰是最多的。

### 4.2 去重窗口按优先级分层

| 优先级 | 去重窗口 |
|---|---|
| 高 | **1–2 分钟** |
| 中 | **3–5 分钟** |
| 低 | **10–15 分钟** |

**核心规则**：*"当同一条件在没有实质状态变化的情况下再次触发，系统应更新已有告警，而不是发送新通知。"*

**这正是 Alva `anomalyEpisodeId` 的设计意图**——同一 episode 的延续更新状态，不重复推送。

### 4.3 抑制的四个合法理由

```
① 维护窗口        → 金融场景对应：非交易时段、数据源已知延迟
② 优先级过滤      → 低于阈值的不推
③ 去重规则        → 同一件事已推过
④ 时间条件        → 用户设的静默时段
```

### 4.4 富化（Enrichment）：让人不用翻日志就知道该干什么

> *"Enrichment 添加上下文，让工程师无需翻查日志就知道该做什么。"*

**映射到我们**：每条告警必须自带

```
发生了什么 · 对你的仓位意味着什么 · 接下来看什么
```

—— 这正是我们信号卡片的四段式。**业界把它叫 enrichment，是有名字的成熟实践。**

---

## 五、宏观与政策/言论告警 ⭐ 前版缺失

前一版阈值表完全没有这两类，是明显缺口。而它们的**性质完全不同**，必须分开设计：

```
宏观日历型    时间已知  →  可以提前预警 + 事后对照      例：NFP · CPI · FOMC
政策言论型    不可预期  →  只能事后响应，噪音极大        例：关税表态 · 地缘冲突
```

---

### 5.1 宏观日历型

#### Tier-1 高影响事件（业界公认）

> *"最大的市场推动者是月度就业报告（非农）、CPI 通胀、FOMC 利率决议、PCE 物价指数和 GDP，
> **相对预期的意外**驱动利率与风险资产的最大波动。"*

| 事件 | 频率 | 时间 |
|---|---|---|
| **非农（NFP）** | 月 | 每月第一个周五 |
| **CPI** | 月 | — |
| **FOMC 决议** | 约 8 次/年 | — |
| **PCE** | 月 | — |
| **GDP** | 季 | — |

#### 关键设计：不是每个数据都该推给每个人

**必须按持仓敏感度过滤。** 这是本 Skill 要定的方法论：

| 宏观指标 | 谁敏感 | 传导逻辑 |
|---|---|---|
| **CPI / PCE** | 成长股 · 长久期资产 · **加密** | 通胀 → 利率预期 → 贴现率 |
| **FOMC** | 全市场，尤其高 beta | 直接定价 |
| **NFP** | 整体风险偏好 · 周期股 | 就业 → 经济强度 → 政策路径 |
| **GDP** | 周期股 · 大宗 | — |

> 示例组合 NVDA / TSLA / BTC 全是高 beta 风险资产 → 对 **FOMC 与 CPI 高度敏感**，
> 对 GDP 敏感度低 → GDP 发布不该打扰这个用户。

#### 三段式告警

```
T−1 日      预告：明天 CPI 发布，你 76% 的持仓属利率敏感资产      Warning
发布瞬间    实际值偏离                                          Critical
事后        你的持仓实际反应 vs 同类资产                          Informational
```

#### ⚠️ 一个数据缺口要诚实标注

Arrays 的 `macro-and-economics` 提供**实际值与发布日期**，
但**没有明确的 consensus（市场共识预期）端点**。

这意味着：

| 能做 | 做不了 |
|---|---|
| ✅ 发布日历预警（T−1 / T−3） | ❌ 严格意义的「意外度」= 实际 vs 共识 |
| ✅ 实际值 vs **前值** 的偏离 | |
| ✅ 实际值 vs **12 月均值** 的 z 分数 | |

**替代方案**：用「vs 前值 / vs 滚动均值」代替「vs 共识」，并在方法页写明这一口径差异。

---

### 5.2 政策 / 言论型

#### 这已经是被市场定价的一等信号

2026 年 7 月，**Trump Media 开始向华尔街出售 Truth Social 帖子的低延迟访问权**，
官方理由就是 —— *"markets already move on Truth Social posts"*。

关税言论的累计市值影响（可量化的实证）：

```
标普 500      −$4.7 万亿
Mag7          −$2 万亿
罗素 2000     −$3,770 亿
```

其对美伊战争的表态也曾多次推动油价大幅波动。

**所以这不是"要不要做"的问题，是"怎么在噪音里挑出那几条"的问题。**

#### 数据源

| 来源 | 能力 |
|---|---|
| `alva/query-breaking-news-feed` | 官方策展的**宏观与跨市场突发流**，可按 recency / topic / ticker 查询 |
| `arrays-data-api-social-feeds` | 追踪账号帖子 · 全文检索 · **可动态新增追踪 handle** ⭐ |

第二条很关键：**social-feeds 支持「start tracking a new handle」** —— 意味着可以按需把特定政治账号加入追踪列表。

#### 三重过滤 ⭐ 这是本类告警的方法论核心

政治言论是噪音之王 —— 每天几十条，绝大多数与市场无关。
**光靠 LLM 判断「这条重不重要」不可靠**，必须交叉确认：

```
① 主题命中     言论内容是否命中你持仓的主题 searchPhrase
               （关税 · 中国 · 半导体 · 加密监管 · 能源…）
                        ↓
② 市场确认 ⭐  发布后 N 分钟内是否出现对应的价格 / 成交量反应
                        ↓
③ 新颖度       是新表态，还是重复既有立场
```

**第 ② 条是设计的关键**：用**市场自己的反应**来验证言论的重要性，
而不是让 LLM 判断"这句话听起来重不重要"。

这符合前文提炼的信号强度总纲第 4 条 —— **交叉确认**。

#### 分级

| 条件 | 严重度 |
|---|---|
| 主题命中 **且** 市场确认 **且** 新颖 | **Critical** |
| 主题命中 **且** 新颖，但无市场反应 | Warning（进界面，不推送） |
| 仅主题命中（重复表态） | Informational |
| 无主题命中 | 抑制 |

> **「有言论但市场没反应」单独设一档很重要** —— 它既不该被丢掉（可能是滞后反应），
> 也不该打扰用户（可能就是没人在意）。

---

## 六、映射回我们的 15 个告警

### ✅ 有明确业界依据的（可直接引用阈值）

| 我们的告警 | 业界依据 |
|---|---|
| 成交量异动 | RVOL 2.0 / 3.0，**按时段归一化** |
| 内部人交易 | **Form 4 代码 P** + 簇买（6–12 月 4–8% 超额） |
| 分析师动作 | 30 天窗口簇 + 变动方向 > 绝对水平 |
| 资金费率 | **0.05%/h**（爆仓前兆）· **0.0182%**（动量转变） |
| 未平仓量 | 高 OI = 拥挤交易，对小冲击敏感 |
| 集中度 | 单股 5%/15% · 板块 20%/35%（前份调研） |
| 价格异动 | z / MAD 基线（Alva 官方 + 竞品） |

### ⚠️ 需要调整的

| 问题 | 调整 |
|---|---|
| **只有推/不推两档** | 加入 **Warning / Informational** 中间态，路由到界面而非推送 |
| **去重窗口没分层** | 按严重度分 1–2 / 3–5 / 10–15 分钟 |
| **内部人告警未区分代码** | 必须过滤到 **P**，排除 M / A / 10b5-1 |
| **BTC 资金费率信号缺量化锚** | 补上绝对阈值 + 历史分位 |
| **缺爆仓数据** | Arrays 无直接端点 → 声明为不支持，或用 OI 骤降近似 |

### ❌ 业界有但我们做不了（要在方法页声明）

```
爆仓热力图      Arrays 无爆仓端点
期权异动扫描    数据有但成本高，且个人难解读
13F 变动        季度滞后 45 天，不是"现在发生的事"
```

---

## 七、建议的阈值表（可直接写进 SKILL.md）

### 股票

| 信号 | 触发 | 严重度 |
|---|---|---|
| 价格异动 | MAD 基线偏离 ≥ 2σ 等效 **且** RVOL ≥ 2.0 **且** 可归因 | Critical |
| 成交量单独异常 | RVOL ≥ 3.0（无价格配合） | Warning |
| 内部人簇买 | ≥2 位内部人 · 30 天内 · **代码 P** | Critical |
| 内部人单笔 | 1 位 · 代码 P | Informational |
| 分析师簇 | ≥3 家同向 · 30 天内 | Critical |
| 分析师单家 | 1 家变动 | Informational |
| 财报临近 | T−3 交易日 | Warning |

### 加密

| 信号 | 触发 | 严重度 |
|---|---|---|
| 资金费率极端 | \|费率\| > 0.05%/h | Critical |
| 资金费率转向 | 跨越 0 **且** 为近 30 日首次 | Warning |
| OI 骤变 | 24h 变化 > ±10% | Warning |
| 代币解锁 | T−7 日 · 解锁量 > 流通量 3% | Critical |

### 宏观（按持仓敏感度过滤）

| 信号 | 触发 | 严重度 |
|---|---|---|
| Tier-1 数据发布预告 | T−1 日 **且** 持仓敏感度 ≥ 中 | Warning |
| Tier-1 实际值偏离 | vs 前值/12 月均值 z ≥ 1.5 | Critical |
| FOMC 决议 | 发布即触发（高 beta 持仓） | Critical |
| 低敏感度数据（如 GDP 对科技持仓） | — | 抑制 |

### 政策 / 言论

| 信号 | 触发 | 严重度 |
|---|---|---|
| 政策言论 | 主题命中 **且** 市场确认 **且** 新颖 | **Critical** |
| 政策言论 | 主题命中 **且** 新颖，无市场反应 | Warning |
| 政策言论 | 重复既有立场 | Informational |
| 突发地缘事件 | breaking-news 流命中持仓主题 | Warning |

### 组合层面

| 信号 | 触发 | 严重度 |
|---|---|---|
| 单股集中度 | > 15% | Warning · > 25% Critical |
| 主题集中度 | > 35% | Warning |
| 主题共振 | ≥2 标的映射同主题 **且** 合计 > 35% | Warning |
| 止损/止盈/回撤 | 用户设定值 | **Critical**（无门槛） |

---

## 八、备选方案：模型化增强（当前不启用）

> **本版本决定不建模型。** 本节记录评估过程与启用条件，供后续版本参考。

### 8.1 为什么不做

告警的三类难点里，只有一类适合建模：

| 难点 | 本质 | 谁最适合 |
|---|---|---|
| 「3 位内部人同周卖 vs 1 位行权」 | 规则问题 | 代码（Form 4 代码 P + 计数） |
| 「这条新闻和上次是不是同一件事」 | 语义问题 | **LLM（alpi）** |
| 「这次异动会不会持续」 | 数值预测 | ⭐ 模型 |

**前两类硬上 ML 是杀鸡用牛刀，效果反而更差。**

### 8.2 唯一值得考虑的方向：信号持续性预测

**标签可从 Alva 自己的数据自动构造，无需人工标注。**

`alva/company-anomaly-read` 的 `anomaly/timeline` 记录了每次 run 的
`isActiveAnomaly` 与 `anomalyEpisodeId` —— **每次异动持续多久是可直接算出的**。

**实测（NVDA，2026-08-08 至 08-19，900 行 timeline）**：

```
状态分布   skipped 541 · not_triggered 326 · continued_no_new_attribution 20
           new_anomaly 8 · continued_no_info 3 · continued_new_attribution 2

11 天内 8 个异动 episode
持续时长   中位 31 分钟 · 最短 0 · 最长 253
标签分布   持续 ≥60 分钟占 3/8 = 38%
```

**38% 的正类比例对二分类是健康分布。**

可用的特征（触发那一刻即可得，天然满足 point-in-time）：

```
priceZScore · volumeZScore · priceMovePct · priceMoveBasis
时段 · 资产类别 · 归因三层分解 · 是否伴随催化剂
```

产品价值：给告警加降级标记 —— 持续概率低的从 Critical 降到 Warning，
**正好填上「中间态」的缺口**。

### 8.3 为什么现在做不了

| 门槛 | 说明 |
|---|---|
| **样本量** | 单票 11 天仅 8 个 episode → 需 ~100–200 只票 × 数月 |
| **数据拉取** | 每票数千行 timeline，上百次 API 调用 |
| **验证要求** | walk-forward + **purge ≥ 标签 horizon**（60 分钟） |
| **契约要求** | `model_meta.json` 五块契约：模型身份 · 数据契约 · 输入契约 · 输出契约 · **验证证据**（含成本假设、漂移风险、重训周期） |
| **参照工作量** | `zal/high-vol-persistent-ranknet`：87 特征 · RankNet 成对训练 · 60 天滚动窗 · 72h purge · 14 天验证窗 · OOF 证据 —— **数周量级** |

### 8.4 启用条件（写进 SKILL.md）

```
何时引入模型
  当规则与 LLM 都无法可靠判断某类信号，且存在足量「可自动构造」的标签时

候选任务
  信号持续性预测 —— 标签从 anomaly/timeline 的 episode 生命周期自动构造

交付标准
  walk-forward + purge ≥ 标签 horizon
  样本外（OOF）证据
  完整 model_meta.json 五块契约
  离线 AUC ≥ 0.75 方可用于降级告警

当前状态
  未启用 —— 统计基线（MAD + 分位数归一化）已足够，
  模型收益不足以抵消验证成本与漂移风险
```

### 8.5 现阶段的替代：统计基线

不建 ML，但解决模型想解决的问题 —— **混合资产的阈值统一**：

| 方法 | 解决什么 |
|---|---|
| **MAD 稳健基线**（中位数绝对偏差） | 比标准差抗异常值；加密的肥尾分布下 z-score 会失真 |
| **分位数归一化** | BTC 的 3% 和 NVDA 的 3% 换算到各自历史分布的同一位置 |
| **同时段基准** | 盘前/盘中/盘后分别建基线，避免时段错配 |

**成本半天，可解释、可复现、无漂移风险。**

---

## 九、一句话总结

> 业界在**阈值**上早有共识（RVOL 2.0/3.0、资金费率 0.05%、集中度 5/15%），
> 在**信号质量**上早有研究（Form 4 代码 P、簇买 4–8% 超额、30 天分析师簇），
> 在**告警工程**上早有成熟方法（分级 / 分层去重 / 抑制 / 富化）。
>
> **金融告警产品普遍只用了第一层，第三层几乎无人迁移。**
> 而第三层恰恰是「什么是噪音」这道题的正解。

---

## 信源

- [Relative Volume (RVOL): Trading Indicator Guide — TradingSim](https://www.tradingsim.com/blog/relative-volume-rvol)
- [Relative Volume: How to Spot High-Momentum Trading Opportunities — Alphio](https://alphio.ai/blog/relative-volume-guide-2026)
- [Detect Stocks With Unusual and Relative Volume Activity — Trade Ideas](https://www.trade-ideas.com/help/filter.html?code=RV)
- [Cluster Buy Signals — Why Multiple Insiders Buying Together Matters — Form4API](https://www.form4api.com/guides/cluster-buy-signals)
- [Cluster insider buying: the signal single-buy screeners miss — Cutonce](https://www.cutonce.ai/blog/cluster-insider-buying-signal)
- [Insider Transactions Alert — StockAlert.pro](https://stockalert.pro/alerts/insider-transactions)
- [Trading Signals: Analyst Revisions & Earnings Surprises — Sigtrix](https://sigtrix.com/blog/trading-signals-analyst-revisions-earnings-surprises)
- [Predictability of Analyst Stock Recommendation Revisions — Bayes Business School](https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0009/681939/Flake_20220318.pdf)
- [Funding Rates in Crypto: The Hidden Cost, Sentiment Signal, and Strategy Trigger — Quant Journey](https://quantjourney.substack.com/p/funding-rates-in-crypto-the-hidden)
- [Bitcoin Futures Market Microstructure: Liquidation Cascades, Funding Regimes, and Open Interest Signals — XT Exchange](https://medium.com/@XT_com/bitcoin-futures-market-microstructure-liquidation-cascades-funding-regimes-and-open-interest-978b107b4889)
- [What are crypto derivatives market signals — Gate.com](https://www.gate.com/crypto-wiki/article/how-do-crypto-derivatives-market-signals-predict-price-movements-futures-open-interest-funding-rates-liquidation-data-long-short-ratio-and-options-explained-20260129)
- [Alert Suppression Best Practices: Reducing Noise Without Risk — Upstat](https://upstat.io/blog/alert-suppression-best-practices)
- [Monitoring and Alerting Best Practices to Reduce Alert Fatigue — OneUptime](https://oneuptime.com/blog/post/2026-02-20-monitoring-alerting-best-practices/view)
- [Trump Media to Sell Traders 'the Fastest' Access to Truth Social Posts — TIME](https://time.com/article/2026/07/17/truth-social-api-wall-street-trump-media/)
- [Equity Markets React To Trump's Tariff Announcements: The Data — Seeking Alpha](https://seekingalpha.com/article/4786044-equity-markets-react-to-trumps-tariff-announcements-the-data)
- [Economic Calendar 2026 – CPI, NFP, GDP, FOMC Release Dates — DataSetIQ](https://www.datasetiq.com/economic-calendar)
- [United States Nonfarm Payrolls — FXStreet Economic Calendar](https://www.fxstreet.com/economic-calendar/event/9cdf56fd-99e4-4026-aa99-2b6c0ca92811)
- [Alerting, Thresholds, and Notification Design — BlueGrid](https://bluegrid.io/guides/the-complete-guide-to-systems-monitoring-fundamentals/alerting-thresholds-and-notification-design-building-alerts-that-dont-burn-out-your-team/)
