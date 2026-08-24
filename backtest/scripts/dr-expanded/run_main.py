"""DR 族主回测（25 只加密）。逐标的，禁止池化。"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L

TH1 = [0.05, 0.075, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.00]
TH3 = [0.05, 0.10, 0.15, 0.20, 0.30]
OUT = {}
t00 = time.time()
for sym in L.CRYPTO:
    t0 = time.time()
    S = L.build(sym)
    f00, fmax, meta = L.load_funding(sym)
    oi = L.load_oi(sym)
    dates = S["dates"]
    ev_f = set(L.to_idx(S, [d for d in dates if d in f00]))
    ev_o = set(L.to_idx(S, [d for d in dates if d in oi]))
    px = {dates[i]: float(S["open"][i]) for i in range(S["n"])}   # 00:00 UTC 价格 = 当日开盘，无前视
    rec = dict(meta=dict(interval_h=meta["interval_h"], cutover=meta["cutover"],
                         fund_days=len(f00), oi_days=len(oi),
                         bars=S["n"], span=[dates[0], dates[-1]],
                         yrs_f=round(L.years_of(S, ev_f), 2) if ev_f else 0,
                         yrs_o=round(L.years_of(S, ev_o), 2) if ev_o else 0))
    fdays = [d for d in dates if d in f00]
    odays = [d for d in dates if d in oi]

    # 资金费率分位（%/8h，00:00 序列）
    fa = np.sort(np.abs(np.array([f00[d] for d in fdays])))
    q = lambda p: round(float(fa[int(p * (len(fa) - 1))]), 4)
    rec["f_quant"] = dict(p50=q(.5), p90=q(.9), p95=q(.95), p99=q(.99), p999=q(.999), max=round(float(fa[-1]), 4))

    # PV1 自检
    z, rv = S["z"], S["rvol"]
    pv1 = [i for i in range(S["n"]) if not np.isnan(z[i]) and not np.isnan(rv[i]) and abs(z[i]) >= 1.5 and rv[i] >= 3.0]
    rec["PV1"] = {a: L.ratio_ci(S, pv1, a) for a in ("fwd", "same")}
    rec["PV1_idx"] = pv1

    # DR1
    rec["DR1"] = {}
    for th in TH1:
        T = L.to_idx(S, L.dr1_days(f00, fdays, th))
        r = {}
        for a in ("fwd", "same"):
            r[a] = L.ratio_ci(S, T, a, eval_idx=ev_f) if T else None
        r["nopurge_fwd"] = L.ratio_ci(S, T, "fwd", eval_idx=ev_f, use_purge=False) if T else None
        r["n_raw"] = len(T)
        rec["DR1"][str(th)] = r
    # DR2
    rec["DR2"] = {}
    for tag, deb in (("debounce30", True), ("nodebounce", False)):
        T = L.to_idx(S, L.dr2_days(f00, fdays, debounce=deb))
        rec["DR2"][tag] = {a: (L.ratio_ci(S, T, a, eval_idx=ev_f) if T else None) for a in ("fwd", "same")}
        rec["DR2"][tag]["n_raw"] = len(T)
    # DR3
    rec["DR3"] = {}
    for den, p in (("usd", None), ("coin", px)):
        rec["DR3"][den] = {}
        for th in TH3:
            T = L.to_idx(S, L.dr3_days(oi, odays, th, px=p))
            r = {a: (L.ratio_ci(S, T, a, eval_idx=ev_o) if T else None) for a in ("fwd", "same")}
            r["nopurge_fwd"] = L.ratio_ci(S, T, "fwd", eval_idx=ev_o, use_purge=False) if T else None
            r["nopurge_same"] = L.ratio_ci(S, T, "same", eval_idx=ev_o, use_purge=False) if T else None
            r["n_raw"] = len(T)
            rec["DR3"][den][str(th)] = r
    # OI 日环比分位
    ratios = []
    for i in range(1, len(odays)):
        d, pv = odays[i], odays[i-1]
        import datetime
        if (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(pv)).days != 1: continue
        if oi[pv] > 0: ratios.append(abs(oi[d]-oi[pv])/oi[pv])
    ra = np.sort(np.array(ratios))
    if len(ra):
        rec["oi_quant"] = {k: round(float(ra[int(v*(len(ra)-1))]), 4)
                           for k, v in dict(p50=.5, p75=.75, p90=.9, p95=.95, p99=.99).items()}
        rec["oi_pct_of_10"] = round(float((ra < 0.10).mean()*100), 1)
    OUT[sym] = rec
    print(f"{sym} done {time.time()-t0:.1f}s", file=sys.stderr)

json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "main.json"), "w"),
          ensure_ascii=False, indent=1)
print(f"total {time.time()-t00:.1f}s", file=sys.stderr)
