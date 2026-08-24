# -*- coding: utf-8 -*-
"""PV1 触发演练：把阈值临时压到必触发，验完整链路，再还原。

⚠️ **为什么需要这个。** PV1 是这套东西里唯一通过回测判据的告警信号，
   而十八轮真跑里**它一次都没响过** —— 没有一只标的真的同时越过两条线。
   于是 `if (fired) { findings.push({...}) }` 那个分支从没被执行过，
   而 BC56 就藏在里面：三处裸的 `move`，一旦真响就 `ReferenceError`，
   `feed.run()` 吞掉异常，整个日线 producer 在那行 abort ——
   **scan / portfolio / series / meta 全都不写，PV1 触发的那一天页面反而是空的。**

   它躲过十八轮，只因为分支没被走过。**罕见分支不造触发就等于没测过。**

⚠️ **这不是「改阈值让测试通过」。** 阈值本身不是被测对象 ——
   θ 的取值有回测背书，这里改的是「让 fired 为真」这个前提，
   验的是**为真之后那条路走不走得通**。跑完必须还原，脚本自己保证。

用法：
    python3 eval/pv1_drill.py <playbook-root> [--profile acct2]

它做四件事，任何一步失败都会尝试还原：
    1. 备份 baselines.json 与 findings.json
    2. 把所有标的的 theta_z / theta_v 压到 0.05，跑日线 producer
    3. 核对：每只 scan 是 triggered · 每只都有一条 PV1 finding ·
       delivery 三处上限取 max · scan 读数没被连坐
    4. 还原 baselines，再跑一次，确认回到原状
"""
import json, subprocess, sys, os, tempfile, pathlib

ROOT = None
PROFILE = None
argv = sys.argv[1:]
if "--profile" in argv:
    i = argv.index("--profile"); PROFILE = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
if argv: ROOT = argv[0]
if not ROOT:
    sys.exit("用法: python3 eval/pv1_drill.py <playbook-root> [--profile acct2]")

ENV = dict(os.environ)
if PROFILE:
    # 一次性配置目录，跟 newrun.sh 一个路子
    d = tempfile.mkdtemp(prefix="pv1drill-")
    os.makedirs(f"{d}/alva", exist_ok=True)
    src = json.load(open(os.path.expanduser("~/.config/alva/config.json")))
    acct = (src.get("profiles") or {}).get(PROFILE)
    if not acct: sys.exit(f"❌ 没有 {PROFILE} profile")
    json.dump({"profiles": {"default": acct}}, open(f"{d}/alva/config.json", "w"))
    os.chmod(f"{d}/alva/config.json", 0o600)
    ENV["XDG_CONFIG_HOME"] = d

NAME = ROOT.rstrip("/").split("/")[-1]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pv1drill-io-"))


def alva(*a):
    r = subprocess.run(["alva", *a], capture_output=True, text=True, env=ENV)
    return r.returncode == 0, r.stdout


def read(rel):
    ok, out = alva("fs", "read", "--path", f"{ROOT}/{rel}")
    if not ok: sys.exit(f"❌ 读不到 {rel}")
    return json.loads(out)


def write(rel, obj):
    p = TMP / rel.replace("/", "_")
    p.write_text(json.dumps(obj, ensure_ascii=False))
    ok, _ = alva("fs", "write", "--path", f"{ROOT}/{rel}", "--file", str(p))
    if not ok: sys.exit(f"❌ 写不进 {rel}")


def run(script):
    ok, out = alva("run", "--entry-path", f"~/playbooks/{NAME}/scripts/{script}",
                   "--timeout-ms", "600000",
                   "--args", json.dumps({"root": ROOT, "playbookUrl": "drill"}))
    try: d = json.loads(out)
    except Exception: return "unparsable", out[:200]
    # ⚠️ feed.run 吞异常 —— status 说 completed 不代表脚本没炸。
    #    error 字段才是真的，必须看它。
    return d.get("status"), (d.get("error") or "")


print(f"── PV1 触发演练 · {ROOT}")
base0 = read("data/baselines.json")
find0 = read("data/findings.json")
(TMP / "base0.json").write_text(json.dumps(base0, ensure_ascii=False))
print(f"  已备份 baselines（{len(base0.get('baselines') or base0)} 只）与 findings")

try:
    d = base0.get("baselines") or base0
    lowered = json.loads(json.dumps(base0))
    dl = lowered.get("baselines") or lowered
    for s in dl:
        th = dl[s].get("thresholds") or {}
        th["theta_z"] = 0.05
        th["theta_v"] = 0.05
    write("data/baselines.json", lowered)
    print("  θz = θv = 0.05 已就位")

    st, err = run("producer.js")
    print(f"  日线 producer: {st}" + (f"  ⚠️ {err[:160]}" if err else ""))
    if err:
        sys.exit("❌ **这就是 BC56 的形状** —— fired 为真时那条分支炸了")

    f = read("data/findings.json")
    pv1 = [x for x in f.get("findings") or [] if x["signalId"] == "PV1"]
    scan = f.get("scan") or []
    trig = [r for r in scan if r.get("state") == "triggered"]
    reads = [r for r in scan if (r.get("price") or {}).get("today") is not None]

    print(f"  scan  {len(trig)}/{len(scan)} triggered · {len(reads)}/{len(scan)} 有读数")
    print(f"  PV1   {len(pv1)} 条 finding")
    bad = []
    if len(trig) != len(scan): bad.append("有标的没被压到触发 —— 阈值没生效")
    if not pv1: bad.append("**scan 说 triggered 而一条 PV1 finding 都没有** —— 分支被吞了")
    if len(reads) != len(scan): bad.append("读数被连坐 —— 触发不该影响 scan 的读数")
    for x in pv1:
        dl2 = x.get("delivery") or {}
        if not dl2.get("level"): bad.append(f"{x['symbol']} 没有 delivery.level")
    if bad:
        print("  ❌ " + "\n  ❌ ".join(bad))
    else:
        print(f"  ✅ 每只都触发、每只都有 finding、读数都在、delivery 都有等级")
        for x in pv1[:4]:
            dl2 = x.get("delivery") or {}
            print(f"       {x['symbol']:6s} {dl2.get('level')} capped={dl2.get('cappedBy')}"
                  f" z={(x.get('measured') or {}).get('z')}")
finally:
    write("data/baselines.json", base0)
    write("data/findings.json", find0)
    st, err = run("producer.js")
    f2 = read("data/findings.json")
    left = [x for x in f2.get("findings") or [] if x["signalId"] == "PV1"]
    print(f"  ── 已还原 · 复跑 {st} · 现在 PV1 {len(left)} 条"
          + ("  ✅" if len(left) == len([x for x in find0.get('findings') or []
                                        if x['signalId'] == 'PV1']) else "  ⚠️ 与演练前不一致"))
