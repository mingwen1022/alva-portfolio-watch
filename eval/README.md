# eval

本目录评估 Skill 本身：把 SKILL.md 交给一个不知情的 agent，检验它建出的产物。
方案见 [`PLAN.md`](PLAN.md)，判官逐条见 [`judges.md`](judges.md)。

## 目录内容

| | |
|---|---|
| [`PLAN.md`](PLAN.md) | **方案**：要回答什么 · 为什么这么切案例 · 五档判官 · 打分 · 成本 · 造判官的顺序 |
| [`judges.md`](judges.md) | **判官 spec** —— 每一层实际断言了什么，50 条逐条列出并链到源码行。⚠️ 由 [`build/gen_judges.py`](build/gen_judges.py) 从判官代码生成，**不要手写** |
| [`badcases.md`](badcases.md) · [`.html`](badcases.html) | **缺陷台账** 69 条：根因 · **判官当时抓到没有** · 修法 · 真跑证据 |
| [`report.html`](report.html) | **跑分报告** 17 轮：每轮的 query · 模式 · 六层结果 · 花费 |
| [`cases/`](cases/) | 10 个案例，每个一句 `input.md` + 一份 `why.md`（这一轮想测什么、为什么这么挑） |
| [`judges/`](judges/) | 判官本体 —— `assertions.py`（L0–L3）· `l4_render.js`（L4 渲染）· `l5_extract.py` + `l5_collect.py`（L5 抽题与收票） |
| [`harness/`](harness/) | 怎么把一轮跑起来 —— `newrun.sh`（三重隔离）· `collect.py`（抓产物、拆资源）· `pv1_drill.py`（触发演练）· `_pickacct.py` |
| [`build/`](build/) | 三个生成器 —— `report.py` → `report.html` · `badcases.py` → `badcases.md/.html` · `gen_judges.py` → `judges.md` |

判官、执行、生成三类分目录存放。文档与产出物置于顶层。

## 单项检查

```bash
python3 backtest/scripts/checks/check_consistency.py   # 23 项 + producer 冒烟测试
python3 eval/judges/assertions.py <产物目录>           # L0–L3（50 条里的 44 条）
node    eval/judges/l4_render.js <产物目录>            # L4 渲染（无头浏览器）
python3 skill/bundle.py                                # 交付包，跑真 eval 前必跑
python3 eval/build/gen_judges.py                       # 改了断言就重生成 judges.md
```

## 完整一轮

```bash
eval/harness/newrun.sh C-single                    # 只做准备，打印要投的那句话与隔离状态
eval/harness/newrun.sh C-single --go               # 真跑
python3 eval/harness/collect.py <run>              # 抓产物到本地（先只抓）
python3 eval/harness/collect.py <run> --teardown   # 确认齐全后，拆掉 cronjob 与 feed
python3 eval/build/report.py               # 渲染 eval/report.html + report.md
```

⚠️ 三重隔离由 `newrun.sh` 保证，缺任一条都会污染评估或线上环境：
空目录（不能在本仓库里开 —— 仓库的 CLAUDE.md 会被自动加载，那是答案）·
独立 CODEX_HOME（只搬 auth.json）· `XDG_CONFIG_HOME` 把 alva 默认账号换成 acct2
（主账号的 playbook 是公开且正在跑的，而 SKILL.md 第八步会用同一个名字发布）。

⚠️ 单个账号可容纳的 playbook 数量有限，且 CLI 无删除 playbook 的命令。
顺序为：抓产物 → 拆活资源 → 下一案例发布同名时覆盖。
抓取必须在拆除之前 —— 拆除后产物不可恢复，且失败不可见。

## L5 · 需要判断的层

该层的判官是主 session 的子 agent，而非 Alva 的 `ask()`：一次归因走 `ask()` 需
110–330 credits，三票约一千。子 agent 不消耗 Alva credits，且能真正独立开三个 ——
同一上下文中询问三次不构成三票。

```bash
python3 eval/judges/l5_extract.py <产物目录>          # 抽题，看一眼
python3 eval/judges/l5_extract.py <产物目录> --json > l5-items.json
# ↑ 然后由主 session 派三个子 agent，各判一个角度，各自吐一份 judge-*.json
python3 eval/judges/l5_collect.py judge-*.json --out <collected 目录>
```

中间一步不在脚本内。由 Python 调用 LLM 会形成「脚本假装能判」的结构，
而实际判定者是另一方，判决归属无法追溯。

### 三个角度

```
A  来源支撑    summary 里每个事实性说法，能不能在它自己的 sources 里找到出处
B  措辞越界    对着归因提示词那八条规则逐条撞 + 语言跟随 + 钟点时刻
C  与数据一致  数字对不对得上 measured · timing 字段按定义重算对不对
```

⚠️ 合票采用全票制，不用多数决。三个判官判定的不是同一个问题：

```
❌ 三个里两个说 pass 就算过
   → 一条无源解释只要措辞干净、数字对得上，就 2:1 过了。
     而无源正是这条产品线一开始要解决的问题
✅ 任一角度 fail 即 fail，并记下是哪个角度
   角度不重叠，所以每一票都是独立否决权
```

多数决仅在同角度重复投票时成立。将三个角度当作对同一问题的三次采样，
是把「角度」误作「重复」。

⚠️ 判官缺席（文件不存在、JSON 损坏）记为缺席，不记为通过。
`confidence: low` 的票不参与否决但需报出 —— 「判不了」与「判了通过」是两种状态。

## 真跑期间的 harness 约束

bash 按字节偏移惰性读取脚本：执行完一条命令后 lseek 回保存的偏移继续解析。
在 `newrun.sh` 运行期间编辑它，文件长度变化会导致 codex 退出后 bash 从错位处继续读取，
最坏情况是重新执行 codex 那条命令，产生二次开销，且表现得像它自行重试。

2026-08-23 的 C-single 真跑期间就发生过（改预算闸门），靠事后挂看门狗
（codex 一退出立刻 kill wrapper）堵住的。

```
常规做法   等本轮结束，或先将改动写入其他文件，跑完再合并
必须改时   改后立即挂看门狗：while kill -0 <codex_pid>; do sleep 2; done; kill <wrapper_pid>
```

`harness/collect.py` 与 `build/report.py` 不受此限制：它们在真跑之后执行，
Python 一次性编译整个文件后再运行。

## 还没造的

变异表的执行器（`mutate.py`）· L4 的文案判官。

L4 渲染判官与 L5 都已经在用了（L5 在 R9 / R10 上判过「拒绝站不站得住」，
结论与理由存在各轮的 `collected/l5.json`）。

**PLAN.md §九 写明了顺序：判官必须先在已知答案的产物上被弄挂过，才有资格判未知产物。**
台账里判官自己的那几条（[BC41](badcases.md) 数的是我们自己写的警告 ·
[BC43](badcases.md) 印了 42 条只渲染 34 条）就是这条规矩没做到位的代价。
