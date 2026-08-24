# Portfolio Watch

一个 [Alva](https://alva.ai) Skill。用户用一句自然语言描述要盯的持仓，它生成一个持续运行的
Playbook：四个 tab 的看板、四个定时任务，以及推送到手机的告警。

判断逻辑由 Skill 决定：什么算异动、什么是噪音、多个信号同时出现时怎么排序。
阈值来自对 92 只美股与 25 个加密资产的历史回测，逐标的验证，不使用市场统一规则。

- 线上实例：[alva.ai/u/mpkg1/playbooks/portfolio-watch](https://alva.ai/u/mpkg1/playbooks/portfolio-watch)
- Playbook 的功能与告警逻辑：[中文](Playbook介绍.md) · [English](Playbook-overview.md)
- 做题思路：[APPROACH.md](APPROACH.md)

## 关于这个仓库

仓库包含 Skill 本体与它背后的全部依据。四层各自独立：

**规格层**（`product/`）是已定案信号的唯一定义处，含 13 条信号的触发式、参数、适用范围、
投递层级，以及产物的数据契约。改阈值或算式改这里。

**证据层**（`backtest/`）记录这些定义是怎么来的：测过 28 条候选，判据是什么，
哪些被证伪、哪些样本不足、哪些机制成立但不可复用。结论按信号族分文件，
结论的变更历史单独记在 `revisions.md`。

**评估层**（`eval/`）回答另一个问题：把 SKILL.md 交给一个不知情的 agent，
它建出来的东西对不对。10 个案例、17 轮真跑、六层判官、60 条缺陷记录。

**实现层**（`skill/` · `mock/` · `pipeline/`）是交付物、可运行的界面与数据契约实例、
以及生成 demo 数据的管线。

`skill/references/` 是写给 agent 的英文精简版，与 `product/` 内容对应但读者不同；
规格以 `product/` 为准。

## 仓库结构

| 目录 | 内容 |
|---|---|
| [`skill/`](skill/) | Skill 本体：[SKILL.md](skill/SKILL.md) · [scripts/](skill/scripts/)（初始化与四个 producer）· [template/](skill/template/) · [references/](skill/references/) |
| [`product/`](product/) | 信号定义 · 算式 · 界面内容 · 数据契约 · 计算链路 |
| [`backtest/`](backtest/) | 回测结论、判据、样本池、取数说明 · [README](backtest/README.md) |
| [`eval/`](eval/) | 案例、判官、报告、缺陷台账 · [README](eval/README.md) |
| [`mock/`](mock/) | 界面与三份数据契约实例 |
| [`pipeline/`](pipeline/) | demo 数据的取数与构建 |
| [`notes/`](notes/) | 前期调研归档与过程记录 |

## 本地运行

```bash
python3 -m http.server 8899 --directory mock
# http://localhost:8899/portfolio-watch-mock.html
```

`mock/` 提供三本账用于切换：混合持仓、ETF 与新上市标的、首次运行。
页面读取的数据即 [`product/output-schema.md`](product/output-schema.md) 定义的契约实例。

## 检查

```bash
python3 backtest/scripts/checks/check_consistency.py   # 规格 · 契约 · 文案 · producer 冒烟，共 23 项
python3 eval/judges/assertions.py mock/data            # 产物断言 L0–L3
node    eval/judges/l4_render.js <产物目录>            # L4 无头浏览器渲染
python3 skill/bundle.py                                # 打交付包
```

判官逐条见 [`eval/judges.md`](eval/judges.md)（50 条断言，由脚本从判官代码生成）。
历轮结果见 [`eval/report.html`](eval/report.html)，缺陷记录见
[`eval/badcases.md`](eval/badcases.md)。

## 数据

回测数据约 54 MB，不包含在仓库中，其中含第三方平台的帖子全文，不适合随代码分发。
回测结论保存在 `backtest/` 的各份文档里，原始数据仅在重算时需要。

取数来源、端点、参数、计费与已知陷阱见
[`backtest/data-sources.md`](backtest/data-sources.md)，脚本在
[`backtest/scripts/fetch/`](backtest/scripts/fetch/)。

## 限制

- 真实券商账户的接入路径未经端到端验证。字段形状已确认，多币种、SHORT 持仓、
  保证金账户的权重口径未验证。
- 全部测试使用模拟数据，构建周期 5 天。盘中、盘后与跨周的实际执行未经周期性验证。
- 回测覆盖美股与加密。ETF、港股等类别在有历史数据时可正常展示与告警，
  但告警后是否伴随量价波动未在同类资产上验证。
- 判据只测触发后的波动放大。不通过波动表现的信息不在这把尺子的量程内。
- 美股盘中信号当前不推送手机：RTH 窗口下触发次数不足以达到判据的独立块要求，
  逐标的评级封顶 L2。加密不受此限制。
