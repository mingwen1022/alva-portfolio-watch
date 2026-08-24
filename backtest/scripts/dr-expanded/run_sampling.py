"""00:00 单点抽样对 DR1 的低估程度（新口径时段 3 或 6 条/日）。"""
import sys, os, json, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L

out = {}
for sym in L.CRYPTO:
    rows = L.load_funding_raw(sym)
    cut = L.detect_cutover(rows); ih = L.funding_interval_hours(rows, cut); k8 = 8.0 / ih
    byday = collections.defaultdict(dict)
    for t, v in rows:
        if t < cut: continue
        byday[t[:10]][t[11:16]] = v * 100.0 * k8
    days = [d for d, v in byday.items() if "00:00" in v and len(v) >= 2]
    rat, f0s, fms = [], [], []
    for d in days:
        v = byday[d]; f0 = abs(v["00:00"]); fm = max(abs(x) for x in v.values())
        f0s.append(f0); fms.append(fm)
        if f0 > 0: rat.append(fm / f0)
    rat = np.sort(np.array(rat)); f0s = np.array(f0s); fms = np.array(fms)
    top = np.argsort(-f0s)[:max(1, len(f0s)//10)]
    rtop = np.sort(fms[top] / np.maximum(f0s[top], 1e-12))
    rec = dict(n_days=len(days), interval_h=ih,
               p50=round(float(np.median(rat)), 3),
               p90=round(float(rat[int(.9*(len(rat)-1))]), 3),
               max=round(float(rat[-1]), 2),
               frac_ge_1_87=round(float((rat >= 1.87).mean()*100), 1),
               top_decile_p50=round(float(np.median(rtop)), 3),
               top_decile_p90=round(float(rtop[int(.9*(len(rtop)-1))]), 3))
    # DR1 在稠密时段：00:00 序列 vs 当日最大
    for th in (0.05, 0.10, 0.15, 0.20, 0.40):
        rec[f"trig00_{th}"] = int((f0s >= th).sum())
        rec[f"trigmax_{th}"] = int((fms >= th).sum())
    out[sym] = rec

json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "sampling.json"), "w"),
          ensure_ascii=False, indent=1)
print("%-7s %5s %4s %6s %6s %7s %8s %7s %7s | 0.05 00/max | 0.15 00/max | 0.40 00/max"
      % ("sym", "days", "ih", "p50", "p90", "max", "≥1.87%", "top50", "top90"))
for s, v in out.items():
    print("%-7s %5d %4d %6.2f %6.2f %7.1f %8.1f %7.2f %7.2f | %4d/%-4d | %4d/%-4d | %4d/%-4d"
          % (s, v["n_days"], v["interval_h"], v["p50"], v["p90"], v["max"], v["frac_ge_1_87"],
             v["top_decile_p50"], v["top_decile_p90"],
             v["trig00_0.05"], v["trigmax_0.05"], v["trig00_0.15"], v["trigmax_0.15"],
             v["trig00_0.4"], v["trigmax_0.4"]))
