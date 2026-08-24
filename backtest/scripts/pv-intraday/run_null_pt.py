"""在采用阈值上跑两种经验零（全池）。用法 run_null_pt.py <tze> <tve> <tzc> <tvc> [reps]"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import null_run, null_run_slot

def main(tze, tve, tzc, tvc, reps=5, nboot=800, out="null_pt"):
    us, cr = full()
    res = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        try: P = prep(s, "UTC" if crypto else "RTH")
        except Exception: continue
        thz, thv = (tzc, tvc) if crypto else (tze, tve)
        for w in ("A", "B"):
            for mode, fn in (("day", null_run), ("slot", null_run_slot)):
                for x in fn(P, thz, thv, window=w, reps=reps, nboot=nboot):
                    res.append(dict(sym=s, asset="crypto" if crypto else "us_equity",
                                    window=w, mode=mode, mult=x["mult"], lo=x["lo"],
                                    blocks=x["blocks"], n=x["n"], passed=bool(x["pass_"])))
    json.dump(res, open(f"{BASE}/derived/{out}.json", "w"), indent=1, ensure_ascii=False)
    for w in ("A", "B"):
        for mode in ("day", "slot"):
            for a in ("us_equity", "crypto"):
                oo = [x for x in res if x["window"] == w and x["mode"] == mode and x["asset"] == a]
                if not oo: continue
                print(f"窗{w} 零-{mode} {a}: n={len(oo):<4} 假阳性 {sum(x['passed'] for x in oo)/len(oo)*100:5.1f}%"
                      f"  倍数中位 {np.median([x['mult'] for x in oo]):.3f}"
                      f"  块中位 {np.median([x['blocks'] for x in oo]):.0f}", flush=True)

if __name__ == "__main__":
    a = [float(x) for x in sys.argv[1:5]]
    main(*a, reps=int(sys.argv[5]) if len(sys.argv) > 5 else 5)
