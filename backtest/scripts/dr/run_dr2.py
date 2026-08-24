"""对齐口径变体 + PV1 重叠 + 触发日明细。

告警在 00:00 UTC 到达（资金费率结算时刻 / OI 快照时刻），而加密日线的 time_open 也是 00:00 UTC。
所以「告警之后的 5 天」在日历上是 t..t+4，不是 t+1..t+5。
主口径沿用 plan.md 的 t+1..t+5（与 PV 可比），此处给 t..t+4 的对照。
"""
import json, math, datetime, statistics as st, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dr_engine import *

Wv, ZT, VT = 90, 1.5, 3.0          # PV1 加密档：|z|>=1.5 且 RVOL>=3.0


def build2(sym, bars):
    S = build(sym, bars)
    n, r, sig = S["n"], S["r"], S["sig"]
    # 同日起算的 V：sqrt(mean(r_t..r_{t+4}^2)) / sigma_rob,t（基线窗仍不含当日）
    V0 = [None] * n
    for t in range(n):
        if sig[t] is None or t + FWD - 1 >= n:
            continue
        rr = [r[t + k] for k in range(0, FWD)]
        if any(x is None for x in rr):
            continue
        V0[t] = math.sqrt(sum(x * x for x in rr) / FWD) / sig[t]
    # PV1
    vol = [b[2] for b in bars]
    z = [None] * n; rv = [None] * n
    for t in range(n):
        w = [r[i] for i in range(max(1, t - Wv), t) if r[i] is not None]
        if len(w) >= 60 and r[t] is not None:
            m = med(w); s = 1.4826 * med([abs(x - m) for x in w])
            if s > 0:
                z[t] = (r[t] - m) / s
        vw = [vol[i] for i in range(max(0, t - Wv), t) if vol[i] and vol[i] > 0]
        if len(vw) >= 60:
            mv = med(vw)
            if mv > 0:
                rv[t] = vol[t] / mv
    pv1 = set(S["dates"][t] for t in range(n)
              if z[t] is not None and rv[t] is not None and abs(z[t]) >= ZT and rv[t] >= VT)
    S["V0"] = V0
    S["pv1"] = pv1
    return S


def stat_for(trig, Vmap, dates):
    trig = trig & set(Vmap) & set(dates)
    if not trig:
        return None
    base = [Vmap[d] for d in dates if d in Vmap and d not in trig]
    td = sorted(datetime.date.fromisoformat(d) for d in trig)
    Vd = {datetime.date.fromisoformat(d): Vmap[d] for d in trig}
    return ratio_ci(td, Vd, base)


out = {}
for sym in SYMS:
    bars = load_bars(sym)
    S = build2(sym, bars)
    f00, fmax, brk = load_funding(sym)
    oi = load_oi(sym)
    # 00:00 时刻价格 ≈ 前一日收盘（该日 K 线的 open）。用当日收盘会引入前视。
    px = {S["dates"][i]: S["close"][i - 1] for i in range(1, S["n"])}
    V1 = {S["dates"][i]: S["V"][i] for i in range(S["n"]) if S["V"][i] is not None}
    V0 = {S["dates"][i]: S["V0"][i] for i in range(S["n"]) if S["V0"][i] is not None}
    dates = sorted(set(V1) & set(V0))
    lo = max(min(f00), min(oi), dates[0]); hi = min(max(f00), max(oi), dates[-1])
    dates = [d for d in dates if lo <= d <= hi]
    ds = set(dates)
    years = len(dates) / 365.0

    sigs = {"DR1": sig_dr1(f00, dates) & ds,
            "DR2": sig_dr2(f00, dates) & ds,
            "DR3": sig_dr3(oi, dates, px=None) & ds,
            "DR3_coin": sig_dr3(oi, dates, px=px) & ds,
            "PV1": S["pv1"] & ds}
    sigs["DR123"] = sigs["DR1"] | sigs["DR2"] | sigs["DR3"]

    rec = {"span": [lo, hi], "days": len(dates), "years": round(years, 2), "sig": {}}
    for k, t in sigs.items():
        rec["sig"][k] = dict(n=len(t), F=round(len(t) / years, 1),
                             main=stat_for(t, V1, dates), same_day=stat_for(t, V0, dates))
    # PV1 重叠
    P = sigs["PV1"]
    rec["vs_PV1"] = {k: dict(both=len(sigs[k] & P), jac=jac(sigs[k], P),
                             p_PV1_given=round(len(sigs[k] & P) / len(sigs[k]), 3) if sigs[k] else None,
                             lift=round((len(sigs[k] & P) / len(sigs[k])) / (len(P) / len(dates)), 2) if sigs[k] and P else None)
                     for k in ["DR1", "DR2", "DR3", "DR3_coin", "DR123"]}
    rec["pv1_base_rate"] = round(len(P) / len(dates), 3)
    # 明细
    rec["DR1_days"] = sorted(sigs["DR1"])
    rec["DR2_days"] = sorted(sigs["DR2"])
    rec["fund_top10"] = sorted(((round(abs(f00[d]), 4), d) for d in dates if d in f00), reverse=True)[:10]
    # 00:00 抽样 vs 当日 max 的比值（仅 3 次/日的时段可算）
    ratios = []
    for d in dates:
        if d >= brk and d in f00 and d in fmax and abs(f00[d]) > 1e-9:
            ratios.append(abs(fmax[d]) / abs(f00[d]))
    ratios.sort()
    rec["maxday_over_0000"] = dict(n=len(ratios),
                                   p50=round(ratios[len(ratios) // 2], 2) if ratios else None,
                                   p90=round(ratios[int(0.9 * (len(ratios) - 1))], 2) if ratios else None,
                                   max=round(ratios[-1], 2) if ratios else None)
    out[sym] = rec

print(json.dumps(out, ensure_ascii=False, indent=1))
