"""FOMC 探索检验的稳健性：剔 2020 年（疫情 + 两次临时会议）后是否还在。"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, ratio_ci, window_of, to_trading
from run_fomc import FOMC, LO, HI

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"

SETS = {
    "全部 54 次": FOMC,
    "剔 2020 年（46 次）": [d for d in FOMC if d[:4] != "2020"],
    "只留定期会（剔 2020-03-03/15）": [d for d in FOMC if d not in ("2020-03-03", "2020-03-15")],
    "2022 起（32 次）": [d for d in FOMC if d >= "2022-01-01"],
}


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
    for k, days in SETS.items():
        T = sorted(set(i for i in (to_trading(s, d, 0) for d in days)
                       if i is not None and lo <= i <= hi))
        r = ratio_ci(s, T, lo, hi, spec="r28", nboot=2000)
        out[k] = None if r is None else dict(mult=r["mult"], lo=r["lo"], hi=r["hi"],
                                             n=r["n"], blocks=r["blocks"], pass_=r["pass_"])
    return sym, out


if __name__ == "__main__":
    U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
    jobs = [(s, "uni") for s in U if U[s]["asset_class"] == "us_equity" and s != "SPY"]
    res = {}
    with Pool(9) as p:
        for o in p.imap_unordered(work, jobs):
            if o: res[o[0]] = o[1]
    json.dump(res, open(f"{OUT}/fomc_rob.json", "w"), ensure_ascii=False)
    RATE = {"金融", "房地产", "公用事业"}
    for k in SETS:
        v = [res[s][k] for s in res if res[s].get(k)]
        m = np.array([x["mult"] for x in v])
        a = [res[s][k] for s in res if res[s].get(k) and U[s]["sector"] in RATE]
        b = [res[s][k] for s in res if res[s].get(k) and U[s]["sector"] not in RATE]
        print(f"{k:26s} 触发中位 {int(np.median([x['n'] for x in v])):3d} 倍数中位 {np.median(m):.3f} "
              f"通过 {sum(1 for x in v if x['pass_']):2d}/{len(v)}  |  利率敏感 {np.median([x['mult'] for x in a]):.3f} "
              f"({sum(1 for x in a if x['pass_'])}/{len(a)})  其余 {np.median([x['mult'] for x in b]):.3f} "
              f"({sum(1 for x in b if x['pass_'])}/{len(b)})")
