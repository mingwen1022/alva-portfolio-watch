# 调研归档 · 只读

> **这三份是调研过程的记录，不是规格。** 结论已提取到
> [`../signal-registry.md`](../signal-registry.md)，**以 registry 为准**。
>
> 保留原文的理由：审计链。评审问「你这个 2σ 怎么变成 1.5 的」时，得能指出出发点在哪。
> **不要修改这三份**——改了就丢了「我们从哪里出发」的痕迹。

---

## 三份的分工

| 文档 | 内容 | 结论去向 |
|---|---|---|
| [`platform-capability.md`](platform-capability.md) | Alva 平台能力：19 个 Arrays data-skill · 十大监控维度 · **官方异动检测规则** · beta 三层归因 · Episode 状态机 · 覆盖矩阵 | registry M1–M6、M21、PV1–PV4 的骨架、§6.4 去重 |
| [`industry-dashboard.md`](industry-dashboard.md) | 业界看板与指标：IBKR / Koyfin / Bloomberg 的区块清单 · 常规指标 · **集中度阈值惯例** · 5/25 规则 | registry M20、M22、PF1–PF2；content-spec §二 指标取舍 |
| [`alert-methodology.md`](alert-methodology.md) | 告警本身：RVOL 阈值 · **Form 4 代码** · 簇买超额收益 · 加密衍生品反身性回路 · **信号强度五条总纲** · 告警工程（分级/去重/抑制/富化）· 宏观与政策告警 | registry M3、M7、M9、M12–M14、EV1、DR1–DR4、§6.1–6.7；**PV1 的原则来源** |

---

## 三处最关键的引用

**① 官方异动检测规则** — `platform-capability.md` §三

原文写着「this is exactly the detection logic to reimplement for a symbol Alva doesn't cover」。
PV1–PV4 的骨架直接来自这里，我们改了两处：`z` 的基线算法（改用 MAD）、`volume_z` 的口径（改用 RVOL 比值）。

**最重要的一处改动是逻辑本身**：官方是 `price_z OR volume_z OR ...`（任一命中），我们改成 AND。
不是官方错了——官方是数据层要不漏（检测），我们是最后一公里要不吵（告警）。

**② 信号强度五条总纲** — `alert-methodology.md` §三

文档自己写着「从三块研究里提炼出的通用判据」，**是归纳不是引用**。
第 1 条「难被解释掉」是总纲，第 4 条「交叉确认」是 PV1 的原则来源。

⚠️ 但从「交叉确认」这个原则到 `|z|≥θz AND RVOL≥θv` 这个式子，**中间没有依据**——那一步是本项目的假设，
后来被 Phase 1 回测证实（V倍数 1.96 vs 1.42/1.57）。

**③ Form 4 交易代码** — `alert-methodology.md` §1.2

`P` 公开市场买入是最干净的信号；`M` 期权行权、`A` 授予无信号。
这直接决定了 EV1 只取 P。后续实测发现 `is_10b51` 字段存在，促成了 EV2 的新增。

---

## 已知的过时之处

这三份写于回测之前，以下内容**已被实测推翻或修正**，以 registry 为准：

| 位置 | 过时内容 | 现状 |
|---|---|---|
| `alert-methodology.md` §六 标题 | 「我们的 15 个告警」 | 实际 **24 条**（§七 自己就列了 23 行） |
| `alert-methodology.md` §七 阈值表 | 价格异动「≥ 2σ 且 RVOL ≥ 2.0」 | **θz=1.5**；θv 分股票 2.0 / 加密 3.0 |
| `alert-methodology.md` §七 | 未含高波股票降级 | PV1 对 σ_ann>50% 的股票**降级 Warning** |
| `alert-methodology.md` §七 | 内部人只有「簇买」 | 新增 **EV2 簇卖**（剔 10b5-1） |
