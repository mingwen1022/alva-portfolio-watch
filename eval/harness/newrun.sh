#!/bin/bash
# 起一次 eval 真跑。用法：eval/harness/newrun.sh <case> [--go]
#
# 不带 --go 只做准备并打印要投的那句话；带 --go 才真的调 codex。
#
# ⚠️ 三重隔离，缺一条都会污染这次评估或线上环境：
#
#   工作目录   空目录 + .agents/skills/{alva,portfolio-watch}
#              —— 不能在本仓库里开：仓库的 CLAUDE.md 会被自动加载，
#                 里面是全部阈值、决策与实测数字，等于把答案连同题目一起发下去
#   CODEX_HOME 独立 codex home，只搬 auth.json
#              —— 默认 home 里有 AGENTS.md 与 40 个别的 skill
#   ALVA 账号   XDG_CONFIG_HOME 指到本次 run 的配置，默认 profile 写成 acct2
#              —— 否则 eval agent 会花主账号的 credits，而且它按 SKILL.md 第八步
#                 执行 `alva release playbook --name portfolio-watch` 时，
#                 与线上那个公开运行中的 playbook 同名，会被覆盖
set -euo pipefail

CASE="${1:?用法: eval/harness/newrun.sh <case> [--go] [--no-skill]}"
GO=""
PICK=1                 # 默认模拟「用户指名了 skill」——那是产品里的真实流程
                       # ⚠️ 一个状态一个词:全套只说「指名 / 未指名」。
                       #    「预选」「先选」「选中」是同一件事的三个说法，
                       #    读者会以为那是三个开关。
for a in "$@"; do
  [ "$a" = "--go" ] && GO="--go"
  [ "$a" = "--no-skill" ] && PICK=0
done
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BASE="/Users/ming/project/alva_test"
TS="$(date +%Y%m%d-%H%M%S)"
RUN="$BASE/runs/$CASE-$TS"
QFILE="$REPO/eval/cases/$CASE/input.md"

[ -f "$QFILE" ] || { echo "❌ 没有这个案例: $CASE"; ls "$REPO/eval/cases"; exit 1; }

# ── 交付包（软链变真文件 + 验证门）──
python3 "$REPO/skill/bundle.py" >/dev/null

# ── 工作目录 ──
mkdir -p "$RUN/.agents/skills"
cp -r "$BASE/.agents/skills/alva" "$RUN/.agents/skills/"          # 官方
cp -r "$REPO/dist/portfolio-watch" "$RUN/.agents/skills/"          # 我们的
# ⚠️ 真实流程是**先选 skill、再提问**:Alva 的输入框里会出现一个 chip
#    （截图里那个「Fintwit Roundtable ×」），然后用户才打字。
#    此前 harness 把裸句子丢给 agent，让它在两个 skill 里自己挑 ——
#    那是一道**更难、而且不存在的**题，测出来的是「我们的描述抢不抢得过别人」，
#    不是「选中我们之后我们做得对不对」。两件事都值得测，但不能混成一次。
#
#    case 文件里只留用户那一句话；「选中」这个动作由 harness 加，
#    因为它属于**环境**不属于输入。`--no-skill` 关掉它，测另一种。
if [ "$PICK" = "1" ]; then
  { printf '使用 portfolio-watch skill。\n\n'; cat "$QFILE"; } > "$RUN/QUERY.txt"
else
  cp "$QFILE" "$RUN/QUERY.txt"
fi
echo "$([ "$PICK" = "1" ] && echo skill-selected || echo skill-not-selected)" > "$RUN/mode.txt"

# ── codex home ──
export CODEX_HOME="$RUN/.codex"
mkdir -p "$CODEX_HOME"
cp ~/.codex/auth.json "$CODEX_HOME/auth.json"

