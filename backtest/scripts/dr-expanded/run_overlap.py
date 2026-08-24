"""DR1/DR2/DR3 重叠分析 —— 先输出计数再给比值（硬规则）。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L

DR1_THS = [0.40, 0.15, 0.05]     # registry 值 + 两个能触发的档
OUT = {}
for sym in L.CRYPTO:
    S = L.build(sym)
    f00, fmax, meta = L.load_funding(sym); oi = L.load_oi(sym)
    dates = S["dates"]
    fdays = [d for d in dates if d in f00]; odays = [d for d in dates if d in oi]
    ev = set(L.to_idx(S, [d for d in dates if d in f00 and d in oi]))
    px = {dates[i]: float(S["open"][i]) for i in range(S["n"])}
    z, rv = S["z"], S["rvol"]
    pv1 = set(i for i in range(S["n"]) if not np.isnan(z[i]) and not np.isnan(rv[i])
              and abs(z[i]) >= 1.5 and rv[i] >= 3.0) & ev
    d2 = set(L.to_idx(S, L.dr2_days(f00, fdays))) & ev
    d3 = set(L.to_idx(S, L.dr3_days(oi, odays, 0.10))) & ev
    d3c = set(L.to_idx(S, L.dr3_days(oi, odays, 0.10, px=px))) & ev
    rec = dict(n_eval=len(ev), DR2=len(d2), DR3=len(d3), DR3coin=len(d3c), PV1=len(pv1))
    for th in DR1_THS:
        d1 = set(L.to_idx(S, L.dr1_days(f00, fdays, th))) & ev
        u = d1 | d2
        def stat(A, Bs):
            inter = len(A & Bs); union = len(A | Bs)
            return dict(inter=inter, jac=round(inter/union, 4) if union else None,
                        p_b_given_a=round(inter/len(A), 3) if A else None,
                        base_b=round(len(Bs)/len(ev), 4) if ev else None,
                        lift=round((inter/len(A))/(len(Bs)/len(ev)), 2) if A and Bs and ev else None)
        rec[f"th{th}"] = dict(
            DR1=len(d1),
            DR1_DR2=stat(d1, d2), DR1_DR3=stat(d1, d3), DR2_DR3=stat(d2, d3),
            U12_DR3=stat(u, d3), DR3_PV1=stat(d3, pv1), DR1_PV1=stat(d1, pv1),
            merged=L.ratio_ci(S, sorted(d1 | d2 | d3), "fwd", eval_idx=ev) if (d1|d2|d3) else None,
            DR1_alone=L.ratio_ci(S, sorted(d1), "fwd", eval_idx=ev) if d1 else None,
            DR2_alone=L.ratio_ci(S, sorted(d2), "fwd", eval_idx=ev) if d2 else None,
            DR3_alone=L.ratio_ci(S, sorted(d3), "fwd", eval_idx=ev) if d3 else None,
        )
    OUT[sym] = rec
    print(sym, "ok", file=sys.stderr)
json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "overlap.json"), "w"),
          ensure_ascii=False, indent=1)
