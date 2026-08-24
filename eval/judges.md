# 判官逐条 · 每一层实际断言了什么

> ⚠️ **本文件由 `eval/build/gen_judges.py` 从判官代码生成，不要手写。**
> 断言分散在四个文件里，手写的清单会和代码分叉 —— 而分叉的方向恰好最坏:
> 文档说查了，代码没查。改了断言就重跑一次这个脚本。

L5 不在这里 —— 它是子 agent 判的「这句话站不站得住」，题目由 [`l5_extract.py`](l5_extract.py) 抽、判决由 [`l5_collect.py`](l5_collect.py) 收（全票制，任一角度 fail 即 fail）。为什么不用多数决，见 [PLAN.md §五](PLAN.md)。

## L0 · 结构与内容

八个必需文件在不在、能不能解析，以及**该有值的地方是不是空的**。空值和缺字段是两回事 —— 前者页面渲染成破折号，看起来像上游没给数，排查会被带去错误的一层。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨sym⟩ spark 非空 | [`eval/judges/assertions.py:86`](assertions.py#L86) |
| 2 | ⟨sym⟩ kline 非空 | [`eval/judges/assertions.py:94`](assertions.py#L94) |
| 3 | 有持仓就有 scan 读数 | [`eval/judges/assertions.py:118`](assertions.py#L118) |
| 4 | ⟨fn⟩ 存在且能解析 | [`eval/judges/assertions.py:72`](assertions.py#L72) |
| 5 | ⟨sym⟩ kline 每根都有 OHLC | [`eval/judges/assertions.py:96`](assertions.py#L96) |
| 6 | ⟨sym⟩ kline 日期递增且不重复 | [`eval/judges/assertions.py:100`](assertions.py#L100) |
| 7 | scan 覆盖每一只持仓 | [`eval/judges/assertions.py:122`](assertions.py#L122) |
| 8 | freshness 五个键齐 = 四个 producer 都跑过 | [`eval/judges/assertions.py:146`](assertions.py#L146) |
| 9 | ⟨fn⟩ 能解析 | [`eval/judges/assertions.py:77`](assertions.py#L77) |
| 10 | ⟨sym⟩ range52w 区间成立 | [`eval/judges/assertions.py:104`](assertions.py#L104) |
| 11 | ⟨f['id']⟩ 触发时刻不晚于 generatedAt | [`eval/judges/assertions.py:163`](assertions.py#L163) |

## L1 · 白名单

`signalId` 只能来自 `signals.json` 的 13 条；证据等级被证伪（red）的不得出现。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ signalId 在 signals.json 里 | [`eval/judges/assertions.py:185`](assertions.py#L185) |
| 2 | ⟨f['id']⟩ evidence ≠ red | [`eval/judges/assertions.py:186`](assertions.py#L186) |

## L2 · 参数

阈值来源必须在枚举内；兜底反解（`fallback_solved`）的标的证据等级不得显示为绿 —— 阈值是解出来的，不是验证过的。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨s⟩ thresholdSource 在枚举内 | [`eval/judges/assertions.py:192`](assertions.py#L192) |
| 2 | ⟨s⟩ 兜底标的证据等级不得为 green | [`eval/judges/assertions.py:194`](assertions.py#L194) |

## L2账目 · 账目

持仓 + 现金 = 总额、权重和 + 现金占比 = 1、Σ 单只盈亏 = 总盈亏。连了账户就每只都要有 shares/avgCost/value，没连就整块不出。容限 0.02。

| # | 断言 | 出处 |
|---|---|---|
| 1 | 持仓 + 现金 = 总额 | [`eval/judges/assertions.py:203`](assertions.py#L203) |
| 2 | 权重和 + 现金占比 = 1 | [`eval/judges/assertions.py:204`](assertions.py#L204) |
| 3 | 连了账户则每只都有 shares/avgCost/value | [`eval/judges/assertions.py:216`](assertions.py#L216) |
| 4 | Σ lifetimePnl = totalPnl.abs | [`eval/judges/assertions.py:206`](assertions.py#L206) |
| 5 | ⟨h['symbol']⟩ lifetimePnl = 市值 − 成本 | [`eval/judges/assertions.py:222`](assertions.py#L222) |
| 6 | 连了账户时权重按市值而非等权 | [`eval/judges/assertions.py:229`](assertions.py#L229) |
| 7 | 连了账户则净值曲线非空 | [`eval/judges/assertions.py:238`](assertions.py#L238) |

## L3同源 · 跨文件 · 同源

同一个事实在两个文件里必须相等 —— 历史触发次数 vs 告警历史条数。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨s⟩ historicalTriggers.⟨k⟩ = alertHistory 条数 | [`eval/judges/assertions.py:271`](assertions.py#L271) |

## L3基准 · 跨文件 · 基准

benchmark 两支形状必须一致，不适用时三个值同时为 null。一个键两种形状，下一个读它的人会挑错一支。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ benchmark 形状固定 | [`eval/judges/assertions.py:324`](assertions.py#L324) |
| 2 | ⟨f['id']⟩ 不适用时三个值为 null | [`eval/judges/assertions.py:327`](assertions.py#L327) |

## L3归因 · 跨文件 · 归因

`timing` 要等于纯函数重算的结果、`origin` 在枚举内、url 可解析；用户线与财报日历**从不做归因** —— 它们自带原因。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ timing 等于纯函数 | [`eval/judges/assertions.py:355`](assertions.py#L355) |
| 2 | ⟨f['id']⟩ origin 枚举 | [`eval/judges/assertions.py:356`](assertions.py#L356) |
| 3 | ⟨f['id']⟩ 用户线/EV4 无归因内容 | [`eval/judges/assertions.py:334`](assertions.py#L334) |
| 4 | ⟨f['id']⟩ url 可解析 | [`eval/judges/assertions.py:359`](assertions.py#L359) |
| 5 | ⟨f['id']⟩ timing=none 时不得有 model 署名 | [`eval/judges/assertions.py:361`](assertions.py#L361) |
| 6 | ⟨f['id']⟩ summary 里不得出现时刻 | [`eval/judges/assertions.py:363`](assertions.py#L363) |

## L3投递 · 跨文件 · 投递

每条 finding 都要有 `delivery`；level 必须是三道上限里最严的那个；`cappedBy` 指向的那一处**确实等于** level —— 否则理由和结果对不上。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ 有 delivery | [`eval/judges/assertions.py:305`](assertions.py#L305) |
| 2 | ⟨f['id']⟩ level = 三处上限的 max | [`eval/judges/assertions.py:315`](assertions.py#L315) |
| 3 | ⟨f['id']⟩ cappedBy 指向的那一处确实等于 level | [`eval/judges/assertions.py:317`](assertions.py#L317) |

## L3自洽 · 跨文件 · 自洽

基线不足 60 日时不得有名次；证据等级不是绿也不是「不适用」时，不得可推送。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ 基线 <60 时无 sizeRank | [`eval/judges/assertions.py:295`](assertions.py#L295) |
| 2 | ⟨f['id']⟩ evidence≠green/na 时不得 pushable | [`eval/judges/assertions.py:299`](assertions.py#L299) |

## L3覆盖 · 跨文件 · 覆盖

scan 集合必须等于持仓集合 —— 少一只就是那只票今天根本没被扫过，而页面上它只是安静地待着。触发了的标的，对应粒度的 scan 必须是 `triggered`。

| # | 断言 | 出处 |
|---|---|---|
| 1 | scan 集合 = 持仓集合 | [`eval/judges/assertions.py:275`](assertions.py#L275) |
| 2 | ⟨f['symbol']⟩ ⟨f['signalId']⟩(⟨f['unit']⟩) 对应粒度的 scan 应为 triggered | [`eval/judges/assertions.py:288`](assertions.py#L288) |
| 3 | ⟨x['symbol']⟩ 基线不足时 price/volume 为 null | [`eval/judges/assertions.py:280`](assertions.py#L280) |

## L3量纲 · 跨文件 · 量纲

`unit` 与信号必须对上（PV1=session · PV5=bar），(unit, 资产类别) 要有对应的 θ；线值只存一处，findings 里不得另存一份。

| # | 断言 | 出处 |
|---|---|---|
| 1 | ⟨f['id']⟩ findings 内不得另存线值 | [`eval/judges/assertions.py:259`](assertions.py#L259) |
| 2 | ⟨f['id']⟩ PV1 必须是 session | [`eval/judges/assertions.py:250`](assertions.py#L250) |
| 3 | ⟨f['id']⟩ PV5 必须是 bar | [`eval/judges/assertions.py:251`](assertions.py#L251) |
| 4 | ⟨f['id']⟩ (unit,资产类别) 有对应 θz | [`eval/judges/assertions.py:255`](assertions.py#L255) |
| 5 | ⟨f['id']⟩ |z| ≥ θz(⟨need⟩) | [`eval/judges/assertions.py:258`](assertions.py#L258) |

## L4 · 渲染

无头浏览器真加载一遍：零未捕获异常、无 404、四个 tab 的卡片都有正文、页面文本里没有 NaN / undefined / [object Object]、**页面上印的数字与产物里的值逐个对得上**。

| # | 断言 | 出处 |
|---|---|---|
| 1 | 页面加载与四个 tab 全部点过之后,零未捕获异常 | [`eval/judges/l4_render.js:217`](l4_render.js#L217) |
| 2 | 没有 404 | [`eval/judges/l4_render.js:219`](l4_render.js#L219) |
| 3 | 页面文本里没有 NaN / undefined / [object Object] | [`eval/judges/l4_render.js:252`](l4_render.js#L252) |
| 4 | ${sym} 页面上印的基线天数 == baselines 里的值 | [`eval/judges/l4_render.js:271`](l4_render.js#L271) |
| 5 | ${pid} 卡片数 == ${PANELS[pid]} | [`eval/judges/l4_render.js:317`](l4_render.js#L317) |
| 6 | ${pid} 每张可见的卡都有正文 | [`eval/judges/l4_render.js:327`](l4_render.js#L327) |

---

共 **50** 条可求值断言，覆盖 12 层。

⚠️ **「求值过」不等于「通过」。** 判官报三种结局:跑了通过 · 跑了失败 · **断言的对象不存在所以没求值**。第三种被折进第一种的话，一份空产物会被报成「全过」—— 这个坑本项目踩过（见 [badcases.md](badcases.md) 里判官自己的那几条）。