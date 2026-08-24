"""切半翻号是期间效应还是噪声：逐年看配对差的跨标的中位"""
import json, os
import numpy as np
from scipy import stats
H = os.path.dirname(os.path.abspath(__file__))
P = [r for r in json.load(open(f"{H}/panel.json")) if "error" not in r]
RNG = np.random.default_rng(31)
YEARS = [str(y) for y in range(2018, 2027)]

def bmed(x, nb=8000):
    x = np.asarray(x, float)
    if len(x) < 3: return np.nan, np.nan, np.nan
    m = np.median(x[RNG.integers(0, len(x), size=(nb, len(x)))], axis=1); m.sort()
    return float(np.median(x)), float(m[int(.025*nb)]), float(m[int(.975*nb)])

for other in ("price_eq", "or_eq"):
    for nm in ("cb", "np"):
        print(f"\n── AND − {other} · 分母 {nm} · 逐年跨标的配对差中位 ──")
        rows = []
        for y in YEARS:
            d = []
            for r in P:
                c = r["panel"].get(y, {})
                ka, ko = f"and_base_{nm}", f"{other}_{nm}"
                if ka in c and ko in c: d.append(c[ka] - c[ko])
            if len(d) < 8: 
                print(f"  {y}  n={len(d):<4} 样本不足"); continue
            m, lo, hi = bmed(d)
            k = int((np.array(d) > 0).sum())
            rows.append((int(y), m, len(d)))
            print(f"  {y}  n={len(d):<4} 配对差 {m:>+7.3f} [{lo:+.3f},{hi:+.3f}]  AND 赢 {k}/{len(d)} = {k/len(d):.0%}")
        if len(rows) >= 5:
            ys = np.array([r[0] for r in rows]); ms = np.array([r[1] for r in rows])
            w = np.array([r[2] for r in rows], float)
            sp = stats.spearmanr(ys, ms)
            lr = stats.linregress(ys, ms)
            print(f"  年份 vs 配对差  Spearman {sp.statistic:+.3f} (p={sp.pvalue:.3f})  "
                  f"线性斜率 {lr.slope:+.4f}/年 (p={lr.pvalue:.3f})")
            neg = sum(1 for _, m, _ in rows if m < 0); pos = len(rows) - neg
            print(f"  {len(rows)} 个年份里 {neg} 年为负 / {pos} 年为正")
