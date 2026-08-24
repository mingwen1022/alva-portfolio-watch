"""MA 族核心批跑：92 美股 + 25 加密 × 全部事件集。

输出 out/core.json：
  per[sym][event] = dict(n, blocks, mult, lo, hi, pass_, mult_legacy, ...)
  norm[sym][event] = {date: 归一化 V}        供 M16 逐日配对用
"""
import sys, os, json, math, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import (build, zrob, rvol, ratio_ci, norm_V, to_trading, window_of, NBOOT)
from macro_calendar import first_release
from m15 import series as m15_series

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"

IND_MAIN = {
    "CPI": "CPI", "CORE_CPI": "CORE_CPI", "NFP": "TOTAL_NONFARM_PAYROLL",
    "UNRATE": "UNEMPLOYMENT_RATE", "GDP": "GDP", "FEDFUNDS": "FEDERAL_FUNDS",
}
# 事件集：name -> (发布日列表, 交易日平移)
def build_events():
    ev = {}
    cal = {k: [rd for rd, _, _ in first_release(v)] for k, v in IND_MAIN.items()}
    for k, rds in cal.items():
        ev[f"{k}_T0"] = (rds, 0)
        ev[f"{k}_T-1"] = (rds, -1)
    # MA2：|M15| >= θ 的发布日
    for k, ind in (("CPI", "CPI"), ("NFP", "TOTAL_NONFARM_PAYROLL")):
        for mode in ("literal", "delta"):
            ser = m15_series(ind, mode)
            for th in (1.5, 2.0):
                sel = [rd for rd, od, a, z in ser if z is not None and abs(z) >= th]
                ev[f"MA2_{k}_{mode}_{th}"] = (sel, 0)
    # 安慰剂平移：|k| >= 6 有效；小平移只作剖面（窗口污染）
    for base in ("CPI", "GDP", "NFP"):
        for k in (-10, -8, -6, -4, -2, -1, 1, 2, 4, 6, 8, 10):
            ev[f"PLACEBO_{base}_{k:+d}"] = (cal[base], k)
    return ev


def load_universe():
    us, cr = [], []
    for r in csv.DictReader(open(UNI)):
        if r["asset_class"] == "us_equity":
            us.append(r)
        else:
            cr.append(r)
    return us, cr


EV = build_events()
M16_EVENTS = ["CPI_T0", "CPI_T-1", "CORE_CPI_T0", "NFP_T0", "NFP_T-1", "GDP_T0", "FEDFUNDS_T0"]
LEGACY_EVENTS = ["CPI_T0", "CPI_T-1", "NFP_T0", "NFP_T-1", "GDP_T0", "GDP_T-1"]


def work(arg):
    sym, source = arg
    try:
        s = build(sym, source)
    except Exception as e:
        return sym, {"_err": str(e)}, {}
    w = window_of(s, LO, HI)
    if w is None:
        return sym, {"_err": "窗口不足"}, {}
    lo, hi = w
    res = {"_win": [s["dates"][lo], s["dates"][hi], hi - lo + 1]}
    nrm = {}
    for name, (rds, shift) in EV.items():
        T = sorted(set(i for i in (to_trading(s, rd, shift) for rd in rds)
                       if i is not None and lo <= i <= hi))
        if len(T) < 3:
            res[name] = None
            continue
        nb = NBOOT if not name.startswith("PLACEBO") else 2000
        r = ratio_ci(s, T, lo, hi, spec="r28", nboot=nb)
        if r is None:
            res[name] = None
            continue
        if name in LEGACY_EVENTS:
            rl = ratio_ci(s, T, lo, hi, spec="legacy", nboot=NBOOT)
            if rl:
                r["mult_legacy"] = rl["mult"]; r["lo_legacy"] = rl["lo"]
                r["hi_legacy"] = rl["hi"]; r["pass_legacy"] = rl["pass_"]
        res[name] = r
        if name in M16_EVENTS:
            nv, _ = norm_V(s, T, lo, hi)
            if nv is not None:
                nrm[name] = {s["dates"][i]: float(nv[i]) for i in T if not np.isnan(nv[i])}
    # PV1 阳性对照
    z = zrob(s); rv = rvol(s)
    thv = 3.0 if source == "crypto" else 2.0
    vlo = int(np.flatnonzero(~np.isnan(s["RV5"]) & ~np.isnan(s["sigma"]))[0])
    vhi = int(np.flatnonzero(~np.isnan(s["RV5"]) & ~np.isnan(s["sigma"]))[-1])
    T = [t for t in range(s["n"]) if not np.isnan(z[t]) and not np.isnan(rv[t])
         and abs(z[t]) >= 1.5 and rv[t] >= thv]
    r = ratio_ci(s, T, vlo, vhi, spec="r28")
    res["PV1_full"] = r
    T2 = [t for t in T if lo <= t <= hi]
    res["PV1_win"] = ratio_ci(s, T2, lo, hi, spec="r28")
    return sym, res, nrm


if __name__ == "__main__":
    us, cr = load_universe()
    jobs = [(r["symbol"], "uni") for r in us] + [(r["symbol"], "crypto") for r in cr]
    print(f"事件集 {len(EV)} 个 · 标的 {len(jobs)} 个", flush=True)
    per, norms = {}, {}
    with Pool(9) as p:
        for i, (sym, res, nrm) in enumerate(p.imap_unordered(work, jobs)):
            per[sym] = res; norms[sym] = nrm
            print(f"[{i+1}/{len(jobs)}] {sym}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(per, open(f"{OUT}/core.json", "w"))
    json.dump(norms, open(f"{OUT}/norms.json", "w"))
    json.dump({k: dict(n=len(v[0]), shift=v[1], dates=v[0]) for k, v in EV.items()},
              open(f"{OUT}/events.json", "w"))
    print("done")
