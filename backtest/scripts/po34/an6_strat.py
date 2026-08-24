"""分层口径下重跑：位置安慰剂 · M16-A 主题重叠 · monetary→加密 · M16-B 样本外。"""
import sys, json, datetime as dt
import numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid, stratlib as S, port_defs
from an1_theme import to_ep
from an3_oos import fit_S1, score, ETS

recs, cp = polib.load()
ev = polib.dedup_events(recs)
G = confgrid.Grid()
eps0 = np.array([to_ep(r["ts"]) for r in ev])
et = np.array([r["etype"] for r in ev])
days = np.array([r["day"] for r in ev])
half = np.array([polib.half(r) for r in ev])
ALL = np.ones(len(ev), bool)
basis = [p for p in G.names() if p.startswith("B:")]
hold = [p for p in G.names() if p.startswith("H:")]
meta = json.load(open("grid_meta.json"))
u = {r["symbol"]: r["sector"] for r in port_defs.load_universe()}

print("=" * 78); print("④' 位置安慰剂 —— 分层口径下重跑"); print("=" * 78)
dts = [dt.datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ") for r in ev]
dom = np.array([d.day for d in dts]); wd = np.array([d.weekday() for d in dts]); hr = np.array([d.hour for d in dts])
mlen = np.array([[31,28,31,30,31,30,31,31,30,31,30,31][d.month-1] for d in dts]); pos = dom / mlen
rules = {"月内前三分之一": pos <= 1/3, "月内中三分之一": (pos > 1/3) & (pos <= 2/3), "月内后三分之一": pos > 2/3,
         "月末最后5日": (mlen - dom) < 5, "月初前5日": dom <= 5,
         "周一": wd == 0, "周二": wd == 1, "周三": wd == 2, "周四": wd == 3, "周五": wd == 4,
         "盘前时段(UTC<14)": hr < 14, "午后(UTC>=18)": hr >= 18}
tot = pas = 0
for nm, m in rules.items():
    rs = [S.strat_cell(G, p, m, ALL, eps0, days, nboot=600) for p in basis]
    rs = [r for r in rs if r]
    k = sum(1 for r in rs if r["pass"]); tot += len(rs); pas += k
    print(f"  {nm:16} {k:>3}/{len(rs):<4}  Δ中位 {np.median([r['d'] for r in rs])*100:+6.2f}pp")
print(f"  合计 {pas}/{tot} = {pas/tot:.1%}   ← 分层后的位置类经验零")

print(); print("=" * 78); print("①' M16-A 主题重叠 —— 分层口径"); print("=" * 78)
for hn, hm in (("H1", half == "H1"), ("H2", half == "H2"), ("全期", ALL)):
    rows = {}
    for p in basis:
        sec = p[2:]
        arm = np.array([sec in r["secs"] for r in ev])
        r = S.strat_cell(G, p, arm, hm, eps0, days, nboot=800)
        if r: rows[p] = r
    k = sum(1 for r in rows.values() if r["pass"])
    print(f"  {hn:4} 通过 {k}/{len(rows)}   Δ中位 {np.median([r['d'] for r in rows.values()])*100:+6.2f}pp")
    for p, r in sorted(rows.items(), key=lambda x: -x[1]["d"])[:4]:
        print(f"       {p:10} n匹配={r['n1']:>5} Δ={r['d']*100:+6.2f}pp CI[{r['lo']*100:+6.2f},{r['hi']*100:+6.2f}]{' ✅' if r['pass'] else ''}")

print(); print("=" * 78); print("②' monetary → 加密 —— 分层口径 + 平移安慰剂"); print("=" * 78)
CRY = ["B:加密", "H:HC1", "H:HC2", "H:HC3", "H:HC4"]
for p in CRY:
    s = f"  {p:8}"
    for hn, hm in (("H1", half == "H1"), ("H2", half == "H2"), ("全期", ALL)):
        r = S.strat_cell(G, p, et == "monetary", hm, eps0, days, nboot=1200)
        s += f" | {hn} Δ={r['d']*100:+5.2f} CI[{r['lo']*100:+5.2f},{r['hi']*100:+5.2f}]{'✅' if r['pass'] else '  '}" if r else " | --"
    print(s)
obs = S.strat_cell(G, "B:加密", et == "monetary", ALL, eps0, days, nboot=1200)
nul = []
for sh in [-7 * k for k in range(1, 26)]:
    r = S.strat_cell(G, "B:加密", et == "monetary", ALL, eps0 + sh * 86400, days, boot=False)
    if r: nul.append(r["d"])
nul = np.array(nul)
print(f"  实测 Δ={obs['d']*100:+.2f}pp  安慰剂均值 {nul.mean()*100:+.2f}pp  sd {nul.std()*100:.2f}  "
      f"安慰剂中 ≥实测 {np.mean(nul >= obs['d']):.1%} (n={len(nul)})")

print(); print("=" * 78); print("③' M16-B 样本外 —— 分层口径"); print("=" * 78)
PORTS = {p: meta[p]["members"] for p in G.names()}
for ln, lf in (("全部", lambda r: True), ("TierA", lambda r: r["layer"] in ("main18", "cb4")),
               ("media7", lambda r: r["layer"] == "media7")):
    S1 = fit_S1(ev, G, eps0, lambda r: lf(r) and polib.half(r) == "H1", basis)
    m2 = np.array([lf(r) and polib.half(r) == "H2" for r in ev])
    rb = {}; rh = {}
    for p, mem in PORTS.items():
        sc = np.array([score(S1, e, mem, u) for e in et])
        r = S.strat_cell(G, p, sc > 0, m2, eps0, days, nboot=800)
        if r: (rb if p.startswith("B:") else rh)[p] = r
    kb = sum(1 for r in rb.values() if r["pass"]); kh = sum(1 for r in rh.values() if r["pass"])
    print(f"  {ln:8} 基础 {kb}/{len(rb)}  Δ中位 {np.median([r['d'] for r in rb.values()])*100:+6.2f}pp   "
          f"留出 {kh}/{len(rh)}  Δ中位 {np.median([r['d'] for r in rh.values()])*100:+6.2f}pp")
