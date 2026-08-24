"""引擎自检：把盘中引擎降到 slot=1（日线）复现已审核数字
期望 XOM 2.70 [1.53,4.87] · SOFI 1.15 [0.90,1.40] 不通过"""
import csv, sys, numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run/scripts")
from engine import (build_grid, indicators, fwd_vol, trigger, ratio_ci,
                    sigma_decile, purge_fixed)

DAILY = "/Users/ming/project/alva/backtest/universe/data/daily"
CRY   = "/Users/ming/project/alva/backtest/universe/data/crypto"

def load(sym, crypto=False):
    ds, cs, vs = [], [], []
    for row in csv.DictReader(open(f"{CRY if crypto else DAILY}/{sym}.csv")):
        try: c = float(row["close"]); v = float(row["volume"])
        except (TypeError, ValueError): continue
        ds.append(row["date"]); cs.append(c); vs.append(v)
    o = np.argsort(ds)
    return np.array(cs)[o], np.array(vs)[o]

def run(sym, thv=2.0, crypto=False, nboot=4000):
    c, v = load(sym, crypto)
    D = len(c)
    C = c.reshape(D, 1); V = v.reshape(D, 1)
    ind = indicators(C, V, 1, cum_rvol=True)
    Vw, L = fwd_vol(ind["r"], 5, session_bound=False, mode="fixed")
    Vw[np.isnan(ind["sigma"])] = np.nan
    valid = (~np.isnan(Vw)) & (~np.isnan(ind["sigma"]))
    cell = sigma_decile(ind["sigma"], valid)
    tm = trigger(ind, 1.5, thv) & valid
    pm = purge_fixed(tm, 5)
    return ratio_ci(Vw, cell, tm, pm, nboot=nboot, block_gap=5)

if __name__ == "__main__":
    print(f"{'标的':<7}{'触发':>6}{'块':>5}{'倍数':>8}{'区间':>20}  判定")
    for sym, exp in [("XOM","2.70 [1.53,4.87]"), ("SOFI","1.15 [0.90,1.40]"),
                     ("NVDA","1.68 [1.40,2.41]"), ("KO","1.30 [1.01,5.83]"),
                     ("TSLA","1.21 [1.05,1.60]")]:
        r = run(sym)
        print(f"{sym:<7}{r['n']:>6}{r['blocks']:>5}{r['mult']:>8.2f}"
              f"   [{r['lo']:.2f}, {r['hi']:.2f}]   {'🟢' if r['pass_'] else '❌'}   期望 {exp}")

# ---- 旧口径（R28 之前）：V 除以 sigma_rob · 全局基准 · 不净化 · 不分层 ----
def run_legacy(sym, thv=2.0, nboot=4000, seed=20260819):
    import numpy as np
    from engine import indicators, fwd_vol, trigger
    c, v = load(sym)
    D = len(c); C = c.reshape(D,1); Vg = v.reshape(D,1)
    ind = indicators(C, Vg, 1, cum_rvol=True)
    Vw,_ = fwd_vol(ind["r"], 5, session_bound=False, mode="fixed")
    sig = ind["sigma"].reshape(-1); Vf = Vw.reshape(-1)
    ratio_day = Vf/sig
    valid = ~np.isnan(ratio_day)
    tm = (trigger(ind,1.5,thv)).reshape(-1) & valid
    T = np.flatnonzero(tm); N = np.flatnonzero(valid & ~tm)
    base = float(np.median(ratio_day[N]))
    point = float(np.median(ratio_day[T]))/base
    # 整块自助（块 = 相邻触发间隔 <5）
    bl,cur=[],[T[0]]
    for i in T[1:]:
        if i-cur[-1]<5: cur.append(i)
        else: bl.append(np.array(cur)); cur=[i]
    bl.append(np.array(cur))
    rng=np.random.default_rng(seed); nb=len(bl); reps=np.empty(nboot)
    blv=[ratio_day[b] for b in bl]
    for b in range(nboot):
        pick=rng.integers(0,nb,nb)
        vv=np.concatenate([blv[j] for j in pick])
        nn=rng.integers(0,len(N),len(N))
        reps[b]=np.median(vv)/np.median(ratio_day[N[nn]])
    reps.sort()
    return dict(n=len(T),blocks=nb,mult=point,lo=float(reps[int(.025*nboot)]),hi=float(reps[int(.975*nboot)]))
