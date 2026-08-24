import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, TIER
from collections import Counter, defaultdict

rows = load()
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
meta = {}
for l in open(os.path.join(D, "raw/registry_all.tsv"), encoding="utf-8"):
    p = l.rstrip("\n").split("\t")
    if p and p[0]: meta[p[0].lower()] = p

MONTHS = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13)]
MONTHS = [m for m in MONTHS if "2025-01" <= m <= "2026-08"]

by_h = defaultdict(list)
for r in rows: by_h[r["handle"]].append(r)

print(f"总条数 {len(rows):,}    覆盖窗 2025-01-01 → 2026-08-20\n")
print("## 账号覆盖\n")
print(f"{'账号':18}{'层':14}{'条数':>7}{'起':>12}{'止':>12}{'注册表 earliest':>16}{'密月起':>10}{'密月数':>7}")
plateau = {}
for t, hs in TIER.items():
    for h in hs:
        v = by_h.get(h, [])
        if not v:
            print(f"{h:18}{t:14}{0:>7}{'—':>12}{'—':>12}"); continue
        ts = sorted(x["ts"] for x in v)
        mc = Counter(x["ts"][:7] for x in v)
        ref = sorted(mc.values())[int(len(mc) * 0.75)] if len(mc) > 3 else max(mc.values())
        dense = [m for m in MONTHS if mc.get(m, 0) >= 0.4 * ref]
        # 最后一段连续密月
        run = []
        for m in reversed(MONTHS):
            if m in dense: run.append(m)
            else: break
        start = run[-1] if run else "—"
        plateau[h] = start
        eb = meta.get(h.lower(), [""] * 4)[2][:7] if h.lower() in meta else "?"
        print(f"{h:18}{t:14}{len(v):>7}{ts[0][:10]:>12}{ts[-1][:10]:>12}{eb:>16}{start:>10}{len(run):>7}")

print("\n## 每月总量（列 = 每 200 条一格）\n")
mc = Counter(r["ts"][:7] for r in rows)
for m in MONTHS: print(f"  {m}  {mc.get(m,0):>6,}  {'#'*int(mc.get(m,0)/200)}")

print("\n## 各账号逐月条数\n")
hs_all = [h for t in TIER for h in TIER[t] if by_h.get(h)]
print("账号".ljust(18) + "".join(m[2:].rjust(7) for m in MONTHS))
for h in hs_all:
    c = Counter(x["ts"][:7] for x in by_h[h])
    print(h.ljust(18) + "".join(str(c.get(m, 0)).rjust(7) for m in MONTHS))

print("\n## content_type\n")
for k, v in Counter(r["ctype"] for r in rows).most_common():
    print(f"  {k or '(空)':10}{v:>8,}  {v/len(rows):>6.1%}")
