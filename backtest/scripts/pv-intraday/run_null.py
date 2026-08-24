"""经验零：保持丛集结构（同 slot 图案），随机换 session。用法 run_null.py <thz> <tve> <tvc> [window] [reps]"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import null_run

def main(thz, tve, tvc, window="A", reps=5, gk_eq="RTH"):
    us, cr = full()
    out = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        try: P = prep(s, "UTC" if crypto else gk_eq)
        except Exception: continue
        for x in null_run(P, thz, tvc if crypto else tve, window=window, reps=reps):
            out.append(dict(sym=s, asset="crypto" if crypto else "us_equity",
                            window=window, mult=x["mult"], lo=x["lo"], blocks=x["blocks"],
                            n=x["n"], passed=bool(x["pass_"])))
    return out

if __name__ == "__main__":
    thz, tve, tvc = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    ws = (sys.argv[4].split(",") if len(sys.argv) > 4 else ["A", "B"])
    reps = int(sys.argv[5]) if len(sys.argv) > 5 else 5
    allout = []
    for w in ws:
        o = main(thz, tve, tvc, window=w, reps=reps)
        allout += o
        for a in ("us_equity", "crypto"):
            oo = [x for x in o if x["asset"] == a]
            if not oo: continue
            print(f"窗 {w} {a}: {len(oo)} 次伪触发  通过 {sum(x['passed'] for x in oo)} "
                  f"= {sum(x['passed'] for x in oo)/len(oo)*100:.1f}%   倍数中位 {np.median([x['mult'] for x in oo]):.3f}")
    json.dump(allout, open(f"{BASE}/derived/null.json", "w"), indent=1, ensure_ascii=False)
