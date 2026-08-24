"""FOMC（手工录入日历）的安慰剂平移与日历位置检查。"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, ratio_ci, window_of, to_trading
from run_fomc import FOMC, LO, HI
from run_calpos import tdom

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
SHIFTS = [-10, -8, -6, -1, 0, 1, 6, 8, 10]


def work(arg):
    sym, source = arg
    try:
        s = build(sym, source)
    except Exception:
        return None
    w = window_of(s, LO, HI)
    if w is None:
        return None
    lo, hi = w
    out = {}
    for sh in SHIFTS:
        T = sorted(set(i for i in (to_trading(s, d, sh) for d in FOMC)
                       if i is not None and lo <= i <= hi))
        r = ratio_ci(s, T, lo, hi, spec="r28", nboot=2000)
        out[sh] = None if r is None else dict(mult=r["mult"], lo=r["lo"], hi=r["hi"],
                                              n=r["n"], blocks=r["blocks"], pass_=r["pass_"])
    return sym, out


if __name__ == "__main__":
    U = [r for r in csv.DictReader(open(UNI))]
    jobs = [(r["symbol"], "uni") for r in U if r["asset_class"] == "us_equity" and r["symbol"] != "SPY"]
    res = {}
    with Pool(9) as p:
        for o in p.imap_unordered(work, jobs):
            if o: res[o[0]] = o[1]
    json.dump(res, open(f"{OUT}/fomc_placebo.json", "w"))
    print("平移 k    " + " ".join(f"{k:+7d}" for k in SHIFTS))
    print("倍数中位  " + " ".join(
        f"{np.median([res[s][k]['mult'] for s in res if res[s].get(k)]):7.3f}" for k in SHIFTS))
    print("通过数    " + " ".join(
        f"{sum(1 for s in res if (res[s].get(k) or {}).get('pass_')):7d}" for k in SHIFTS))
    s = build("AAPL", "uni"); lo, hi = window_of(s, LO, HI); pos = tdom(s["dates"], lo, hi)
    for sh in SHIFTS:
        ii = [to_trading(s, d, sh) for d in FOMC]
        p1 = [pos[i][0] for i in ii if i is not None and i in pos]
        p2 = [pos[i][1] for i in ii if i is not None and i in pos]
        print(f"  k={sh:+3d} 月内位置中位 第 {np.median(p1):4.1f} 个 · 倒数第 {abs(np.median(p2)):4.1f} 个  "
              f"落在月末3日或月初1日 {np.mean([(a <= 1 or b >= -3) for a, b in zip(p1, p2)])*100:4.0f}%")
