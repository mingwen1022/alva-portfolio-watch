"""补充检查
  ① 共用净化基准 cb 自身是否可靠：各 sigma 十分位在 cb 池里还剩几天，回退到全局中位的比例
  ② 等块数对照组 price_eqblk 的经验零与安慰剂特异性（主表未算）
  ③ 配对差的切半稳定性（前半段 / 后半段各算一次）
"""
import json, os, sys, time
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mine import (prep, calibrate, masks, thr_for_count, ratio_ci_fast,
                  basepool_from, blocks_of, roster, _decile, NBOOT)
from run_all import full_basepool, calib_blocks, KS

OUT = os.path.dirname(os.path.abspath(__file__))


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
    E, Eidx = ind["E"], ind["Eidx"]
    az = np.abs(ind["z"])
    tgt = len(blocks_of(trig["and_base"]))
    tof = lambda t: np.flatnonzero(E & (az >= t))
    thr_b, _, _ = calib_blocks(az[E], tof, tgt, min(int(E.sum()) - 1, n_and * 6))
    trig["price_eqblk"] = tof(thr_b)

    bp_cb = basepool_from(ind, trig["or_base"])
    bp_np = full_basepool(ind)
    rec = {"sym": ind["sym"], "asset": ind["asset"], "vol_tier": ind["vol_tier"],
           "sector": ind["sector"], "years": ind["years"]}

    # ① cb 池各层剩余日数
    rec["cb_pool"] = [int(len(p)) for p in bp_cb]
    rec["cb_fallback_dec"] = int(sum(1 for p in bp_cb if len(p) < 10))
    rec["np_pool"] = [int(len(p)) for p in bp_np]

    # ② price_eqblk 的经验零 + 特异性
    lo_i, hi_i = int(Eidx[0]), int(Eidx[-1]); span = hi_i - lo_i + 1
    rng = np.random.default_rng(abs(hash(ind["sym"])) % (2 ** 31))
    deltas = rng.integers(int(span * .08), int(span * .92), size=200)
    rec["extra"] = {}
    for a in ["price_eqblk", "and_base"]:
        T = trig[a]
        ms = []
        for dl in deltas:
            Ts = np.unique(lo_i + ((T - lo_i + int(dl)) % span))
            Ts = Ts[np.isfinite(ind["V"][Ts]) & np.isfinite(ind["sigma"][Ts])]
            if Ts.size < 3: continue
            r = ratio_ci_fast(ind, Ts, fixed_basepool=bp_cb, want_ci=False)
            if r: ms.append(r["mult"])
        pl = {}
        for k in [0] + KS:
            Tk = T + k
            Tk = Tk[(Tk >= 0) & (Tk < ind["n"])]
            Tk = Tk[np.isfinite(ind["V"][Tk]) & np.isfinite(ind["sigma"][Tk])]
            if Tk.size < 3: continue
            r = ratio_ci_fast(ind, Tk, fixed_basepool=bp_cb, want_ci=False)
            if r: pl[str(k)] = r["mult"]
        rec["extra"][a] = {"null_med": float(np.median(ms)) if ms else None, "placebo": pl}

    # ③ 切半稳定性
    half = int(Eidx[len(Eidx) // 2])
    rec["half"] = {}
    for tag, sel in (("h1", lambda t: t <= half), ("h2", lambda t: t > half)):
        o = {}
        for a in ("and_base", "price_eq", "or_eq", "price_eqblk"):
            T = trig[a][sel(trig[a])]
            if T.size < 5: continue
            for nm, bp in (("cb", bp_cb), ("np", bp_np)):
                r = ratio_ci_fast(ind, T, fixed_basepool=bp, want_ci=False)
                if r: o[f"{a}_{nm}"] = r["mult"]
        rec["half"][tag] = o
    return rec


if __name__ == "__main__":
    rows = roster()
    t0 = time.time(); out = []
    with Pool(processes=int(os.environ.get("NPROC", "9"))) as p:
        for i, rec in enumerate(p.imap_unordered(one, rows)):
            out.append(rec)
            if (i + 1) % 20 == 0: print(f"{i+1}/{len(rows)}", flush=True)
    out.sort(key=lambda r: r["sym"])
    json.dump(out, open(os.path.join(OUT, "supp.json"), "w"), ensure_ascii=False, indent=1)
    print(f"完成 {len(out)} 只 {time.time()-t0:.0f}s")
