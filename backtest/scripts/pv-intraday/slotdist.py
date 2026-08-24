"""触发的 slot 分布 + 与日线的告警量对齐点"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import trig_mask, valid_mask, daily_pack
from engine import trigger as dtrig

def daily_dayrate(sym, crypto, lo, hi, thv):
    dp = daily_pack(sym, crypto)
    tm = dtrig(dp["ind"], 1.5, thv).reshape(-1)
    vm = dp["vm"].reshape(-1)
    keys = np.array([int(d.replace("-", "")) for d in dp["dates"]])
    sel = (keys >= lo) & (keys <= hi) & vm
    if sel.sum() == 0: return None, 0
    return float(tm[sel].sum() / sel.sum()), int(sel.sum())

if __name__ == "__main__":
    us, cr = full()
    THZ = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0]
    slotcnt = {"us_equity": None, "crypto": None}
    rows = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        try: P = prep(s, "UTC" if crypto else "RTH")
        except Exception: continue
        thv = 3.0 if crypto else 2.0
        K = int(P["nslots"])
        vm = valid_mask(P, "A")
        days = P["days"]; vd = days[vm.any(axis=1)]
        if len(vd) < 50: continue
        dr, nday = daily_dayrate(s, crypto, int(vd.min()), int(vd.max()), thv)
        rec = dict(sym=s, asset="crypto" if crypto else "us_equity", daily_dayrate=dr, n_daily_days=nday)
        for thz in THZ:
            tm = trig_mask(P, thz, thv) & vm
            rec[f"intra_dayrate_z{thz}"] = float(tm.any(axis=1).mean())
            rec[f"intra_perday_z{thz}"] = float(tm.sum() / max(vm.any(axis=1).sum(), 1))
        tm = trig_mask(P, 1.5, thv) & vm
        c = tm.sum(axis=0).astype(float)
        a = rec["asset"]
        slotcnt[a] = c if slotcnt[a] is None else slotcnt[a] + c
        rows.append(rec)
    json.dump(dict(rows=rows, slot_us=list(slotcnt["us_equity"]), slot_cr=list(slotcnt["crypto"])),
              open(f"{BASE}/derived/slotdist.json", "w"), indent=1)
    for a in ("us_equity", "crypto"):
        rr = [x for x in rows if x["asset"] == a and x["daily_dayrate"] is not None]
        print(f"\n{a} n={len(rr)}  日线 PV1 有触发日占比 中位 {np.median([x['daily_dayrate'] for x in rr]):.4f}")
        for thz in THZ:
            print(f"   盘中 z{thz:<4} 有触发日占比中位 {np.median([x[f'intra_dayrate_z{thz}'] for x in rr]):.4f}"
                  f"   触发/日中位 {np.median([x[f'intra_perday_z{thz}'] for x in rr]):.3f}")
    c = np.array(slotcnt["us_equity"]); c = c / c.sum()
    print("\n美股 RTH 触发的时段分布（z1.5 v2.0）")
    for k in range(len(c)):
        print(f"   {9+((30+k*15)//60):02d}:{(30+k*15)%60:02d}  {c[k]*100:5.2f}%")
    c2 = np.array(slotcnt["crypto"]); c2 = c2/c2.sum()
    print("加密 UTC 前 8 与后 8 槽占比", np.round(c2[:8]*100,2), np.round(c2[-8:]*100,2))
