"""引擎自检：复现已过审核的 PV1 逐标的数字。
PV1 = |z_rob| >= 1.5 AND RVOL >= 2.0（股票），全样本 2018-01 起。
目标（CLAUDE.md §三）：XOM 2.70 [1.53,4.87] · NVDA 1.68 [1.40,2.41] · KO 1.30 [1.01,5.83]
                      · TSLA 1.21 [1.05,1.60] · SOFI 1.15 [0.90,1.40] ❌ · AAPL 1.97 [1.29,3.28]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from engine import build, zrob, rvol, ratio_ci

SYMS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "PLTR", "RIVN", "SOFI", "KO", "XOM", "MSTR"]

print(f"{'标的':6s} {'触发':>5s} {'块':>4s} | {'R28 口径':>22s} | {'legacy 口径':>22s}")
rows = []
for sym in SYMS:
    for src in ("legacy", "uni"):
        try:
            s = build(sym, src)
        except FileNotFoundError:
            continue
        z = zrob(s); rv = rvol(s)
        T = [t for t in range(s["n"])
             if not np.isnan(z[t]) and not np.isnan(rv[t]) and abs(z[t]) >= 1.5 and rv[t] >= 2.0]
        valid = np.flatnonzero(~np.isnan(s["RV5"]) & ~np.isnan(s["sigma"]))
        lo, hi = int(valid[0]), int(valid[-1])
        a = ratio_ci(s, T, lo, hi, spec="r28")
        b = ratio_ci(s, T, lo, hi, spec="legacy")
        tag = "老数据" if src == "legacy" else "新池   "
        print(f"{sym:6s} {tag} {a['n']:5d} {a['blocks']:4d} | "
              f"{a['mult']:6.2f} [{a['lo']:.2f}, {a['hi']:.2f}] {'✓' if a['pass_'] else '✗'} | "
              f"{b['mult']:6.2f} [{b['lo']:.2f}, {b['hi']:.2f}] {'✓' if b['pass_'] else '✗'}")
        rows.append((sym, src, a, b))

for spec, k in (("R28", 2), ("legacy", 3)):
    for src in ("legacy", "uni"):
        sel = [r for r in rows if r[1] == src]
        if sel:
            print(f"{spec:7s} {src:7s} 通过 {sum(1 for r in sel if r[k]['pass_'])}/{len(sel)}")
