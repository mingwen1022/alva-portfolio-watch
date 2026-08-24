"""经验零分布：用随机伪日历跑同一条流水线，得到「x/91 通过」在无效应下的参考分布。

伪日历构造：与真实月度发布同节奏 —— 每 21 个交易日取 1 天，起点随机，共 10 套。
对每套跑 91 只美股，统计通过数。用于回答「0/91 是真的没效应，还是这把尺子对谁都给 0」。
"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, ratio_ci, window_of

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"
NCAL = 10
STEP = 21


def work(arg):
    sym, source = arg
    try:
        s = build(sym, source)
    except Exception:
        return sym, None
    w = window_of(s, LO, HI)
    if w is None:
        return sym, None
    lo, hi = w
    out = {}
    for c in range(NCAL):
        rng = np.random.default_rng(1000 + c)
        start = lo + int(rng.integers(0, STEP))
        T = list(range(start, hi + 1, STEP))
        # 加一点抖动，避免与星期几完全对齐
        T = sorted(set(min(hi, max(lo, t + int(rng.integers(-3, 4)))) for t in T))
        r = ratio_ci(s, T, lo, hi, spec="r28", nboot=2000)
        out[c] = None if r is None else dict(mult=r["mult"], lo=r["lo"], hi=r["hi"],
                                             n=r["n"], blocks=r["blocks"], pass_=r["pass_"])
    return sym, out


if __name__ == "__main__":
    U = [r for r in csv.DictReader(open(UNI))]
    jobs = [(r["symbol"], "uni") for r in U if r["asset_class"] == "us_equity" and r["symbol"] != "SPY"]
    res = {}
    with Pool(9) as p:
        for i, (sym, o) in enumerate(p.imap_unordered(work, jobs)):
            res[sym] = o
            if (i + 1) % 20 == 0:
                print(f"[{i+1}/{len(jobs)}]", flush=True)
    json.dump(res, open(f"{OUT}/null.json", "w"))
    print(f"{'伪日历':8s} {'通过/91':>9s} {'倍数中位':>9s} {'倍数max':>8s}")
    npass = []
    for c in range(NCAL):
        v = [res[s][c] for s in res if res[s] and res[s].get(c)]
        p_ = sum(1 for x in v if x["pass_"])
        npass.append(p_)
        print(f"#{c:<7d} {p_:5d}/{len(v):<3d} {np.median([x['mult'] for x in v]):9.3f} "
              f"{max(x['mult'] for x in v):8.3f}")
    print(f"经验零：通过数 中位 {np.median(npass):.1f} · 区间 [{min(npass)}, {max(npass)}] · "
          f"均值 {np.mean(npass):.1f}（名义 2.5% 单侧 → 期望 2.3）")
