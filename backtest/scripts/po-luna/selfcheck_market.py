"""市场确认模块自检 —— 先量出「随机时刻的确认率」这个底数，再谈帖子的确认率。

不标定底数就报「事实性帖子 30% 被确认」是没有意义的：判据 |AR_z|≥2 OR RVOL≥2
在肥尾 + 日内 U 型下本身就有相当高的无条件触发率。
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M

SYMS = ["NVDA", "AMD", "MSFT", "BTC", "ETH", "SOL"]
D0, D1 = 20260101, 20260820


def base_rate(sym):
    g = M.grid(sym); p = M.prep(sym)
    K, span = g["K"], p["span"]
    days = g["days"]
    sel = (days >= D0) & (days < D1)
    arz, rv, n = [], [], 0
    for d in np.flatnonzero(sel):
        for k in range(1, K - span + 1):
            r = p["R"][d, k]; s = p["sig"][d, k]
            if np.isnan(r) or np.isnan(s):
                continue
            rm = None if p["RM"] is None else p["RM"][d, k]
            if rm is not None and np.isnan(rm):
                continue
            ar = r - (0.0 if rm is None else p["beta"][d, k] * rm)
            z = ar / s
            vm, vv = p["volmed"][d, k], p["VOL"][d, k]
            q = vv / vm if (vm and vm > 0 and not np.isnan(vv)) else np.nan
            arz.append(z); rv.append(q); n += 1
    arz = np.array(arz); rv = np.array(rv)
    a = float(np.mean(np.abs(arz) >= 2.0))
    b = float(np.nanmean(rv >= 2.0))
    both = float(np.mean((np.abs(arz) >= 2.0) | ((~np.isnan(rv)) & (rv >= 2.0))))
    return dict(sym=sym, n=n, p_ar=a, p_rvol=b, p_or=both,
                med_absz=float(np.median(np.abs(arz))), med_rvol=float(np.nanmedian(rv)))


if __name__ == "__main__":
    print(f"{'标的':6}{'窗口数':>8}{'|AR_z|>=2':>11}{'RVOL>=2':>9}{'OR':>8}{'中位|z|':>9}{'中位RVOL':>10}")
    for s in SYMS:
        try:
            r = base_rate(s)
        except Exception as e:
            print(s, "ERR", repr(e)); continue
        print(f"{r['sym']:6}{r['n']:>8}{r['p_ar']:>11.1%}{r['p_rvol']:>9.1%}{r['p_or']:>8.1%}"
              f"{r['med_absz']:>9.2f}{r['med_rvol']:>10.2f}")
