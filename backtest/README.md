# backtest/scripts

本目录含三类脚本与逐族实验目录。检查器与仓库根之间存在相对路径依赖，
分组在文档中标注，目录结构保持不变。

## 检查器

验证同一事实的多个副本是否一致，而非验证数值本身。改动后需运行。

| 脚本 | 查什么 |
|---|---|
| [`check_consistency.py`](check_consistency.py) | 总入口。跑下面几个 + eval 断言 + 四个 producer 冒烟 + gap 文案三个方向 |
| [`check_schema_drift.py`](check_schema_drift.py) | 产物里的字段必须在 `output-schema.md` 有出处 |
| [`check_skill_refs.py`](check_skill_refs.py) | SKILL.md 引用的文件真的存在 |
| [`check_js_parity.py`](check_js_parity.py) | Python 版与 `skill/scripts/lib.js` 同一算法必须同一结果（线上只有 V8） |
| [`check_disclaimer.py`](check_disclaimer.py) | 免责与边界文案没被删掉 |
| [`check_prompt_english.py`](check_prompt_english.py) | 递给模型的 prompt 保持英文 |
| [`test_state.py`](test_state.py) | 状态机的读-改-写 |
| [`add_toc.py`](add_toc.py) | 长文档目录自动生成 |

## 取数

原始数据（33.8 MB）不包含在仓库中。来源、端点、参数、计费与陷阱见
[`../data-sources.md`](../data-sources.md)，以下脚本是该文档的可执行部分。

| 脚本 | 拉什么 |
|---|---|
| [`fetch.js`](fetch.js) · [`fetch2.js`](fetch2.js) | 日线 / 完整 OHLCV |
| [`insider.js`](insider.js) · [`insider2.js`](insider2.js) · [`ev_fetch.js`](ev_fetch.js) | 内部人 Form 4 |
| [`gov_fetch.js`](gov_fetch.js) · [`gov2.js`](gov2.js) | 议员交易 |
| [`po_fetch.js`](po_fetch.js) · [`trump.js`](trump.js) | 社交语料。⚠️ 计费，约 21 credits/次 |
| [`lag.js`](lag.js) | 申报滞后分布 |

## 回测引擎

[`engine.py`](engine.py) · [`ev_engine.py`](ev_engine.py) · [`ev2.py`](ev2.py) ·
[`ev3.py`](ev3.py) · [`export.py`](export.py)

## 逐族实验

一族一个目录。结论保存在 [`../results-*.md`](../)，被证伪与被搁置的记录在
[`../signal-registry.md`](../signal-registry.md)。

| 目录 | 族 |
|---|---|
| `pv-expanded/` · `pv-intraday/` | PV 价量（日线 / 盘中） |
| `ev-expanded/` · `ev35/` | EV 事件 |
| `dr/` · `dr-expanded/` | DR 衍生品 |
| `ma/` · `ma-expanded/` | MA 宏观 |
| `andor/` · `andor-verify/` | 决策 #1 的 AND vs OR 复核 |
| `universe/` | 样本池扩建（92 美股 + 25 加密） |
| `probes/` | 端点探测 |
| `m24/` | M24 指标 |
| `smoke/` | 四个 producer 的冒烟测试（被 `check_consistency.py` 调用） |

### PO 族未进入 spec

`po-corpus/` · `po-luna/` · `po-run/` · `po34/` 共 79 个文件，占本目录的 28%，
而 PO 族最终没有信号进入 [`product/signal-spec.md`](../../product/signal-spec.md)。

原因是 LLM 判定的可重复性不足：`specificity` 在关键样本上三次重复出现 2:1 分歧。
判据本身不稳定时，不能用它判定信号。详见 [`../results-po.md`](../results-po.md)
与 registry 的 PO 族章节。

这部分保留在仓库中，作为被排除方案的实验记录。
