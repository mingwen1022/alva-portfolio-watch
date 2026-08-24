"""盘中 PV1 与日线 PV1 的关系：提前量 · 召回 · 日内回吐"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import daily_pack, trig_mask, valid_mask
from engine import trigger as dtrig

def daily_trigger_days(sym, crypto, lo, hi, thv):
    dp = daily_pack(sym, crypto)
    tm = dtrig(dp["ind"], 1.5, thv).reshape(-1)
    out = []
    for i, d in enumerate(dp["dates"]):
        k = int(d.replace("-", ""))
        if tm[i] and lo <= k <= hi: out.append(k)
    return set(out), dp

def run(tze, thv_eq, tzc, thv_cr, gridkind_eq="RTH"):
    us, cr = full()
    rows = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        gk = "UTC" if crypto else gridkind_eq
        thv = thv_cr if crypto else thv_eq
        thz = tzc if crypto else tze
        try:
            P = prep(s, gk)
        except Exception as e:
            continue
        days = P["days"]; K = int(P["nslots"])
        vm = (~np.isnan(P["z"])) & (~np.isnan(P["rvol"]))
        tm = trig_mask(P, thz, thv) & vm
        vdays = days[vm.any(axis=1)]
        if len(vdays) < 50: continue
        lo, hi = int(vdays.min()), int(vdays.max())
        try:
            dset, dp = daily_trigger_days(s, crypto, lo, hi, thv_cr if crypto else 2.0)
        except Exception:
            continue
        dset = {d for d in dset if lo <= d <= hi}
        intr = {}
        rowsel = np.flatnonzero(tm.any(axis=1))
        for d in rowsel:
            slots = np.flatnonzero(tm[d])
            intr[int(days[d])] = int(slots[0])
        both = set(intr) & dset
        # 提前量：bar 收盘时刻到当日收盘的分钟数
        if crypto:
            close_slot = K            # 24h 收线 = slot 96 结束
            step = 15
        else:
            close_slot = K            # 15:45 bar 收于 16:00
            step = 15
        leads = [ (close_slot - (intr[d] + 1)) * step for d in both ]
        rows.append(dict(sym=s, asset="crypto" if crypto else "us_equity",
                         sector=r["sector"], vol_tier=r["vol_tier"],
                         n_valid_days=int(len(vdays)),
                         n_daily=len(dset), n_intra=len(intr), n_both=len(both),
                         recall=len(both)/len(dset) if dset else None,
                         precision=len(both)/len(intr) if intr else None,
                         intraday_only=1 - (len(both)/len(intr)) if intr else None,
                         lead_med_min=float(np.median(leads)) if leads else None,
                         lead_p25=float(np.percentile(leads,25)) if leads else None,
                         lead_p75=float(np.percentile(leads,75)) if leads else None))
        print(f"{s:<7}{rows[-1]['asset']:<10} 日线 {len(dset):>4} 盘中日 {len(intr):>4} 交集 {len(both):>4}"
              f"  召回 {rows[-1]['recall'] if rows[-1]['recall'] is not None else float('nan'):.2f}"
              f"  仅盘中 {rows[-1]['intraday_only'] if rows[-1]['intraday_only'] is not None else float('nan'):.2f}"
              f"  提前 {rows[-1]['lead_med_min'] if leads else float('nan'):.0f} 分钟", flush=True)
    return rows

if __name__ == "__main__":
    tze, tve, tzc, tvc = (float(x) for x in sys.argv[1:5])
    rows = run(tze, tve, tzc, tvc)
    import os
    OUT = sys.argv[5] if len(sys.argv) > 5 else "daily_link"
    json.dump(rows, open(f"{BASE}/derived/{OUT}.json","w"), indent=1, ensure_ascii=False)
    import statistics as st, numpy as np
    for a in ("us_equity","crypto"):
        rr=[x for x in rows if x["asset"]==a and x["recall"] is not None and x["intraday_only"] is not None]
        if not rr: continue
        print(f"\n{a}  n={len(rr)}  召回中位 {st.median(x['recall'] for x in rr):.3f}"
              f"  仅盘中中位 {st.median(x['intraday_only'] for x in rr):.3f}"
              f"  提前中位 {st.median([x['lead_med_min'] for x in rr if x['lead_med_min'] is not None]):.0f} 分钟"
              f"  召回四分位 [{np.percentile([x['recall'] for x in rr],25):.2f}, {np.percentile([x['recall'] for x in rr],75):.2f}]")
