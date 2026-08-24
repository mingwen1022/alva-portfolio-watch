"""④ 加密 vs 美股分化：按年分块，估计配对差在截面上的相关，给出有效独立样本量。

逐标的只有一个配对差观测，无法直接估计截面相关。
做法：把配对差拆成「标的 × 日历年」的面板，用年作为重复观测估计标的间相关，
再用设计效应 n_eff = n / (1 + (n-1)·rho_bar) 折算，并做按年整块自助。
"""
import json, os, sys, time
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mine import prep, calibrate, masks, ratio_ci_fast, basepool_from, roster
from run_all import full_basepool

OUT = os.path.dirname(os.path.abspath(__file__))
YEARS = [str(y) for y in range(2018, 2027)]
MINTRIG = 5


def one(row):
    try:
        ind = prep(row)
    except Exception as e:
        return {"sym": row["symbol"], "error": str(e)}
    if ind["Eidx"].size < 300:
        return {"sym": row["symbol"], "error": "n_elig<300"}
    M0 = masks(ind, {"qz": np.inf, "qv": np.inf, "or_qz": np.inf, "or_qv": np.inf, "or_a": 1.0})
    n_and = int(M0["and_base"].sum())
    if n_and < 10:
        return {"sym": row["symbol"], "error": "n_and<10"}
    cal = calibrate(ind, n_and)
    M = masks(ind, cal)
    trig = {k: np.flatnonzero(v) for k, v in M.items()}
    bp = {"cb": basepool_from(ind, trig["or_base"]), "np": full_basepool(ind)}
    yr = np.array([d[:4] for d in ind["dates"]])
    rec = {"sym": ind["sym"], "asset": ind["asset"], "vol_tier": ind["vol_tier"],
           "sector": ind["sector"], "panel": {}}
    for y in YEARS:
        cell = {}
        for a in ("and_base", "price_eq", "or_eq", "price_eqblk" if "price_eqblk" in trig else "or_eq"):
            T = trig[a][yr[trig[a]] == y]
            if T.size < MINTRIG: continue
            for nm in ("cb", "np"):
                r = ratio_ci_fast(ind, T, fixed_basepool=bp[nm], want_ci=False)
                if r: cell[f"{a}_{nm}"] = r["mult"]
            cell[f"{a}_n"] = int(T.size)
        if cell: rec["panel"][y] = cell
    return rec


if __name__ == "__main__":
    t0 = time.time(); out = []
    with Pool(processes=int(os.environ.get("NPROC", "9"))) as p:
        for i, r in enumerate(p.imap_unordered(one, roster())):
            out.append(r)
            if (i + 1) % 25 == 0: print(f"{i+1}", flush=True)
    out.sort(key=lambda r: r["sym"])
    json.dump(out, open(os.path.join(OUT, "panel.json"), "w"), ensure_ascii=False, indent=1)
    print(f"完成 {len(out)} {time.time()-t0:.0f}s")
