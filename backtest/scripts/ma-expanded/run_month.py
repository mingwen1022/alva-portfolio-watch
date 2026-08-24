"""把「日历位置」本身当信号跑一遍，与宏观发布日直接对比。

三条纯日历规则：月末最后一个交易日 · 月初第一个交易日 · 月中第 13 个交易日（对照）
若纯日历规则的通过数高于任何宏观发布日，则宏观族里剩下的「通过」不能归因于宏观信息。

附带：beta 与倍数的秩相关在 10 套伪日历上的零分布（判 FEDFUNDS 日的 +0.285 是否异常）。
"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy import stats
from engine import build, ratio_ci, window_of

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"


def month_idx(dates, lo, hi):
    first, last, mid = [], [], []
    cur, idxs = None, []
    def flush():
        if not idxs: return
        first.append(idxs[0]); last.append(idxs[-1])
        if len(idxs) >= 13: mid.append(idxs[12])
    for i in range(lo, hi + 1):
        ym = dates[i][:7]
        if ym != cur:
            flush(); idxs.clear(); cur = ym
        idxs.append(i)
    flush()
    return dict(月初首日=first, 月末末日=last, 月中第13日=mid)


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
    for k, T in month_idx(s["dates"], lo, hi).items():
        r = ratio_ci(s, T, lo, hi, spec="r28")
        out[k] = None if r is None else {x: r[x] for x in ("n", "blocks", "mult", "lo", "hi", "pass_")}
    return sym, out


if __name__ == "__main__":
    U = [r for r in csv.DictReader(open(UNI))]
    jobs = [(r["symbol"], "uni") for r in U if r["asset_class"] == "us_equity" and r["symbol"] != "SPY"]
    jobs += [(r["symbol"], "crypto") for r in U if r["asset_class"] == "crypto"]
    res = {}
    with Pool(9) as p:
        for o in p.imap_unordered(work, jobs):
            if o: res[o[0]] = o[1]
    json.dump(res, open(f"{OUT}/month.json", "w"), ensure_ascii=False)
    UU = {r["symbol"]: r for r in U}
    for grp, syms in (("美股", [s for s in res if UU[s]["asset_class"] == "us_equity"]),
                      ("加密", [s for s in res if UU[s]["asset_class"] == "crypto"])):
        for k in ("月末末日", "月初首日", "月中第13日"):
            v = [res[s][k] for s in syms if res[s].get(k)]
            m = np.array([x["mult"] for x in v])
            print(f"{grp} {k:8s} n={len(v):3d} 触发中位 {int(np.median([x['n'] for x in v]))} "
                  f"倍数中位 {np.median(m):.3f} [{m.min():.2f}, {m.max():.2f}] "
                  f"通过 {sum(1 for x in v if x['pass_'])}/{len(v)}")

    # beta 秩相关的伪日历零分布
    null = json.load(open(f"{OUT}/null.json"))
    per = json.load(open(f"{OUT}/core.json"))
    beta = {s: float(UU[s]["beta"]) for s in UU if UU[s]["asset_class"] == "us_equity" and UU[s]["beta"]}
    rows = []
    for c in range(10):
        syms = [s for s in null if null[s] and null[s].get(str(c) if str(c) in (null[s] or {}) else c) and s in beta]
        x = [beta[s] for s in syms]
        y = [null[s][str(c) if str(c) in null[s] else c]["mult"] for s in syms]
        if len(x) > 30:
            r, p = stats.spearmanr(x, y)
            rows.append(r)
    print(f"\nbeta 与倍数的 Spearman 在 10 套伪日历上：{[round(x,3) for x in rows]}")
    print(f"   |rho| 最大 {max(abs(x) for x in rows):.3f} · 实测 FEDFUNDS 当日 +0.285")
    for s in list(res)[:1]:
        pass
    mm = {s: res[s]["月末末日"]["mult"] for s in res if UU[s]["asset_class"] == "us_equity" and res[s].get("月末末日")}
    x = [beta[s] for s in mm if s in beta]; y = [mm[s] for s in mm if s in beta]
    r, p = stats.spearmanr(x, y)
    print(f"   月末末日（纯日历）上的 beta 秩相关 {r:+.3f} (p={p:.3f})")
