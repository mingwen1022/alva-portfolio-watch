"""PO3 与 PO4 的信号级检验：M16 那一层到底拦没拦下东西、有没有增量。

PO3  M24 ∧ M16高敏 ∧ M19新 ∧ 确认
PO4  (M17∨M24) ∧ 主题敞口匹配 ∧ M19新 ∧ 确认
"""
import sys, json
import numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid, stratlib as S, port_defs
from an1_theme import to_ep, blockboot
from an3_oos import fit_S1, score

recs, cp = polib.load()
ev = polib.dedup_events(recs)
G = confgrid.Grid()
eps = np.array([to_ep(r["ts"]) for r in ev])
days = np.array([r["day"] for r in ev])
et = np.array([r["etype"] for r in ev])
m17 = np.array([r["m17"] for r in ev]); m24 = np.array([r["m24"] for r in ev])
half = np.array([polib.half(r) for r in ev])
lay = np.array([r["layer"] for r in ev])
ALL = np.ones(len(ev), bool)
basis = [p for p in G.names() if p.startswith("B:")]
meta = json.load(open("grid_meta.json"))
u = {r["symbol"]: r["sector"] for r in port_defs.load_universe()}

# ---------- M16-C：registry 现行规则 β_组合 > 1.2 或 加密占比 > 20% ----------
import market as M2
print("=" * 78); print("M16-C（registry 现行）逐组合判定"); print("=" * 78)
verdict = {}
for p in G.names():
    mem = meta[p]["members"]
    if p.endswith("加密") or all(m in [r["symbol"] for r in port_defs.load_universe() if r["sector"] == "加密"] for m in mem):
        verdict[p] = ("高敏", "E_加密=100% > 20%")
        continue
    bs = []
    for s in mem:
        pr = M2.prep(s)
        b = pr["beta"][~np.isnan(pr["beta"])]
        bs.append(float(np.median(b)) if len(b) else np.nan)
    bp = float(np.nanmean(bs))
    verdict[p] = ("高敏" if bp > 1.2 else "低敏", f"β_组合={bp:.2f}")
for p in sorted(verdict):
    print(f"  {p:10} {verdict[p][0]}  ({verdict[p][1]})")
hi = [p for p in basis if verdict[p][0] == "高敏"]; lo = [p for p in basis if verdict[p][0] == "低敏"]
print(f"  基础组合中 高敏 {len(hi)} 个 · 低敏 {len(lo)} 个")

# ---------- PO3：M24 路上，M16-C 高敏 vs 低敏 的确认率 ----------
print(); print("=" * 78); print("PO3 · M24 路：M16-C 高敏组合 vs 低敏组合（同一批事件，跨组合比较）"); print("=" * 78)
only24 = m24 & ~m17
for lname, lm in (("全部", ALL), ("TierA", np.isin(lay, ["main18", "cb4"])), ("media7", lay == "media7")):
    pool = lm & only24
    rs = {}
    for p in basis:
        v, c, k = S.locate(G, p, eps)
        vv = v & pool
        if vv.sum() < 40: continue
        rs[p] = (float(c[vv].mean()), int(vv.sum()))
    if not rs: continue
    rh = [rs[p][0] for p in hi if p in rs]; rl = [rs[p][0] for p in lo if p in rs]
    print(f"  {lname:8} 仅M24事件 n≈{list(rs.values())[0][1]:>5}   高敏组合确认率中位 {np.median(rh):6.2%}   低敏 {np.median(rl):6.2%}   差 {(np.median(rh)-np.median(rl))*100:+5.2f}pp")
print("  ⚠️ 该对比跨组合，受组合自身波动水平影响，不是判据；判据看下面的组合内对比。")

print(); print("=" * 78); print("PO3 · 组合内：仅M24 事件 vs 全部候选（同分母，分层口径）"); print("=" * 78)
for lname, lm in (("全部", ALL), ("TierA", np.isin(lay, ["main18", "cb4"])), ("media7", lay == "media7")):
    rows = {}
    for p in basis:
        r = S.strat_cell(G, p, only24, lm, eps, days, nboot=800)
        if r: rows[p] = r
    k = sum(1 for r in rows.values() if r["pass"])
    print(f"  {lname:8} 通过 {k}/{len(rows)}  Δ中位 {np.median([r['d'] for r in rows.values()])*100:+6.2f}pp")

print(); print("=" * 78); print("PO3 vs PO4 · 两条相关性路径的增量（M17 路 vs 仅M24 路，组合内同分母）"); print("=" * 78)
for lname, lm in (("全部", ALL), ("TierA", np.isin(lay, ["main18", "cb4"]))):
    for armname, arm in (("M17命中", m17), ("仅M24", only24), ("M17∨M24=全体", m17 | m24)):
        rows = {}
        for p in basis:
            r = S.strat_cell(G, p, arm, lm, eps, days, nboot=600)
            if r: rows[p] = r
        if not rows: continue
        k = sum(1 for r in rows.values() if r["pass"])
        print(f"  {lname:8} {armname:14} 通过 {k}/{len(rows)}  Δ中位 {np.median([r['d'] for r in rows.values()])*100:+6.2f}pp")

print(); print("=" * 78); print("PO4 · 主题匹配 在 M17∨M24 命中集内的增量（这是 PO4 真正的问句）"); print("=" * 78)
for lname, lm in (("全部", ALL), ("TierA", np.isin(lay, ["main18", "cb4"])), ("media7", lay == "media7")):
    for hn, hm in (("H1", half == "H1"), ("H2", half == "H2")):
        rows = {}
        for p in basis:
            sec = p[2:]
            arm = np.array([sec in r["secs"] for r in ev])
            r = S.strat_cell(G, p, arm, lm & hm & (m17 | m24), eps, days, nboot=800)
            if r: rows[p] = r
        if not rows: continue
        k = sum(1 for r in rows.values() if r["pass"])
        print(f"  {lname:8} {hn}  通过 {k}/{len(rows)}  Δ中位 {np.median([r['d'] for r in rows.values()])*100:+6.2f}pp")
