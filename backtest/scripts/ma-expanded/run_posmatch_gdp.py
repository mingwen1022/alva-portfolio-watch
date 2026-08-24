"""日历位置匹配安慰剂：把每个触发日换成「往前 3 个月的同一个月内序位」。

普通安慰剂（平移 k 个交易日）会改变月内位置，因此测不出「效应是不是月内位置带的」。
位置匹配安慰剂保持月内序位不变、只换月份，两者之差才是事件本身的增量。
"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, ratio_ci, window_of, to_trading
from macro_calendar import first_release
from run_fomc import FOMC

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"

EVSETS = {
    "产出 GDP": [rd for rd, _, _ in first_release("GDP")],
}
OFFSETS = [0, -1, -2, 1, 2]


def month_map(dates, lo, hi):
    """-> {ym: [下标...]}, 每个下标 -> (ym, 序位, 倒数序位)"""
    by = {}
    for i in range(lo, hi + 1):
        by.setdefault(dates[i][:7], []).append(i)
    pos = {}
    for ym, idxs in by.items():
        for k, i in enumerate(idxs):
            pos[i] = (ym, k, k - len(idxs))
    return by, pos


def shift_month(ym, k):
    y, m = int(ym[:4]), int(ym[5:7])
    m += k
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


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
    by, pos = month_map(s["dates"], lo, hi)
    out = {}
    for name, rds in EVSETS.items():
        base = [i for i in (to_trading(s, rd, 0) for rd in rds) if i is not None and lo <= i <= hi]
        for off in OFFSETS:
            T = []
            for i in base:
                ym, p, pb = pos[i]
                tgt = by.get(shift_month(ym, off))
                if not tgt:
                    continue
                # 同时匹配正序位与倒序位：优先正序，位数不够时用倒序
                j = tgt[p] if p < len(tgt) else (tgt[pb] if -pb <= len(tgt) else None)
                if j is not None:
                    T.append(j)
            T = sorted(set(T))
            r = ratio_ci(s, T, lo, hi, spec="r28", nboot=2000) if len(T) >= 5 else None
            out[f"{name}|{off:+d}月"] = None if r is None else dict(
                mult=r["mult"], lo=r["lo"], hi=r["hi"], n=r["n"], blocks=r["blocks"], pass_=r["pass_"])
    return sym, out


if __name__ == "__main__":
    U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
    jobs = [(s, "uni") for s in U if U[s]["asset_class"] == "us_equity" and s != "SPY"]
    res = {}
    with Pool(9) as p:
        for o in p.imap_unordered(work, jobs):
            if o: res[o[0]] = o[1]
    json.dump(res, open(f"{OUT}/posmatch_gdp.json", "w"), ensure_ascii=False)
    print(f"{'事件':16s} " + " ".join(f"{('实际' if o==0 else f'{o:+d}月同位'):>12s}" for o in OFFSETS))
    for name in EVSETS:
        cells = []
        for off in OFFSETS:
            k = f"{name}|{off:+d}月"
            v = [res[s][k] for s in res if res[s].get(k)]
            if not v:
                cells.append("  -"); continue
            cells.append(f"{np.median([x['mult'] for x in v]):6.3f}/{sum(1 for x in v if x['pass_']):3d}")
        print(f"{name:16s} " + " ".join(f"{c:>12s}" for c in cells))
    print("\n格式：倍数中位 / 通过标的数（分母 90）")
