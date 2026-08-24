"""复现对照：用 mine.py 独立复算若干标的的四个 arm，与 arms.json 逐位比对。"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mine import prep, calibrate, masks, ratio_ci, roster

SRC = "/Users/ming/project/alva/backtest/scripts/andor/arms.json"
CHECK = ["and_base", "price_base", "vol_base", "or_base",
         "price_eq", "vol_eq", "or_eq", "or_scale"]


def main(syms):
    ref = {r["sym"]: r for r in json.load(open(SRC))}
    rows = {r["symbol"]: r for r in roster()}
    bad = 0
    for s in syms:
        if s not in ref:
            print(f"{s}: 不在 arms.json"); continue
        R = ref[s]
        ind = prep(rows[s])
        M0 = masks(ind, {"qz": np.inf, "qv": np.inf, "or_qz": np.inf,
                         "or_qv": np.inf, "or_a": 1.0})
        n_and = int(M0["and_base"].sum())
        cal = calibrate(ind, n_and)
        M = masks(ind, cal)
        print(f"\n===== {s} ({ind['asset']}) 我 n_elig={ind['Eidx'].size} "
              f"参考 n_elig={R['n_elig']} | 我 n_and={n_and} 参考={R['arms']['and_base']['n']}")
        for k, v in cal.items():
            rv = R["cal"][k]
            eq = (abs(v - rv) < 5e-4) if isinstance(rv, float) else (v == rv)
            if not eq:
                print(f"   cal.{k}: 我 {v} vs 参考 {rv}  <<< 不一致"); bad += 1
        for a in CHECK:
            T = np.flatnonzero(M[a])
            Tref = np.array(R["trig"][a], int)
            same = (T.size == Tref.size) and bool((T == Tref).all())
            res = ratio_ci(ind, T)
            ra = R["arms"][a]
            dm = abs(res["mult"] - ra["mult"])
            dlo = abs(res["lo"] - ra["lo"])
            dhi = abs(res["hi"] - ra["hi"])
            flag = "OK " if (same and dm < 5e-4 and dlo < 5e-4 and dhi < 5e-4) else "!! "
            if flag == "!! ":
                bad += 1
            print(f" {flag}{a:<11} n {T.size:>4}/{ra['n']:<4} 触发集{'同' if same else '异'} "
                  f"blocks {res['blocks']}/{ra['blocks']} "
                  f"mult {res['mult']:.4f}/{ra['mult']:.4f} "
                  f"CI [{res['lo']:.4f},{res['hi']:.4f}] / [{ra['lo']:.4f},{ra['hi']:.4f}]")
    print(f"\n不一致项合计 {bad}")


if __name__ == "__main__":
    syms = sys.argv[1:] or ["VALE", "NVDA", "XOM", "SOFI", "KO", "BTC", "TSLA", "AAPL"]
    main(syms)
