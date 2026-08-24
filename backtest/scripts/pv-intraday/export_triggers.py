"""导出触发时刻列表 + 每次触发的中间量（原始 bar 不落盘，见 README 重取方法）
用法 export_triggers.py <tze> <tve> <tzc> <tvc> <outname>"""
import sys, gzip, csv, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import trig_mask, valid_mask, daily_pack
from engine import sigma_decile, trigger as dtrig

HDR = ["sym", "asset", "grid", "session_day", "slot", "bar_start_et_or_utc", "z", "rvol",
       "rvol_bar", "logret", "sigma_rob", "V_A", "V_B", "L_B", "sigma_decile",
       "block_session", "daily_pv1_same_day", "lead_min_to_close"]

def slot_label(grid, k):
    if grid == "UTC": m = k * 15
    elif grid == "RTH": m = 9 * 60 + 30 + k * 15
    else: m = 4 * 60 + k * 15
    return f"{m//60:02d}:{m%60:02d}"

def main(tze, tve, tzc, tvc, out):
    us, cr = full()
    f = gzip.open(f"{BASE}/derived/{out}.csv.gz", "wt", newline="")
    w = csv.writer(f); w.writerow(HDR)
    n = 0
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        gk = "UTC" if crypto else "RTH"
        thz, thv = (tzc, tvc) if crypto else (tze, tve)
        try: P = prep(s, gk)
        except Exception: continue
        vm = valid_mask(P, "A")
        tmAll = trig_mask(P, thz, thv)          # 不受窗 A 有效性限制，完整触发列表
        vmB = valid_mask(P, "B")
        dec = sigma_decile(P["sigma"], vm)
        K = int(P["nslots"]); days = P["days"]
        try:
            dp = daily_pack(s, crypto)
            dt = dtrig(dp["ind"], 1.5, 3.0 if crypto else 2.0).reshape(-1)
            dset = {int(d.replace("-", "")) for i, d in enumerate(dp["dates"]) if dt[i]}
        except Exception:
            dset = set()
        for d, k in zip(*np.where(tmAll)):
            day = int(days[d])
            w.writerow([s, "crypto" if crypto else "us_equity", gk, day, int(k), slot_label(gk, int(k)),
                        round(float(P["z"][d, k]), 4), round(float(P["rvol"][d, k]), 4),
                        round(float(P["rvol_bar"][d, k]), 4) if not np.isnan(P["rvol_bar"][d, k]) else "",
                        round(float(P["r"][d, k]), 6), round(float(P["sigma"][d, k]), 8),
                        round(float(P["VA"][d, k]), 8) if not np.isnan(P["VA"][d, k]) else "",
                        round(float(P["VB"][d, k]), 8) if not np.isnan(P["VB"][d, k]) else "",
                        int(P["LB"][d, k]), int(dec[d, k]), day,
                        1 if day in dset else 0, (K - (int(k) + 1)) * 15])
            n += 1
    f.close()
    print(out, "行", n)

if __name__ == "__main__":
    main(*[float(x) for x in sys.argv[1:5]], sys.argv[5])
