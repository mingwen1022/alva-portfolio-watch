"""两种经验零，多个阈值点。用法 run_null2.py"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import grid_subset
from prep import prep
from analysis import null_run, null_run_slot

POINTS = [(1.5, 2.0, 3.0), (2.5, 2.0, 3.0), (4.0, 2.0, 3.0), (5.0, 2.0, 3.0)]
WINDOWS = ["A", "B"]

def main(reps=4, nboot=600):
    gu, gc = grid_subset()
    cache = {}
    for r in gu: cache[r["symbol"]] = ("us_equity", prep(r["symbol"], "RTH"))
    for r in gc: cache[r["symbol"]] = ("crypto", prep(r["symbol"], "UTC"))
    out = []
    for thz, tve, tvc in POINTS:
        for w in WINDOWS:
            for mode, fn in (("day", null_run), ("slot", null_run_slot)):
                rec = []
                for s, (a, P) in cache.items():
                    for x in fn(P, thz, tvc if a == "crypto" else tve, window=w, reps=reps, nboot=nboot):
                        rec.append(dict(sym=s, asset=a, thz=thz, window=w, mode=mode,
                                        mult=x["mult"], lo=x["lo"], blocks=x["blocks"],
                                        n=x["n"], passed=bool(x["pass_"])))
                out += rec
                for a in ("us_equity", "crypto"):
                    oo = [x for x in rec if x["asset"] == a]
                    if not oo: continue
                    print(f"z{thz} 窗{w} 零假设-{mode} {a}: n={len(oo):<4} 假阳性 "
                          f"{sum(x['passed'] for x in oo)/len(oo)*100:5.1f}%  倍数中位 {np.median([x['mult'] for x in oo]):.3f}",
                          flush=True)
    json.dump(out, open(f"{BASE}/derived/null2.json", "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
