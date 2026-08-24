"""MA3 探索性附加检验：手工录入的 FOMC 决议日历。

⚠️ 这份日历**不来自 Arrays 端点**，是人工录入的公开会期表，可能有 ±1 日错误，
   不能作为正式证据（证据等级仍为 ⚪）。目的只有一个：回答产品问题
   「若外购一份 FOMC 日历，MA3 值不值得做」。

自检：决议日 SPY 当日 |收益| 应显著高于常态（这是文献里最稳的日内事实之一）。
      若自检不过，说明录入的日期是错的，下面的结论一律作废。
"""
import sys, os, json, csv, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from engine import build, ratio_ci, window_of, to_trading, zrob

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"

FOMC = """
2020-01-29 2020-03-03 2020-03-15 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29
""".split()


def work(arg):
    sym, source, shift = arg
    try:
        s = build(sym, source)
    except Exception:
        return sym, shift, None
    w = window_of(s, LO, HI)
    if w is None:
        return sym, shift, None
    lo, hi = w
    T = sorted(set(i for i in (to_trading(s, d, shift) for d in FOMC)
                   if i is not None and lo <= i <= hi))
    r = ratio_ci(s, T, lo, hi, spec="r28")
    return sym, shift, None if r is None else {k: r[k] for k in ("n", "blocks", "mult", "lo", "hi", "pass_")}


if __name__ == "__main__":
    # ---- 日期自检 ----
    wd = [datetime.date.fromisoformat(d).weekday() for d in FOMC]
    print(f"录入 {len(FOMC)} 个决议日 · 周三占 {sum(1 for x in wd if x==2)} · "
          f"其他星期 {sorted(set(x for x in wd if x!=2))}")
    s = build("SPY", "uni")
    z = zrob(s)
    idx = [to_trading(s, d, 0) for d in FOMC]
    idx = [i for i in idx if i is not None]
    zz = np.array([abs(z[i]) for i in idx if not np.isnan(z[i])])
    allz = np.abs(z[~np.isnan(z)])
    print(f"自检 · SPY 决议日 |z| 中位 {np.median(zz):.3f}（n={len(zz)}） vs 全样本 {np.median(allz):.3f} "
          f"→ 比值 {np.median(zz)/np.median(allz):.2f}")
    same = [s["dates"][i] for i in idx]
    print(f"落在交易日上的比例 {sum(1 for d,i in zip(FOMC,idx) if s['dates'][i]==d)}/{len(idx)}")

    U = [r for r in csv.DictReader(open(UNI))]
    jobs = []
    for r in U:
        src = "uni" if r["asset_class"] == "us_equity" else "crypto"
        if r["symbol"] == "SPY":
            continue
        for sh in (0, -1):
            jobs.append((r["symbol"], src, sh))
    res = {}
    with Pool(9) as p:
        for sym, sh, o in p.imap_unordered(work, jobs):
            res.setdefault(sym, {})[sh] = o
    json.dump(res, open(f"{OUT}/fomc.json", "w"))
    UU = {r["symbol"]: r for r in U}
    RATE = {"金融", "房地产", "公用事业"}
    for sh in (0, -1):
        for grp, syms in (("全部美股", [s for s in res if UU[s]["asset_class"] == "us_equity"]),
                          ("利率敏感", [s for s in res if UU[s]["sector"] in RATE]),
                          ("其余美股", [s for s in res if UU[s]["asset_class"] == "us_equity"
                                     and UU[s]["sector"] not in RATE]),
                          ("加密", [s for s in res if UU[s]["asset_class"] == "crypto"])):
            v = [res[s][sh] for s in syms if res[s].get(sh)]
            if not v:
                continue
            m = np.array([x["mult"] for x in v])
            print(f"平移 {sh:+d} · {grp:8s} n={len(v):3d}  倍数 中位 {np.median(m):.3f} "
                  f"[{m.min():.2f}, {m.max():.2f}]  通过 {sum(1 for x in v if x['pass_'])}/{len(v)}  "
                  f"触发中位 {int(np.median([x['n'] for x in v]))}")
