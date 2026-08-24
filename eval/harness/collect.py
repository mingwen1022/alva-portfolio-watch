# -*- coding: utf-8 -*-
"""把一次 eval 真跑的全部证据抓到本地，然后拆掉平台上的活资源。

⚠️ 顺序不能反。一个账号放得下的 playbook 有限，下一个案例发布同名时会覆盖上一个 ——
   **产物必须在拆之前落地**，否则这一轮就白跑了，而且看不出来白跑了。

⚠️ CLI 没有删 playbook 的命令（只有 automation / feed / cronjob）。
   所以「清场」的定义是：活资源全部拆掉，playbook 壳留着由下一轮覆盖。
   壳留着不消耗任何东西，但它会让 `playbooks mine` 显示上一轮的名字 —— 别据此判断清干净了。

用法：
    python3 eval/collect.py <run 目录> [--teardown]
    python3 eval/collect.py <run 目录> --credits-only   # 只补账单，不碰已冻住的产物
"""
import json, os, subprocess, sys, datetime, pathlib

RUN = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
if not RUN or not RUN.is_dir():
    sys.exit("用法: python3 eval/collect.py <run 目录> [--teardown]")
TEARDOWN = "--teardown" in sys.argv
# ⚠️ **抓完就该冻住。** 一次真跑的产物在拆掉 cronjob 之前是**活的** ——
#    重抓一次，判定结果会跟着变（实测:R2 重抓后 L1 从 ✓ 变「未跑」、产物从 24 变 25）。
#    那不是 bug，是「我们在测一个还在动的东西」。
#    所以要单独补账单时用 `--credits-only`:只重取计费，不碰已经冻住的产物。
CREDITS_ONLY = "--credits-only" in sys.argv

ENV = dict(os.environ, XDG_CONFIG_HOME=str(RUN / "config"))
OUT = RUN / "collected"
OUT.mkdir(exist_ok=True)


def alva(*args, **kw):
    """跑一条 alva 命令，返回 (ok, 解析后的对象或原文)。失败不抛 —— 失败本身是证据。"""
    r = subprocess.run(["alva", *args], capture_output=True, text=True, env=ENV, **kw)
    txt = r.stdout.strip()
    try:
        return r.returncode == 0, json.loads(txt)
    except Exception:
        return r.returncode == 0, txt or r.stderr.strip()


def save(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) if not isinstance(obj, str) else obj)
    return p


ok, who = alva("whoami")
user = who.get("username") if isinstance(who, dict) else None
# ⚠️ 主账号上跑 eval 是允许的（acct2 额度用完时的退路，`newrun.sh --acct1`），
#    因为拆资源按 `args.root` 匹配 —— 生产那本 portfolio-watch 的 root 对不上。
#    但那本**不能**被当成这一轮的产物:它的名字不来自 transcript，
#    真误判成本轮 root 的话，teardown 会把生产的四个 cronjob 全删掉。
#    所以只挡一件事:主账号上认出来的 root 恰好是生产那本。
MAIN_PROD = "/alva/home/mpkg1/playbooks/portfolio-watch"
save("whoami.json", who)
print(f"  身份 {user}")