# ── alva 账号：默认 acct2；`--acct1` 在主账号上跑（acct2 额度用完时的退路）──
# ⚠️ 主账号上**跑着生产那本 portfolio-watch**。可以在它上面起 eval，
#    因为 collect 拆资源按 `args.root` 匹配，生产那本的 root 对不上，不会被误删。
#    但隔离检查要跟着放宽 —— 否则它把「就是要用主账号」判成隔离失败。
ACCT="acct2"
for a in "$@"; do [ "$a" = "--acct1" ] && ACCT="default"; done
export XDG_CONFIG_HOME="$RUN/config"
mkdir -p "$XDG_CONFIG_HOME/alva"
python3 "$REPO/eval/harness/_pickacct.py" "$XDG_CONFIG_HOME/alva/config.json" "$ACCT" || exit 1
WHO="$(alva whoami 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("username","?"))' || echo '?')"
if [ "$ACCT" = "acct2" ]; then
  [ "$WHO" = "mpkg1" ] && { echo "❌ 隔离失败：仍然是主账号 mpkg1"; exit 1; }
else
  [ "$WHO" = "mpkg1" ] || { echo "❌ --acct1 却不是 mpkg1，实际是 $WHO"; exit 1; }
  echo "  ⚠️ 这一轮跑在**主账号**上（生产那本也在这里）。拆资源按 args.root 匹配。"
fi

cat <<TXT

  案例      $CASE
  run       $RUN
  alva 身份  $WHO   （不是主账号 mpkg1 ✅）
  余额      $(alva credits wallet 2>/dev/null | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("balance"),"· 今日已用",d.get("todayUsed"))' || echo '?')

  模式      $(cat "$RUN/mode.txt")   （--no-skill 切换成「不指名，靠 description 自己触发」）

  要投的那一句：
$(sed 's/^/    /' "$RUN/QUERY.txt")

TXT

if [ "$GO" != "--go" ]; then
  echo "  只做了准备。真跑加 --go"
  exit 0
fi

# ── 预算闸门 ──
# ⚠️ harness 压不了归因次数。dailyCap 在 config/alerts.json 里，
#    那个文件是 agent 在运行中自己写的 —— 开跑前它还不存在。
#    能做的只有一件事：按最坏情况核余额，不够就不开跑。
#    （拉数基本免费；花钱的只有归因，约 208/次 × cap 10。）
# 一次归因 110–330（rollup 79–299 + 4~5 条检索子条），cap 10 → 绝对上限约 3,300，
# 已经超过 acct2 每日 3,000。所以闸门**不是**「够不够最坏情况」——
# 那样它会挡掉每一次运行，等于没装。
#
# 闸门要挡的是另一件事：**跑到一半没钱**。半个建好的 playbook 比没开跑更糟 ——
# 数据落了一部分、卡片缺归因，看起来像信号不成立，而不是像没钱了。
# 所以设成「够走完预期路径 + 余量」的地板。
#
# 预期路径：单标的最多 2 次归因（PV1 日线 + PV5 盘中，US 族不调），
# 加上 playbook 运行时长（2 credits/分钟，一轮几十次 cronjob 约 30–50）。
FLOOR=800
BAL="$(alva credits wallet 2>/dev/null | python3 -c 'import sys,json;print(int(float(json.load(sys.stdin).get("balance") or 0)))' || echo 0)"
if [ "$BAL" -lt "$FLOOR" ]; then
  echo "❌ 余额 $BAL < 地板 $FLOOR —— 不开跑，会跑到一半没钱。"
  exit 1
fi
echo "  预算闸门  余额 $BAL ≥ 地板 $FLOOR ✅   （绝对上限 cap10 × 330 ≈ 3300，挡不住，靠事后核账）"
echo "$BAL" > "$RUN/balance-before.txt"
echo "  开跑（sandbox: workspace-write + 网络放行）…"
cd "$RUN"
# ⚠️ `< /dev/null` 不能省。stdin 不是 TTY 时 codex 会把管道内容**追加到 prompt**，
#    于是它停在「Reading additional input from stdin...」等 EOF —— 没有报错、没有超时，
#    transcript 停在 39 字节，看起来像模型在思考。
#    2026-08-23 第二轮就这么挂了 4 分钟：起因是同一条 shell 命令里先跑了一个 heredoc
#    （git commit -m "$(cat <<EOF ...)"），它把 stdin 留在了一个不会 EOF 的状态。
codex exec --skip-git-repo-check -s workspace-write \
  -c sandbox_workspace_write.network_access=true \
  -C "$RUN" "$(cat "$RUN/QUERY.txt")" < /dev/null 2>&1 | tee "$RUN/transcript.txt"

echo
echo "  transcript: $RUN/transcript.txt"
echo "  接下来：python3 $REPO/eval/collect.py $RUN"
