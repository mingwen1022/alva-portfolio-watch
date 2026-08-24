"""等强度对照 —— PO3「等市场确认」到底比「市场刚动了一下」多给了什么。

问题：条件在「市场确认」上再去测后续波动，测到的多半是**波动聚集**，不是政策信息。
盘中 PV1 已经证明「刚动过的 bar 后面更动荡」。所以必须做等强度对照：

  A 组  该标的在该 bar 被确认（|AR_z|≥2 或 RVOL≥2）**且**该 bar 上有 M24 帖子
  B 组  该标的在该 bar 被确认**且**前后 ±2 根 bar 内没有任何候选帖子

两组的触发格与前瞻窗完全同构（trigger = 确认 bar + 1，窗 = +2..+6）。
若 A ≈ B，PO3 的「等确认」等于把 PV1 换了个名字。
"""
import os, sys, json, gzip
import numpy as np
import multiprocessing as mp
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crit, market as M

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")
REPS = 20
D0, D1 = crit.D0, crit.D1


def confirmed_bars(sym, crypto):
    """该标的每个 bar 是否满足确认判据（与 market.py 同一套 AR_z / RVOL）。
    返回 dict[(daykey, k)] = True。"""
    g = M.grid(sym); p = M.prep(sym)
    K, span = g["K"], p["span"]
    out = set()
    days = g["days"]
    for d in range(g["D"]):
        if not (D0 <= days[d] < D1):
            continue
        for k in range(1, K - span + 1):
            r, s = p["R"][d, k], p["sig"][d, k]
            if np.isnan(r) or np.isnan(s):
                continue
            rm = None if p["RM"] is None else p["RM"][d, k]
            if rm is not None and np.isnan(rm):
                continue
            ar = r - (0.0 if rm is None else p["beta"][d, k] * rm)
            z = ar / s
            vm, vv = p["volmed"][d, k], p["VOL"][d, k]
            q = vv / vm if (vm and vm > 0 and not np.isnan(vv)) else np.nan
            if abs(z) >= 2.0 or ((not np.isnan(q)) and q >= 2.0):
                out.add((int(days[d]), k))
    return out


def post_cells(eps, crypto):
    day, kstar, _ = crit.post_slots(eps, crypto)
    return {(int(d), int(k)) for d, k in zip(day, kstar)}


def run_one(args):
    sym, crypto, eps, seed = args
    P = crit.load(sym, crypto)
    K = int(P["nslots"])
    d_of = {int(d): i for i, d in enumerate(P["days"])}
    conf = confirmed_bars(sym, crypto)
    pcells = post_cells(eps, crypto)
    pdays = {}
    for d, k in pcells:
        pdays.setdefault(d, set()).add(k)

    def mask(cells):
        tm = np.zeros((len(P["days"]), K), bool)
        for d, k in cells:
            i = d_of.get(d)
            if i is None:
                continue
            j = k + 1                       # trigger = 确认 bar + 1 → 窗 = +2..+6
            if 0 <= j < K:
                tm[i, j] = True
        return tm

    A = [c for c in conf if c in pcells]
    B = [c for c in conf if not any((c[1] + o) in pdays.get(c[0], ()) for o in (-2, -1, 0, 1, 2))]
    if len(A) < 5 or len(B) < len(A):
        return None
    ra = crit.run_sym(P, mask(A), nboot=1000)
    rng = np.random.default_rng(seed)
    reps = []
    for _ in range(REPS):
        idx = rng.choice(len(B), size=len(A), replace=False)
        rb = crit.run_sym(P, mask([B[i] for i in idx]), nboot=400)
        if rb:
            reps.append(rb)
    if not ra or not reps:
        return None
    return dict(sym=sym, asset="crypto" if crypto else "us_equity",
                nA=len(A), nB=len(B), A_mult=ra["mult"], A_lo=ra["lo"], A_pass=ra["pass_"],
                B_mult=float(np.mean([x["mult"] for x in reps])),
                B_mult_p95=float(np.percentile([x["mult"] for x in reps], 95)),
                B_pass=float(np.mean([x["pass_"] for x in reps])))


def main():
    ts = json.load(open(f"{DERIV}/trigsets_nollm.json"))
    eps = ts["M24only_tierA"]
    k = crit.kinds()
    jobs = [(s, v == "crypto", eps, 20260819) for s, v in sorted(k.items())]
    pool = Pool(9)
    res = [r for r in pool.map(run_one, jobs) if r]
    pool.close()
    json.dump(res, open(f"{DERIV}/control_intensity.json", "w"), indent=1)
    for asset in ("crypto", "us_equity"):
        sub = [r for r in res if r["asset"] == asset]
        if not sub:
            continue
        print(f"\n{asset}  n={len(sub)} 个标的")
        print(f"  A 组（确认 ∧ 有 M24 帖）倍数中位 {np.median([r['A_mult'] for r in sub]):.3f}  通过 {np.mean([r['A_pass'] for r in sub]):.1%}")
        print(f"  B 组（确认 ∧ 无帖，等触发数）倍数中位 {np.median([r['B_mult'] for r in sub]):.3f}  通过 {np.mean([r['B_pass'] for r in sub]):.1%}")
        d = [r["A_mult"] - r["B_mult"] for r in sub]
        print(f"  配对差 A−B 中位 {np.median(d):+.3f}   A>B 的标的 {sum(1 for x in d if x>0)}/{len(d)}")
        print(f"  触发数中位 A {np.median([r['nA'] for r in sub]):.0f} · 可选 B {np.median([r['nB'] for r in sub]):.0f}")


if __name__ == "__main__":
    mp.set_start_method("fork", force=True)
    main()
