"""主跑：三个前瞻窗 × 全池，逐标的输出。用法 run_all.py <thz> <thv_eq> <thv_cr> [grid]"""
import sys, json, time, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import run_window, run_window_C, daily_pack, trig_mask, valid_mask

def main(tze, tve, tzc, tvc, gk_eq="RTH", nboot=2000, out="main"):
    us, cr = full()
    rows = []
    t0 = time.time()
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        gk = "UTC" if crypto else gk_eq
        thv = tvc if crypto else tve
        thz = tzc if crypto else tze
        try: P = prep(s, gk)
        except Exception as e:
            print("ERR prep", s, e); continue
        rec = dict(sym=s, asset="crypto" if crypto else "us_equity", grid=gk,
                   sector=r["sector"], vol_tier=r["vol_tier"], size_tier=r["size_tier"],
                   sigma_ann_daily=float(r["sigma_ann"]) if r["sigma_ann"] else None)
        vmA = valid_mask(P, "A")
        tmA = trig_mask(P, thz, thv)
        rec["n_bar_valid"] = int(((~np.isnan(P["z"])) & (~np.isnan(P["rvol"]))).sum())
        rec["n_trig_raw"] = int(tmA.sum())
        rec["n_trig_A"] = int((tmA & vmA).sum())
        rec["n_days_valid"] = int(vmA.any(axis=1).sum())
        rec["n_days_trig"] = int((tmA & vmA).any(axis=1).sum())
        rec["rho"] = float(np.mean(np.abs(P["z"][~np.isnan(P["z"])]) >= thz)) if (~np.isnan(P["z"])).any() else None
        rr = P["r"][tmA & vmA]; rec["absr_med_at_trig"] = float(np.median(np.abs(rr))) if rr.size else None
        rec["thz"] = thz; rec["thv"] = thv
        for w in ("A", "AX", "B"):
            res = run_window(P, thz, thv, window=w, nboot=nboot)
            if res:
                rec[w] = dict(n=res["n"], blocks=res["blocks"], mult=round(res["mult"], 3),
                              lo=round(res["lo"], 3), hi=round(res["hi"], 3), passed=bool(res["pass_"]))
            else:
                rec[w] = None
        # 窗 C：日线
        try:
            dp = daily_pack(s, crypto)
            days = P["days"]
            tdays = [int(d) for d in days[(tmA & vmA).any(axis=1)]]
            resC = run_window_C(dp, tdays, nboot=nboot)
            rec["C"] = dict(n=resC["n"], blocks=resC["blocks"], mult=round(resC["mult"],3),
                            lo=round(resC["lo"],3), hi=round(resC["hi"],3), passed=bool(resC["pass_"])) if resC else None
        except Exception as e:
            rec["C"] = None; rec["C_err"] = str(e)[:80]
        rows.append(rec)
        a = rec["A"]; b = rec["B"]; c = rec["C"]
        print(f"{s:<7}{rec['asset']:<10}触发 {rec['n_trig_A']:>5} 日 {rec['n_days_trig']:>4}  "
              f"A {a['mult'] if a else float('nan'):.2f}[{a['lo'] if a else 0:.2f}]{'🟢' if a and a['passed'] else '❌'}  "
              f"B {b['mult'] if b else float('nan'):.2f}[{b['lo'] if b else 0:.2f}]{'🟢' if b and b['passed'] else '❌'}  "
              f"C {c['mult'] if c else float('nan'):.2f}[{c['lo'] if c else 0:.2f}]{'🟢' if c and c['passed'] else '❌'}",
              flush=True)
    json.dump(rows, open(f"{BASE}/derived/{out}.json", "w"), indent=1, ensure_ascii=False)
    print("用时", round(time.time()-t0), "秒")
    return rows

if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]),
         sys.argv[5] if len(sys.argv) > 5 else "RTH",
         out=sys.argv[6] if len(sys.argv) > 6 else "main")
