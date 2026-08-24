"""④ 加密 vs 美股的分化：截面相关 → 有效独立样本量 → 按年整块自助"""
import json, os, itertools
import numpy as np
from scipy import stats

H = os.path.dirname(os.path.abspath(__file__))
P = [r for r in json.load(open(f"{H}/panel.json")) if "error" not in r]
R = {r["sym"]: r for r in json.load(open(f"{H}/res.json")) if "error" not in r}
YEARS = [str(y) for y in range(2018, 2027)]
RNG = np.random.default_rng(23)


def build(other="price_eq", nm="cb"):
    """返回 dict sym -> {year: 配对差}，以及标的属性"""
    out = {}
    for r in P:
        d = {}
        for y, c in r["panel"].items():
            ka, ko = f"and_base_{nm}", f"{other}_{nm}"
            if ka in c and ko in c:
                d[y] = c[ka] - c[ko]
        if d: out[r["sym"]] = d
    return out


def mean_pairwise_corr(panel, syms, min_overlap=4):
    cs = []
    for a, b in itertools.combinations(syms, 2):
        ya = panel.get(a, {}); yb = panel.get(b, {})
        com = sorted(set(ya) & set(yb))
        if len(com) < min_overlap: continue
        x = np.array([ya[y] for y in com]); z = np.array([yb[y] for y in com])
        if x.std() == 0 or z.std() == 0: continue
        cs.append(np.corrcoef(x, z)[0, 1])
    return (float(np.mean(cs)), float(np.median(cs)), len(cs)) if cs else (np.nan, np.nan, 0)


def year_block_boot(panel, syms, nboot=20000):
    """按年整块自助：每次抽一组年份，逐标的在抽中的年上取均值，再取跨标的中位"""
    ys = YEARS
    reps = []
    for _ in range(nboot):
        pick = [ys[i] for i in RNG.integers(0, len(ys), len(ys))]
        vals = []
        for s in syms:
            d = panel.get(s, {})
            v = [d[y] for y in pick if y in d]
            if v: vals.append(np.mean(v))
        if vals: reps.append(np.median(vals))
    reps = np.sort(np.array(reps))
    return float(np.median(reps)), float(reps[int(.025*len(reps))]), float(reps[int(.975*len(reps))])


def hdr(t): print("\n" + "="*80); print(t); print("="*80)


hdr("④ 加密 vs 美股：配对差在截面上有多相关，25 只加密相当于几只独立标的")
for other in ("price_eq", "or_eq"):
    for nm in ("cb", "np"):
        pan = build(other, nm)
        cry = [s for s in pan if R[s]["asset"] == "crypto"]
        eqy = [s for s in pan if R[s]["asset"] != "crypto"]
        print(f"\n  ── 对照 {other} · 分母 {nm} ──")
        for lab, syms in (("加密", cry), ("美股", eqy)):
            mc, mdc, npair = mean_pairwise_corr(pan, syms)
            n = len(syms)
            deff = 1 + (n - 1) * max(mc, 0)
            neff = n / deff
            # 逐标的全样本配对差（来自 res.json，口径与 §2 一致）
            key = "mult_cb" if nm == "cb" else "mult_np"
            fd = [R[s]["arms"]["and_base"][key] - R[s]["arms"][other][key]
                  for s in syms
                  if R[s]["arms"]["and_base"].get(key) is not None
                  and R[s]["arms"][other].get(key) is not None]
            fd = np.array(fd)
            k = int((fd > 0).sum()); nn = len(fd)
            p_naive = stats.binomtest(k, nn, .5).pvalue
            keff = int(round(k / nn * max(neff, 2)))
            p_eff = stats.binomtest(keff, int(round(max(neff, 2))), .5).pvalue
            m, lo, hi = year_block_boot(pan, syms)
            print(f"    {lab}  n={n}  平均两两相关 {mc:+.3f}（中位 {mdc:+.3f}，{npair} 对）"
                  f"  设计效应 {deff:.1f}  有效独立样本 n_eff ≈ {neff:.1f}")
            print(f"       全样本配对差中位 {np.median(fd):+.3f}  AND 赢 {k}/{nn} = {k/nn:.0%}"
                  f"  朴素 p={p_naive:.3f}  按 n_eff 折算 p={p_eff:.3f}")
            print(f"       按年整块自助（吃掉共同年份冲击）：{m:+.3f} [{lo:+.3f}, {hi:+.3f}]"
                  f"  {'不含 0' if lo*hi>0 else '含 0'}")

hdr("④b 加密与美股的差异本身是否稳健（按年整块自助的差）")
for other in ("price_eq", "or_eq"):
    for nm in ("cb", "np"):
        pan = build(other, nm)
        cry = [s for s in pan if R[s]["asset"] == "crypto"]
        eqy = [s for s in pan if R[s]["asset"] != "crypto"]
        reps = []
        for _ in range(10000):
            pick = [YEARS[i] for i in RNG.integers(0, len(YEARS), len(YEARS))]
            def med(syms):
                vals = []
                for s in syms:
                    d = pan.get(s, {}); v = [d[y] for y in pick if y in d]
                    if v: vals.append(np.mean(v))
                return np.median(vals) if vals else np.nan
            reps.append(med(cry) - med(eqy))
        reps = np.sort(np.array([x for x in reps if np.isfinite(x)]))
        m, lo, hi = np.median(reps), reps[int(.025*len(reps))], reps[int(.975*len(reps))]
        frac = float((reps > 0).mean())
        print(f"  {other:<10} {nm}: 加密 − 美股 = {m:+.3f} [{lo:+.3f}, {hi:+.3f}]"
              f"  自助中 >0 的比例 {frac:.1%}  {'稳健' if lo>0 else '不稳健'}")

hdr("④c 加密里 AND 的优势是不是「θv=3.0 更严」而不是「加密不一样」")
# 加密 θv=3.0，美股 2.0。用触发率对比：AND 触发日占比
for lab, f in (("加密", lambda s: R[s]["asset"] == "crypto"), ("美股", lambda s: R[s]["asset"] != "crypto")):
    rho = [R[s]["arms"]["and_base"]["n"] / R[s]["n_elig"] for s in R if f(s)]
    rv = [R[s]["arms"]["and_base"]["med_rvol"] for s in R if f(s)]
    print(f"  {lab}: AND 触发日占比 中位 {np.median(rho):.2%}  触发日 RVOL 中位 {np.median(rv):.2f}")
# 高波美股 vs 加密
hi_eq = [s for s in R if R[s]["asset"] != "crypto" and R[s]["vol_tier"] == "高波 >50%"]
hi_cr = [s for s in R if R[s]["asset"] == "crypto" and R[s]["vol_tier"] == "高波 >50%"]
for lab, syms in (("高波·美股", hi_eq), ("高波·加密", hi_cr)):
    d = np.array([R[s]["arms"]["and_base"]["mult_cb"] - R[s]["arms"]["price_eq"]["mult_cb"]
                  for s in syms if R[s]["arms"]["price_eq"].get("mult_cb") is not None])
    if len(d) < 3: continue
    k = int((d > 0).sum())
    print(f"  {lab} n={len(d)} 配对差中位 {np.median(d):+.3f} AND 赢 {k}/{len(d)}"
          f" p={stats.binomtest(k,len(d),.5).pvalue:.3f}")
