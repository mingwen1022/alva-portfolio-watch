# 判官逐条 · 每一层实际断言了什么

> ⚠️ **本文件由 `eval/build/gen_judges.py` 从判官代码生成，不要手写。**
> 断言分散在四个文件里，手写的清单会和代码分叉 —— 而分叉的方向恰好最坏:
> 文档说查了，代码没查。改了断言就重跑一次这个脚本。

**L0–L3 读的是产物文件**（Skill 跑完落在 Alva FS 上的那八个 JSON）,**L4 是真加载页面**（无头浏览器，查渲染出来的 DOM 与页面上印的数字）,**L5 是子 agent 判文字**（见文末）。

⚠️ **不是二元的，是三态。** 每条断言的结局有三种:跑了通过 · 跑了失败 · **断言的对象不存在所以没求值**。第三种单独报（代码里是 `M()` 不是 `A()`）—— 折进第一种的话，一份空产物会被报成「全过」，这个坑本项目踩过。

## L0 · 结构与内容

八个必需文件在不在、能不能解析，以及**该有值的地方是不是空的**。空值和缺字段是两回事 —— 前者页面渲染成破折号，看起来像上游没给数，排查会被带去错误的一层。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨sym⟩ spark 非空 | `symbols/<SYM>.json` → `spark`。持仓表每行右侧那条迷你走势图的数据。空了整行看起来像这只票没有行情。 | [`eval/judges/assertions.py:86`](assertions.py#L86) |
| 2 | ⟨sym⟩ kline 非空 | `symbols/<SYM>.json` → `kline`。Tab 2 的蜡烛图。空了二级页是一张白图。 | [`eval/judges/assertions.py:94`](assertions.py#L94) |
| 3 | 有持仓就有 scan 读数 | `findings.json` → `scan[]`。持仓表「告警依据」那六列全从它取数。空了六列一起变破折号，看起来像上游没给。 | [`eval/judges/assertions.py:118`](assertions.py#L118) |
| 4 | ⟨fn⟩ 存在且能解析 | 八个必需产物文件本身在不在 —— portfolio · series · baselines · findings · news · signals · market · meta。 | [`eval/judges/assertions.py:72`](assertions.py#L72) |
| 5 | ⟨sym⟩ kline 每根都有 OHLC | `symbols/<SYM>.json` → `kline[].o/h/l/c`。缺一根，蜡烛图那一天画不出实体。 | [`eval/judges/assertions.py:96`](assertions.py#L96) |
| 6 | ⟨sym⟩ kline 日期递增且不重复 | `symbols/<SYM>.json` → `kline[].d`。重复日期会在 x 轴上叠出两根同日蜡烛。 | [`eval/judges/assertions.py:100`](assertions.py#L100) |
| 7 | scan 覆盖每一只持仓 | `findings.json` → `scan[].symbol` 对 `portfolio.json` → `holdings[].symbol`。少一只 = 那只票今天根本没被扫过，而页面上它只是安静地待着。 | [`eval/judges/assertions.py:122`](assertions.py#L122) |
| 8 | freshness 五个键齐 = 四个 producer 都跑过 | `meta.json` → `freshness`。**这是全套断言里唯一能证明四个 cronjob 真的跑过的一条** —— 五个键分别由日线 · 盘中 · 新闻 · 财报 · 行情写下。缺哪个就是那一路没落地。 | [`eval/judges/assertions.py:146`](assertions.py#L146) |
| 9 | ⟨fn⟩ 能解析 | 产物文件是不是合法 JSON。解析不了与内容为空是两回事，排查会去到不同的层。 | [`eval/judges/assertions.py:77`](assertions.py#L77) |
| 10 | ⟨sym⟩ range52w 区间成立 | `symbols/<SYM>.json` → `range52w`。要求 low ≤ 现价 ≤ high。这三个点画在区间轴上，顺序错了肉眼看不出来。 | [`eval/judges/assertions.py:104`](assertions.py#L104) |
| 11 | ⟨f['id']⟩ 触发时刻不晚于 generatedAt | `findings.json` → `findings[].triggeredAt` 对 `meta.json` → `generatedAt`。这一轮的产物里不能出现还没发生的事。加密 24 小时交易、美股钉在收盘，两个时钟混用就会撞上这条。 | [`eval/judges/assertions.py:163`](assertions.py#L163) |

## L1 · 白名单

`signalId` 只能来自 `signals.json` 的 13 条；证据等级被证伪（red）的不得出现。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ signalId 在 signals.json 里 | `findings.json` → `findings[].signalId` 必须是 `signals.json` 里定义过的那 13 条之一。凭空出现的 ID 页面渲染不出名字与文案。 | [`eval/judges/assertions.py:185`](assertions.py#L185) |
| 2 | ⟨f['id']⟩ evidence ≠ red | `signals.json` → 该信号的 `evidence`。被回测证伪的信号不得出现在告警流里。 | [`eval/judges/assertions.py:186`](assertions.py#L186) |

## L2 · 参数

阈值来源必须在枚举内；兜底反解（`fallback_solved`）的标的证据等级不得显示为绿 —— 阈值是解出来的，不是验证过的。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨s⟩ thresholdSource 在枚举内 | `baselines.json` → `<SYM>.thresholds.source`,只能是 validated / fallback_solved / user_set。 | [`eval/judges/assertions.py:192`](assertions.py#L192) |
| 2 | ⟨s⟩ 兜底标的证据等级不得为 green | 阈值靠反解兜底出来的标的，页面上不得显示成「已验证」—— 那个阈值是解出来的，不是在这只票上验过的。 | [`eval/judges/assertions.py:194`](assertions.py#L194) |

## L2账目 · 账目

持仓 + 现金 = 总额、权重和 + 现金占比 = 1、Σ 单只盈亏 = 总盈亏。连了账户就每只都要有 shares/avgCost/value，没连就整块不出。容限 0.02。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | 持仓 + 现金 = 总额 | `portfolio.json`:Σ`holdings[].value` + `cash` = `kpi.totalValue`,容限 0.02。对不上意味着页头那个总额和下面的明细是两笔账。 | [`eval/judges/assertions.py:203`](assertions.py#L203) |
| 2 | 权重和 + 现金占比 = 1 | `holdings[].weight` 之和加上现金占比必须为 1。 | [`eval/judges/assertions.py:204`](assertions.py#L204) |
| 3 | 连了账户则每只都有 shares/avgCost/value | 连了券商账户就不能有半只票缺字段 —— 缺了那一行的盈亏列会静默变成破折号。 | [`eval/judges/assertions.py:216`](assertions.py#L216) |
| 4 | Σ lifetimePnl = totalPnl.abs | Σ`holdings[].lifetimePnl` = `kpi.totalPnl`。 | [`eval/judges/assertions.py:206`](assertions.py#L206) |
| 5 | ⟨h['symbol']⟩ lifetimePnl = 市值 − 成本 | 逐只核 `lifetimePnl` = `value` − `shares`×`avgCost`。总额对得上而单只对不上，是两个错互相抵消。 | [`eval/judges/assertions.py:222`](assertions.py#L222) |
| 6 | 连了账户时权重按市值而非等权 | 连了账户还给等权，说明权重根本没按持仓算 —— 配置饼图会全错。 | [`eval/judges/assertions.py:229`](assertions.py#L229) |
| 7 | 连了账户则净值曲线非空 | `series.json`。Tab 1 的净值曲线，空了那张图是白的。 | [`eval/judges/assertions.py:238`](assertions.py#L238) |

## L3同源 · 跨文件 · 同源

同一个事实在两个文件里必须相等 —— 历史触发次数 vs 告警历史条数。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨s⟩ historicalTriggers.⟨k⟩ = alertHistory 条数 | `baselines.json` → `historicalTriggers` 对 `symbols/<SYM>.json` → `alertHistory`。同一个事实存在两个文件里，必须相等。K 线上的历史标记画的是后者，卡片上的次数印的是前者。 | [`eval/judges/assertions.py:271`](assertions.py#L271) |

## L3基准 · 跨文件 · 基准

benchmark 两支形状必须一致，不适用时三个值同时为 null。一个键两种形状，下一个读它的人会挑错一支。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ benchmark 形状固定 | `findings[].context.benchmark` 两支必须同形。一个键两种形状，下一个读它的人会挑错一支。 | [`eval/judges/assertions.py:324`](assertions.py#L324) |
| 2 | ⟨f['id']⟩ 不适用时三个值为 null | 基准不适用（如加密无市场基准）时，三个值要一起为 null,不能一半有值一半没有。 | [`eval/judges/assertions.py:327`](assertions.py#L327) |

## L3归因 · 跨文件 · 归因

`timing` 要等于纯函数重算的结果、`origin` 在枚举内、url 可解析；用户线与财报日历**从不做归因** —— 它们自带原因。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ timing 等于纯函数 | `findings[].context.attribution.timing` 必须等于用发布时刻与触发时刻重算的结果 —— 它是算出来的，不许 LLM 自己填。 | [`eval/judges/assertions.py:355`](assertions.py#L355) |
| 2 | ⟨f['id']⟩ origin 枚举 | 归因来源 `sources[].origin` 只能取约定的几个值。 | [`eval/judges/assertions.py:356`](assertions.py#L356) |
| 3 | ⟨f['id']⟩ 用户线/EV4 无归因内容 | 用户线与财报日历**从不做归因** —— 它们自带原因（用户自己设的线 / 日历上的日子）。给它们配一段 LLM 解释是在编。 | [`eval/judges/assertions.py:334`](assertions.py#L334) |
| 4 | ⟨f['id']⟩ url 可解析 | `sources[].url` 要能解析成合法 URL,否则卡片上那个链接点了是死的。 | [`eval/judges/assertions.py:359`](assertions.py#L359) |
| 5 | ⟨f['id']⟩ timing=none 时不得有 model 署名 | 没做归因就不能署模型名 —— 署了就是把「没问过」显示成「模型说的」。 | [`eval/judges/assertions.py:361`](assertions.py#L361) |
| 6 | ⟨f['id']⟩ summary 里不得出现时刻 | 归因正文里不许出现具体时刻。数据里的时刻有多个时钟（收盘 · 取数 · 发布），LLM 挑哪个都可能挑错。 | [`eval/judges/assertions.py:363`](assertions.py#L363) |

## L3投递 · 跨文件 · 投递

每条 finding 都要有 `delivery`；level 必须是三道上限里最严的那个；`cappedBy` 指向的那一处**确实等于** level —— 否则理由和结果对不上。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ 有 delivery | `findings[].delivery`。没有它页面不知道这条该进推送还是只进记录页。 | [`eval/judges/assertions.py:305`](assertions.py#L305) |
| 2 | ⟨f['id']⟩ level = 三处上限的 max | 投递层级必须是三道上限（标的等级 · 降级标记 · 信号证据）里**最严**的那个。这条规则曾在管线 · 页面自检 · eval 三处各写一份且互不相同,后果是三条用户亲手设的止损被拦在手机之外。 | [`eval/judges/assertions.py:315`](assertions.py#L315) |
| 3 | ⟨f['id']⟩ cappedBy 指向的那一处确实等于 level | `cappedBy` 说是被哪一道拦的，那一道的值就必须等于最终 level —— 否则理由和结果对不上。 | [`eval/judges/assertions.py:317`](assertions.py#L317) |

## L3自洽 · 跨文件 · 自洽

基线不足 60 日时不得有名次；证据等级不是绿也不是「不适用」时，不得可推送。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ 基线 <60 时无 sizeRank | 基线不足 60 个交易日就算不出分位，此时不得给「今天排第几大」。 | [`eval/judges/assertions.py:295`](assertions.py#L295) |
| 2 | ⟨f['id']⟩ evidence≠green/na 时不得 pushable | 证据等级不是绿、也不是「不适用」的信号，不得推到手机上。 | [`eval/judges/assertions.py:299`](assertions.py#L299) |

## L3覆盖 · 跨文件 · 覆盖

scan 集合必须等于持仓集合 —— 少一只就是那只票今天根本没被扫过，而页面上它只是安静地待着。触发了的标的，对应粒度的 scan 必须是 `triggered`。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | scan 集合 = 持仓集合 | 两个集合必须逐只相等,多一只少一只都算不过。 | [`eval/judges/assertions.py:275`](assertions.py#L275) |
| 2 | ⟨f['symbol']⟩ ⟨f['signalId']⟩(⟨f['unit']⟩) 对应粒度的 scan 应为 triggered | 出了 finding，对应粒度那一行的 scan 状态就必须是 triggered —— 「告警响了」和「扫描说安静」不能同时成立。 | [`eval/judges/assertions.py:288`](assertions.py#L288) |
| 3 | ⟨x['symbol']⟩ 基线不足时 price/volume 为 null | 基线算不出来时读数要给 null 而不是 0 —— 0 会被渲染成一个真实的读数。 | [`eval/judges/assertions.py:280`](assertions.py#L280) |

## L3量纲 · 跨文件 · 量纲

`unit` 与信号必须对上（PV1=session · PV5=bar），(unit, 资产类别) 要有对应的 θ；线值只存一处，findings 里不得另存一份。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | ⟨f['id']⟩ findings 内不得另存线值 | 阈值线只存在 `baselines.json` 一处,finding 里不得再存一份副本。 | [`eval/judges/assertions.py:259`](assertions.py#L259) |
| 2 | ⟨f['id']⟩ PV1 必须是 session | `findings[].unit`。日线信号的粒度只能是 session。 | [`eval/judges/assertions.py:250`](assertions.py#L250) |
| 3 | ⟨f['id']⟩ PV5 必须是 bar | 盘中信号的粒度只能是 bar。 | [`eval/judges/assertions.py:251`](assertions.py#L251) |
| 4 | ⟨f['id']⟩ (unit,资产类别) 有对应 θz | 该粒度 × 该资产类别必须能在 `baselines.json` 里找到对应阈值,找不到说明这条信号根本不该在这只标的上产出。 | [`eval/judges/assertions.py:255`](assertions.py#L255) |
| 5 | ⟨f['id']⟩ |z| ≥ θz(⟨need⟩) | finding 记的读数必须真的过线。这条查的是「它凭什么算触发」。 | [`eval/judges/assertions.py:258`](assertions.py#L258) |

## L4 · 渲染

无头浏览器真加载一遍：零未捕获异常、无 404、四个 tab 的卡片都有正文、页面文本里没有 NaN / undefined / [object Object]、**页面上印的数字与产物里的值逐个对得上**。

| # | 断言 | 说明 · 查的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | 页面加载与四个 tab 全部点过之后,零未捕获异常 | 把 `mock/` 那份页面配上本轮产物真加载一遍，四个 tab 逐个点过，控制台不许有未捕获异常。 | [`eval/judges/l4_render.js:217`](l4_render.js#L217) |
| 2 | 没有 404 | 页面请求的资源全部要能取到。 | [`eval/judges/l4_render.js:219`](l4_render.js#L219) |
| 3 | 页面文本里没有 NaN / null / undefined / [object Object] | 渲染出来的文字里不许出现这几个词 —— 它们是「某个字段没给值」漏到了用户眼前。 | [`eval/judges/l4_render.js:264`](l4_render.js#L264) |
| 4 | 告警弹窗里没有 NaN / null / undefined / [object Object] | 同上，但要把每一条告警的弹窗逐个打开再查 —— 弹窗里的内容不打开就扫不到。 | [`eval/judges/l4_render.js:303`](l4_render.js#L303) |
| 5 | ${sym} 页面上印的基线天数 == baselines 里的值 | 页面上印的数字与产物里的值逐个对得上。渲染层自己算一遍再显示是常见的分叉点。 | [`eval/judges/l4_render.js:322`](l4_render.js#L322) |
| 6 | ${pid} 卡片数 == ${PANELS[pid]} | 每个 tab 该有几张卡就是几张,少一张说明有一类内容整块没渲染。 | [`eval/judges/l4_render.js:368`](l4_render.js#L368) |
| 7 | ${pid} 每张可见的卡都有正文 | 卡片壳子在、里面是空的，看起来像「今天没事」,实际是没渲染出来。 | [`eval/judges/l4_render.js:378`](l4_render.js#L378) |

## L5 · 说的话站不站得住（子 agent 判）

上面四层查的是**结构与数值**,能用等式表达。L5 查的是**文字**:一段解释有没有来源支撑、一个缺口说没说清、安静的一天有没有被说成「什么都没发生」。这类问题没有等式，所以交给一个**跑在本机的子 agent** 逐题判,而不是写进 `assertions.py`。

| # | 题目 | 说明 · 判的是哪个文件里的什么 | 出处 |
|---|---|---|---|
| 1 | 这段解释站得住吗 | `findings.json` → `findings[].context.attribution.summary`。**只抽真的做过归因的**（`generatedAt` 非空）—— 「没问过」不是判断题，混进来会让通过率被一堆空卡稀释。「问过了没找到」（summary 为 null）也不判，但要记进 skipped,否则「一条都没判」和「判了都过」在报告里长得一样。 | [`eval/judges/l5_extract.py:38`](judges/l5_extract.py#L38) |
| 2 | 这些缺口说清楚了吗 | `meta.json` → `gaps[]`。判的是它说没说清**缺的是什么**,还是只说了「没有」。用户看到「暂无数据」和看到「这个端点只覆盖 2025-08 之后」,能做的判断完全不同。 | [`eval/judges/l5_extract.py:68`](judges/l5_extract.py#L68) |
| 3 | 安静态表达得对吗 | `findings.json` → `scan[].state`。一天没有告警是**正常结局**,不是空页面。判的是页面有没有把「都在阈值内」表达成「什么都没发生」。 | [`eval/judges/l5_extract.py:77`](judges/l5_extract.py#L77) |

**判决是全票制:任一角度 fail 即 fail,并且记下是哪个角度**（[`l5_collect.py`](judges/l5_collect.py)）。为什么不用多数决,见 [PLAN.md §五](PLAN.md)。

---

共 **51** 条可求值断言（L0–L4）+ L5 的 3 类判断题,覆盖 13 层。

## 定时任务覆盖到什么程度

**这套判官判的是「一次建库跑完之后产物长什么样」,不是「它此后每天还对不对」。**

四个 cronjob 确实被走到了 —— agent 建完库它们就开始跑,`collect.py` 抓产物时抓到的已经是「init 的输出 + 首轮 cronjob 的输出」。但整套断言里**只有 L0 第 8 条**（`freshness` 五个键齐）能证明它们真的跑过,而它只证明「各跑过至少一次」。

没有任何断言在查:cron 表达式对不对 · `run_count` 有没有按时 +1 · 第二天第三天的那几轮还对不对 · 加密在周末推不推进。这些靠每日人工核查,不在 eval 里。

⚠️ `collect.py` 还记了一个 `settled` 标记（五个 freshness 键是否齐全）,那是**给读报告的人看的警告**,不是判官的断言 —— 抓早了会把「还没跑完」拍成「没做」,2026-08-23 就这么误判过一次 BC24。

---

⚠️ **「求值过」不等于「通过」。** 判官报三种结局:跑了通过 · 跑了失败 · **断言的对象不存在所以没求值**。第三种被折进第一种的话，一份空产物会被报成「全过」—— 这个坑本项目踩过（见 [badcases.md](badcases.md) 里判官自己的那几条）。