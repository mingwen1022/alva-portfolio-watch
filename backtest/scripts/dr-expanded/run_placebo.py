"""安慰剂平移：|k| >= 6（前瞻窗长 5）。k<=-6 时窗口不含触发日本身。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L

KS = [-12, -10, -8, -6, 0, 6, 8, 10, 12]
OUT = {}
for sym in L.CRYPTO:
    S = L.build(sym)
    f00, fmax, meta = L.load_funding(sym); oi = L.load_oi(sym)
    dates = S["dates"]
    fdays = [d for d in dates if d in f00]; odays = [d for d in dates if d in oi]
    ev_f = set(L.to_idx(S, fdays)); ev_o = set(L.to_idx(S, odays))
    px = {dates[i]: float(S["open"][i]) for i in range(S["n"])}
    sets = {
        "DR1@0.05": (L.to_idx(S, L.dr1_days(f00, fdays, 0.05)), ev_f),
        "DR3usd@0.10": (L.to_idx(S, L.dr3_days(oi, odays, 0.10)), ev_o),
        "DR3coin@0.10": (L.to_idx(S, L.dr3_days(oi, odays, 0.10, px=px)), ev_o),
    }
    rec = {}
    for name, (T, ev) in sets.items():
        rec[name] = {}
        for k in KS:
            Tk = [i + k for i in T if 0 <= i + k < S["n"]]
            r = L.ratio_ci(S, Tk, "fwd", eval_idx=ev, B=800) if Tk else None
            rec[name][str(k)] = None if r is None else dict(mult=r['mult'], lo=r['lo'], n=r['n'], blocks=r['blocks'])
    OUT[sym] = rec
    print(sym, "ok", file=sys.stderr)
json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "placebo.json"), "w"),
          ensure_ascii=False, indent=1)
