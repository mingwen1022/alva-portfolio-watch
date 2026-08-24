"""日历位置检验：把归一化 V 按「当月第几个交易日」聚合。

动机：有效联邦基金利率「发布日」= 每月首个工作日，本身不是市场事件，
      却在 92 只池子上给出 20–26/90 通过。若通过率随日历位置系统性变化，
      则 MA 族所有「通过」都要先排除日历位置，才能归因到宏观信息。
"""
import sys, os, json, csv, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, norm_V, window_of, ratio_ci, to_trading
from macro_calendar import first_release

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"


def tdom(dates, lo, hi):
    """每个下标 -> (当月第几个交易日 1..n, 距月末倒数第几个 -1..-n)"""
    pos = {}
    cur, idxs = None, []
    for i in range(lo, hi + 1):
        ym = dates[i][:7]
        if ym != cur:
            for k, j in enumerate(idxs):
                pos[j] = (k + 1, k - len(idxs))
            cur, idxs = ym, []
        idxs.append(i)
    for k, j in enumerate(idxs):
        pos[j] = (k + 1, k - len(idxs))
    return pos


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
    nv, _ = norm_V(s, [], lo, hi)          # 无触发 → 基准 = 窗内全部可用日（σ 十分位分层）
    if nv is None:
        return None
    pos = tdom(s["dates"], lo, hi)
    fwd, bwd = {}, {}
    for i in range(lo, hi + 1):
        if np.isnan(nv[i]) or i not in pos:
            continue
        a, b = pos[i]
        fwd.setdefault(a, []).append(float(nv[i]))
        bwd.setdefault(b, []).append(float(nv[i]))
    return sym, {k: float(np.median(v)) for k, v in fwd.items() if len(v) >= 20}, \
                {k: float(np.median(v)) for k, v in bwd.items() if len(v) >= 20}


def event_positions(sym="AAPL"):
    s = build(sym, "uni")
    lo, hi = window_of(s, LO, HI)
    pos = tdom(s["dates"], lo, hi)
    out = {}
    for ind, lab in (("CPI", "物价"), ("TOTAL_NONFARM_PAYROLL", "就业"),
                     ("GDP", "产出"), ("FEDERAL_FUNDS", "有效联邦基金利率")):
        rds = [rd for rd, _, _ in first_release(ind)]
        for sh, tag in ((0, "T0"), (-1, "T−1"), (-6, "k=−6"), (-8, "k=−8"), (-10, "k=−10")):
            ii = [to_trading(s, rd, sh) for rd in rds]
            p = [pos[i][0] for i in ii if i is not None and i in pos]
            pb = [pos[i][1] for i in ii if i is not None and i in pos]
            if p:
                out[f"{lab} {tag}"] = (float(np.median(p)), float(np.median(pb)), len(p))
    return out


if __name__ == "__main__":
    U = [r for r in csv.DictReader(open(UNI))]
    jobs = [(r["symbol"], "uni") for r in U if r["asset_class"] == "us_equity" and r["symbol"] != "SPY"]
    res = []
    with Pool(6) as p:
        for o in p.imap_unordered(work, jobs):
            if o: res.append(o)
    print(f"标的 {len(res)} 只")
    print("\n当月第几个交易日 → 归一化 V 的跨标的中位（1.00 = 与该 σ 档常态一样）")
    print(f"{'位置':>5s} {'中位':>7s} {'>1.02 的标的占比':>16s}")
    tab_f = {}
    for k in range(1, 23):
        v = [f[k] for _, f, _ in res if k in f]
        if len(v) < 40: continue
        tab_f[k] = (float(np.median(v)), float(np.mean([x > 1.02 for x in v])), len(v))
        print(f"{k:5d} {tab_f[k][0]:7.3f} {tab_f[k][1]*100:15.0f}%  n={len(v)}")
    print("\n距月末倒数第几个交易日：")
    tab_b = {}
    for k in range(-1, -8, -1):
        v = [b[k] for _, _, b in res if k in b]
        if len(v) < 40: continue
        tab_b[k] = (float(np.median(v)), float(np.mean([x > 1.02 for x in v])), len(v))
        print(f"{k:5d} {tab_b[k][0]:7.3f} {tab_b[k][1]*100:15.0f}%  n={len(v)}")

    print("\n各事件集落在什么日历位置（中位；正数=当月第几个交易日，负数=距月末倒数第几）")
    for k, v in event_positions().items():
        print(f"  {k:16s} 第 {v[0]:4.1f} 个交易日 · 倒数第 {abs(v[1]):4.1f} 个   n={v[2]}")
    json.dump(dict(fwd=tab_f, bwd=tab_b, ev=event_positions()),
              open(f"{OUT}/calpos.json", "w"), ensure_ascii=False, indent=1)