# ── 1. 平台侧的状态：先记下来，拆之前 ────────────────────────────
manifest = {"collectedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "user": user, "files": [], "missing": []}

ok, pbs = alva("playbooks", "mine")
save("playbooks.json", pbs)
ok, jobs = alva("deploy", "list")
save("cronjobs.json", jobs)
ok, feeds = alva("feed", "list")
save("feeds.json", feeds)
# ⚠️ `credits items --today` 给的是**当天全部**，不是这一轮的。
#    直接存下来，报告那一列就会写着「这一轮花了 X」而实际是「账号今天花了 X」——
#    R2 与 R3 因此显示了一模一样的 626。
#    按时间窗切:run 目录名里的时间戳是开始，现在是结束。
ok, credits = alva("credits", "items", "--today")
save("credits-day.json", credits)          # 原始的也留着，切错了能回查

_stamp = RUN.name.rsplit("-", 2)
_t0 = None
if len(_stamp) == 3 and _stamp[1].isdigit():
    try:
        _t0 = datetime.datetime.strptime(_stamp[1] + _stamp[2], "%Y%m%d%H%M%S").timestamp() * 1000
    except Exception:
        _t0 = None
_t1 = datetime.datetime.now().timestamp() * 1000

if _t0 and isinstance(credits, dict):
    edges = credits.get("items", {}).get("edges", [])
    kept = [e for e in edges
            if _t0 <= float(e.get("node", {}).get("createdAtMs") or 0) <= _t1]
    credits = {"items": {"edges": kept},
               "_window": {"from": _t0, "to": _t1,
                           "note": "按 run 目录名的时间戳切；窗口外的条目在 credits-day.json"},
               "_droppedOutsideWindow": len(edges) - len(kept)}
    print(f"  credits 按本轮时间窗切:{len(kept)}/{len(edges)} 条")
else:
    # ⚠️ 切不了就说出来，不要把当天全部当成这一轮的
    credits = {"items": {"edges": []},
               "_window": None,
               "_note": "切不出本轮时间窗（目录名不含时间戳），当天全部见 credits-day.json"}
    print("  ⚠️ credits 切不出本轮时间窗 —— 报告会显示「无法归属」，不显示当天总额")
save("credits.json", credits)

# ⚠️ **谁建的，问 transcript，不问目录时间。**
#    第一版按 `mod_time` 取最新的目录 —— 2026-08-23 R3 因此抓成了上一轮的
#    `btc-sol-doge-watch`（那个壳还在，而且时间戳更新），报出来的字段全是别人的。
#    一个「取最新」的启发式在这里判的是「谁最后被碰过」，不是「谁是这一轮建的」。
#    transcript 里 agent 自己写的 `--name` 才是权威。
import re as _re
_tp = RUN / "transcript.txt"
_declared = None
if _tp.exists():
    _pat = _re.compile(r'''alva release playbook(?:-draft)?\s+--name\s+['"\\]*([A-Za-z0-9._-]+)''')
    _hits = _pat.findall(_tp.read_text(errors="ignore"))
    if _hits:
        _declared = _hits[-1]          # 最后一次发布用的名字
        print(f"  transcript 里 agent 发布的名字: {_declared}")

# ⚠️ `alva playbooks mine` 是给人看的文本（「• 显示名 [public]」换行缩进真名换行 id:）。
#    靠「行首不是 • 且不含 playbook」去猜真名，名字里带 playbook 三个字就会被**静默丢掉**，
#    而丢掉的症状是「找不到产物目录」——看起来像 agent 没发布，指向错误的一方。
#    ALFS 的 readdir 直接给准确答案，不用猜。
ok, ents = alva("fs", "readdir", "--path", f"/alva/home/{user}/playbooks")
names = [e["name"] for e in (ents.get("entries") or [])
         if isinstance(ents, dict) and e.get("is_dir")] if isinstance(ents, dict) else []
save("playbooks-readdir.json", ents)
print(f"  playbook 目录 {names or '（无 —— 这一轮可能根本没发布）'}")

# ── 2. 产物：整棵目录抓下来 ──────────────────────────────────────
# 一个账号可能留着上一轮的壳（CLI 删不掉），所以按修改时间取最新的那个，
# 而不是取第一个 —— 取错会把上一轮的产物当成这一轮的判，**而且全部通过**。
if CREDITS_ONLY:
    _mf = OUT / "manifest.json"
    if _mf.exists():
        _old = json.loads(_mf.read_text())
        manifest["files"] = _old.get("files", [])
        manifest["frozenAt"] = _old.get("collectedAt")
        manifest["note"] = "只补了账单；产物沿用 " + str(_old.get("collectedAt"))
        save("manifest.json", manifest)
        print(f"  ✅ 只补账单。产物冻结于 {_old.get('collectedAt')}，"
              f"{len(manifest['files'])} 个文件未动")
    else:
        print("  ⚠️ 还没抓过产物，--credits-only 只留下了账单")
    sys.exit(0)

root = None
if names:
    rows = [e for e in ents["entries"] if e.get("is_dir")]
    pick = None
    if _declared and _declared in [e["name"] for e in rows]:
        pick = _declared
        manifest["pickedBy"] = "transcript 里的 --name"
    elif len(rows) == 1:
        pick = rows[0]["name"]
        manifest["pickedBy"] = "账号上只有一个"
    else:
        # ⚠️ 认不出就**不猜**。抓错产物之后每一条断言都在判别人的东西，
        #    而它们照样会给出一个看起来合理的结论。
        manifest["missing"].append(
            "认不出这一轮建的是哪个 playbook（transcript 里没有 --name，账号上有 %d 个：%s）"
            % (len(rows), ", ".join(e["name"] for e in rows)))
        print("  ❌ " + manifest["missing"][-1])
    if pick:
        root = f"/alva/home/{user}/playbooks/{pick}"
        if len(rows) > 1:
            manifest["note"] = ("账号上有 %d 个目录，按 %s 选了 %s；其余：%s"
                                % (len(rows), manifest["pickedBy"], pick,
                                   ", ".join(e["name"] for e in rows if e["name"] != pick)))
            print("  " + manifest["note"])

# ⚠️ **主账号只能放一本 playbook**，所以在它上面跑 eval 就是原地覆盖生产那本 ——
#    这是既定的测试方式，不是事故。收集要照常做。
#    但**拆资源必须挡住**:那四个 cronjob 是生产的，删了就没了，
#    而它们的 root 恰好等于本轮 root，`args.root` 那道匹配在这里失效。
ON_MAIN_PROD = (root == MAIN_PROD)
if ON_MAIN_PROD:
    print(f"  ⚠️ 本轮跑在主账号的生产 playbook 上（{MAIN_PROD}）—— 数据已被覆盖，"
          "测完要还原。**teardown 在这一轮被禁用**。")
if not root:
    manifest["missing"].append("playbook root — agent 没有发布，或名字对不上")
    print("  ⚠️ 找不到 playbook 目录 —— 这本身就是一条 L0 结论，如实记下")
else:
    print(f"  产物根 {root}")
    stack, seen = [root], set()
    while stack:
        d = stack.pop()
        if d in seen:
            continue
        seen.add(d)
        ok, entries = alva("fs", "readdir", "--path", d)
        rows = entries.get("entries", entries) if isinstance(entries, dict) else []
        if not isinstance(rows, list):
            continue
        for e in rows:
            name, is_dir = e.get("name"), e.get("is_dir")
            if not name:
                continue
            full = f"{d}/{name}"
            if is_dir:
                stack.append(full)
                continue
            ok, body = alva("fs", "read", "--path", full)
            rel = full[len(root) + 1:]
            dst = OUT / "playbook" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
            manifest["files"].append({"path": rel, "bytes": dst.stat().st_size})
    print(f"  抓到 {len(manifest['files'])} 个文件")

# transcript 一并归档
tp = RUN / "transcript.txt"
if tp.exists():
    _txt = tp.read_text()
    (OUT / "transcript.txt").write_text(_txt)
    manifest["transcript"] = True

    # ── 本轮碰过哪些外部实现 ────────────────────────────────────────
    # ⚠️ **不判对错，只要求可见。** 平台自己有一个 `portfolio-watch-setup`，
    #    名字和用途都跟我们高度重叠，agent 用 `alva skillhub get` 就能把它拉进来。
    #    实测过一轮：拉完照着写 `require("@alva/portfolio-watch")`，撞 Pro 订阅墙，
    #    在那个形状上重写四五遍才绕回我们的脚本 —— 绕回来之后只补齐了最小集，
    #    四个 producer 只建了两个。
    #    这不是污染，是现实：用户的 agent 手上本来就同时有这两个。
    #    所以 eval **不屏蔽 skillhub** —— 屏蔽了测出来的是一个不存在的环境，
    #    要测的恰恰是「两个都在时我们这个赢不赢」。但它必须在报告里留痕，
    #    否则一轮「参考了竞品实现」的结果会被当成我们这个 skill 的成绩。
    #    ⚠️ 只能从 transcript 查 —— 产物上一点看不出来。
    #    ⚠️ **只数真正执行过的命令行，不数「文本里出现过」。**
    #       第一版按整篇计数，R5 报出 4 处 —— 逐条看全是假的:
    #       1 处是 agent 在读我们自己 SKILL.md 里的那段警告，
    #       3 处是 `alva release playbook --help` 里提到 `alva skillhub list`。
    #       也就是说，**警告写得越细，这个检测器命中越多** —— 它报的方向是反的。
    #       transcript 里执行过的命令都以 `/bin/zsh -lc` 开头，只在那些行里数。
    _cmds = [ln for ln in _txt.split("\n") if ln.startswith("/bin/zsh -lc")]
    _probes = {
        "skillhub_invoked":      "skillhub",
        "alva_module_required":  "@alva/portfolio-watch",
        "setup_skill_fetched":   "portfolio-watch-setup",
    }
    _hits = {k: sum(ln.count(v) for ln in _cmds) for k, v in _probes.items()}
    _hits = {k: n for k, n in _hits.items() if n}
    # 撞订阅墙是**返回值**不是命令，单独从全文找 —— 但要减掉 SKILL.md 自己那一处。
    _wall = _txt.count("requires a Pro subscription") - 1
    if _wall > 0:
        _hits["pro_subscription_wall"] = _wall
    manifest["externalRefs"] = _hits
    if _hits:
        print("  ⚠️ 本轮参考了外部实现（不判对错，但要计入解读）：")
        for k, n in _hits.items():
            print(f"       {k}  ×{n}")
    else:
        print("  ✅ transcript 里没有外部同名实现的痕迹")
else:
    # 「没有 transcript」和「有 transcript 且干净」不是一件事。
    manifest["externalRefs"] = None

# ⚠️ **抓早了会把「还没跑完」拍成「没做」。**
#    agent 建完就返回，而四个 cronjob 的首轮还在陆续落地。
#    2026-08-23 R4 起跑 11:10:56、抓取 11:14:27，而 cronjob 首轮落在 11:13:10–11:15:00 ——
#    **快照拍在了中间**，于是 `scan` 是空的、`scanned` 缺失，
#    我据此判定 BC24「没修好」，而手工再跑一次日线 producer 就写进去了。
#    产品没问题，是测量拍早了。
_fr = {}
try:
    _fr = json.loads((OUT / "playbook" / "data" / "meta.json").read_text()).get("freshness") or {}
except Exception:
    pass
_need = ["prices", "intraday", "news", "earningsCalendar", "market"]
_lack = [k for k in _need if not _fr.get(k)]
manifest["freshness"] = _fr
manifest["settled"] = not _lack
# ⚠️ **「压根没建」和「建了还没跑完」不是一回事，而落定检查会把前者说成后者。**
#    实测 R9（0700.HK）:agent 探到端点 400、按 skill 的规则拒绝建一个全空的面板，
#    而这里照样印「这几个 producer 还没落地……等下一轮重抓」—— 等多久都不会落地。
#    一句「再等等」把一个**已经完成且正确**的结局说成了测量没做完。
if root is None:
    # ⚠️ **只记事实，不下判断。** 第一版在这里直接写 `outcome: "declined"` ——
    #    也就是把「没有产物」等同于「正确地拒绝了」，而那恰恰是上一条
    #    （判官把正确拒绝记成 ✗）的镜像错误:一次静默的空跑会被记成一次漂亮的拒绝。
    #    「拒绝得站不站得住」需要读 agent 说了什么、它有没有先去核实 ——
    #    那是判断题，归 L5，不归收集器。这里只把证据摆好。
    manifest["outcome"] = "no_playbook"
    manifest["settled"] = True
    manifest["settleWarning"] = None
    try:
        _all = (RUN / "transcript.txt").read_text().rstrip().split("\n")
        # ⚠️ 按行数从尾部切会把工具返回的 JSON 一起切进来（实测 G-hk 的「理由」
        #    前一半是 `"credits_used": 0` 之类）。transcript 里 agent 自己说的话
        #    以单独一行 `codex` 起头 —— 从最后一个那行之后取，才是它真正说的。
        _i = max(i for i, l in enumerate(_all) if l.strip() == "codex") \
            if any(l.strip() == "codex" for l in _all) else len(_all) - 16
        _msg = [l for l in _all[_i + 1:] if l.strip() and l.strip() != "tokens used"
                and not l.startswith("/bin/zsh") and not l.strip().isdigit()
                and not l.strip().replace(",", "").isdigit()]
        manifest["finalMessage"] = "\n".join(_msg)[:900]
        # 「说了理由」与「先去核实过」是两件事，后者才是拒绝站不站得住的关键。
        manifest["probedBeforeDeclining"] = sum(
            1 for l in _all if l.startswith("/bin/zsh") and "alva " in l)
    except Exception as _e:
        # ⚠️ 原来这里写 `= None`，于是一个 NameError（`_tail` 改名后忘了跟着改）
        #    被吞成「agent 什么都没说」—— 而那正是判 ✗ 的依据。
        #    抽不出来和抽出来是空的必须分开:前者是我的 bug，后者是它的结论。
        manifest["finalMessage"] = None
        manifest["finalMessageError"] = f"{type(_e).__name__}: {_e}"
        print(f"  ❌ 抽 agent 最后一段时出错（不是它没说）：{type(_e).__name__}: {_e}")
    print("  ⚠️ 这一轮**没有产物**，也不是没跑完。agent 的最后一段已存进 manifest，"
          "拒绝站不站得住交给 L5 判。")
elif _lack:
    manifest["settleWarning"] = (
        "抓取时这几个 producer 还没落地:" + " ".join(_lack)
        + " —— 判定里任何「这块是空的」都可能只是没等到。等下一轮再 --credits-only 重抓，"
          "或直接重抓产物")
    print("  ⚠️ " + manifest["settleWarning"])
else:
    print("  ✅ 五个 freshness 键都在，快照已落定")

save("manifest.json", manifest)

# ── 3. 拆活资源 ──────────────────────────────────────────────────
if ON_MAIN_PROD and TEARDOWN:
    print("\n  ⛔ 这一轮跑在生产 playbook 上，**teardown 已禁用** —— "
          "那四个 cronjob 是生产的，`args.root` 那道归属判据在这里等于没有。"
          "要停请手工按 id 停。")
elif not TEARDOWN:
    print("\n  只抓取，没有拆。确认产物齐全后再跑一次带 --teardown")
    sys.exit(0)

if not manifest["files"]:
    sys.exit("❌ 一个产物文件都没抓到，拒绝 teardown —— 拆完就再也拿不回来了")

# ⚠️ **只拆这一轮建的。**
#    第一版删的是账号上**所有** cronjob 和 feed —— 2026-08-23 因此误删了
#    31910 `portfolio-watch-automation`（8-22 就在、已 paused、feed 已孤立）。
#    它不是这一轮建的，而脚本没有任何地方问过「这是谁的」。
#
#    归属判据用 args.root：这一轮的 cronjob 全部带 `--args '{"root": "<playbook 根>"}'`，
#    那是 SKILL.md 第八步规定的传参方式，比按名字前缀匹配可靠 ——
#    名字是 agent 自己起的，下一个案例可能叫别的。
#    ⚠️ 认不出归属的**不拆，列出来让人看**。静默跳过和静默删除一样糟，
#       只是方向相反：一个留下垃圾，一个删掉别人的东西，而两者都不出声。
torn, kept = [], []
def mine(obj):
    a = obj.get("args") or {}
    r = a.get("root") or ""
    return bool(root) and isinstance(r, str) and r == root

jl = jobs.get("cronjobs", []) if isinstance(jobs, dict) else []
for j in jl:
    if not mine(j):
        kept.append(f"cronjob {j['id']} {j.get('name')} — args.root 不是本轮的产物根，未拆")
        continue
    ok, _ = alva("deploy", "delete", "--id", str(j["id"]))
    torn.append(f"cronjob {j['id']} {j.get('name')} {'ok' if ok else 'FAILED'}")

# feed 上没有 args，只能按「被本轮的 cronjob 引用过」来认
mine_feed_names = {j.get("name") for j in jl if mine(j)}
fl = feeds.get("feeds", []) if isinstance(feeds, dict) else []
for f in fl:
    if f.get("name") not in mine_feed_names:
        kept.append(f"feed {f['id']} {f.get('name')} — 没有本轮的同名 cronjob 引用它，未拆")
        continue
    ok, _ = alva("feed", "delete", "--id", str(f["id"]))
    torn.append(f"feed {f['id']} {f.get('name')} {'ok' if ok else 'FAILED'}")

save("kept.json", kept)

save("teardown.json", torn)
print("\n  拆掉：")
for t in torn:
    print("   ", t)
if kept:
    print("\n  ⚠️ 认不出归属，没拆（要拆请自己确认后手动删）：")
    for k in kept:
        print("   ", k)
print("\n  ⚠️ playbook 壳没删（CLI 无此命令）。下一轮发布同名时覆盖它。")
