"""AND vs OR 独立复核主运行

三套基准（分母）
  own  逐对照组各自净化 ±5 天          —— R34 / registry 判据用的口径
  cb   净化集统一取 or_base            —— 对照组无关，可比但池子被抽薄
  np   完全不净化                      —— 对照组无关，池子完整

对照组之间只有分母一致时才可比。own 口径下 price_base 的净化会剔掉 60-90% 的日子，
且剔掉的正是高波日 → 基准被压低 → 倍数被抬高。这就是本次复核的核心检查点。

另产出：安慰剂平移 · 经验零（环形平移）· 等块数校准 · 样本外校准
"""
import json, os, sys, time
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mine import (prep, calibrate, masks, thr_for_count, ratio_ci_fast,
                  basepool_from, blocks_of, roster, _decile, NBOOT)

OUT = os.path.dirname(os.path.abspath(__file__))
KS = [-40, -30, -20, -15, -10, -8, -6, 6, 8, 10, 15, 20, 30, 40]
PLACEBO_ARMS = ["and_base", "price_base", "vol_base", "or_base", "price_eq", "vol_eq", "or_eq"]
NULL_ARMS = ["and_base", "price_base", "vol_base", "or_base", "price_eq", "vol_eq", "or_eq"]
NULL_POINT, NULL_CI, NBOOT_NULL = 200, 80, 1000


def full_basepool(ind, ndec=10):
    V, sigma = ind["V"], ind["sigma"]
    valid = np.flatnonzero(np.isfinite(V) & np.isfinite(sigma))
    dec = _decile(sigma, valid, ndec)
    return [valid[dec[valid] == d] for d in range(ndec)]


def calib_blocks(x, trig_of, target_blocks, n_hi):
    lo, hi, best = 3, n_hi, None
    while lo <= hi:
        mid = (lo + hi) // 2
        thr = thr_for_count(x, mid)
        T = trig_of(thr)
        b = len(blocks_of(T))
        d = abs(b - target_blocks)
        if best is None or d < best[0]:
            best = (d, mid, thr, len(T), b)
        if b < target_blocks: lo = mid + 1
        elif b > target_blocks: hi = mid - 1
        else: break
    return best[2], best[3], best[4]


def one(row):
    t0 = time.time()
    try:
        ind = prep(row)
    except Exception as e:
        return {"sym": row["symbol"], "error": f"prep {e}"}
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
    az_all = np.abs(ind["z"])
    tgt_blocks = len(blocks_of(trig["and_base"]))
    tof = lambda thr: np.flatnonzero(E & (az_all >= thr))
    thr_b, n_b, got_b = calib_blocks(az_all[E], tof, tgt_blocks, min(int(E.sum()) - 1, n_and * 6))
    trig["price_eqblk"] = tof(thr_b)

    bp_cb = basepool_from(ind, trig["or_base"])
    bp_np = full_basepool(ind)

    rec = dict(sym=ind["sym"], asset=ind["asset"], sector=ind["sector"],
               size_tier=ind["size_tier"], vol_tier=ind["vol_tier"],
               stratum=ind["stratum"], sigma_ann=round(ind["sigma_ann"], 4),
               advol=ind["advol"], years=round(ind["years"], 2),
               n_elig=int(Eidx.size), thv=ind["thv"], n_and=n_and,
               cal={k: (round(v, 4) if isinstance(v, float) else v) for k, v in cal.items()},
               cal_blocks=dict(thr=round(float(thr_b), 4), n=int(n_b),
                               blocks=int(got_b), target_blocks=int(tgt_blocks)),
               arms={}, placebo={}, null={})

    for a, T in trig.items():
        if T.size < 3:
            rec["arms"][a] = dict(n=int(T.size)); continue
        d = dict(n=int(T.size), freq=round(T.size / ind["years"], 2),
                 med_absz=float(np.median(np.abs(ind["z"][T]))),
                 med_rvol=float(np.median(ind["rvol"][T])),
                 med_abs_ret=float(np.median(np.abs(ind["r"][T]))))
        for tag, bp in (("", None), ("_cb", bp_cb), ("_np", bp_np)):
            r = ratio_ci_fast(ind, T, fixed_basepool=bp, nboot=NBOOT)
            if r is None:
                continue
            d["blocks"] = r["blocks"]
            d["mult" + tag] = r["mult"]; d["lo" + tag] = r["lo"]
            d["hi" + tag] = r["hi"]; d["passed" + tag] = r["pass_"]
            d["base_med" + tag] = r["base_med"]; d["nbase" + tag] = r["nbase"]
        rec["arms"][a] = d

    # ---- 安慰剂平移：固定基准，避免净化池被抽干 ----
    nmax = ind["n"]
    for a in PLACEBO_ARMS:
        T = trig[a]
        if T.size < 3: continue
        o = {}
        for k in [0] + KS:
            Tk = T + k
            Tk = Tk[(Tk >= 0) & (Tk < nmax)]
            Tk = Tk[np.isfinite(ind["V"][Tk]) & np.isfinite(ind["sigma"][Tk])]
            if Tk.size < 3: continue
            e = {}
            for tag, bp in (("cb", bp_cb), ("np", bp_np)):
                r = ratio_ci_fast(ind, Tk, fixed_basepool=bp, want_ci=False)
                if r: e[tag] = r["mult"]; e["n"] = r["n"]; e["blocks"] = r["blocks"]
            if e: o[str(k)] = e
        rec["placebo"][a] = o

    # ---- 经验零：触发集环形平移（保 n / 保块结构，破时间对齐） ----
    lo_i, hi_i = int(Eidx[0]), int(Eidx[-1])
    span = hi_i - lo_i + 1
    rng = np.random.default_rng(abs(hash(ind["sym"])) % (2 ** 31))
    deltas = rng.integers(int(span * 0.08), int(span * 0.92), size=NULL_POINT)
    for a in NULL_ARMS:
        T = trig[a]
        if T.size < 3: continue
        m_own, m_cb, passes = [], [], []
        for i, dl in enumerate(deltas):
            Ts = np.unique(lo_i + ((T - lo_i + int(dl)) % span))
            Ts = Ts[np.isfinite(ind["V"][Ts]) & np.isfinite(ind["sigma"][Ts])]
            if Ts.size < 3: continue
            r_cb = ratio_ci_fast(ind, Ts, fixed_basepool=bp_cb, want_ci=False)
            if r_cb: m_cb.append(r_cb["mult"])
            if i < NULL_CI:
                r_own = ratio_ci_fast(ind, Ts, nboot=NBOOT_NULL)   # 自身净化 = 判据口径
                if r_own:
                    m_own.append(r_own["mult"]); passes.append(bool(r_own["pass_"]))
        e = dict(n_shift_cb=len(m_cb), n_shift_own=len(m_own))
        if m_cb:
            e.update(med_cb=float(np.median(m_cb)), q05_cb=float(np.quantile(m_cb, .05)),
                     q95_cb=float(np.quantile(m_cb, .95)))
        if m_own:
            e.update(med_own=float(np.median(m_own)),
                     q95_own=float(np.quantile(m_own, .95)))
        if passes:
            e.update(pass_rate=float(np.mean(passes)), n_pass_eval=len(passes))
        rec["null"][a] = e

    # ---- 样本外校准 ----
    half = int(Eidx[len(Eidx) // 2])
    firstE = Eidx[Eidx <= half]; secondE = Eidx[Eidx > half]
    Ta1 = trig["and_base"][trig["and_base"] <= half]
    Ta2 = trig["and_base"][trig["and_base"] > half]
    if Ta1.size >= 5 and Ta2.size >= 5 and secondE.size > 50:
        thr_oos = thr_for_count(az_all[firstE], int(Ta1.size))
        thr_is = thr_for_count(az_all[secondE], int(Ta2.size))
        o = {"thr_oos": float(thr_oos), "thr_is": float(thr_is)}
        for nm, TT in (("and_h2", Ta2),
                       ("price_oos_h2", secondE[az_all[secondE] >= thr_oos]),
                       ("price_is_h2", secondE[az_all[secondE] >= thr_is])):
            r = ratio_ci_fast(ind, TT, fixed_basepool=bp_cb, nboot=NBOOT)
            r2 = ratio_ci_fast(ind, TT, nboot=NBOOT)
            if r:
                o[nm] = dict(n=r["n"], blocks=r["blocks"], mult_cb=r["mult"],
                             lo_cb=r["lo"], passed_cb=r["pass_"],
                             mult=(r2["mult"] if r2 else None))
        rec["oos"] = o

    rec["secs"] = round(time.time() - t0, 1)
    return rec


if __name__ == "__main__":
    rows = roster()
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        rows = [r for r in rows if r["symbol"] in only]
    t0 = time.time()
    out = []
    with Pool(processes=int(os.environ.get("NPROC", "9"))) as p:
        for i, rec in enumerate(p.imap_unordered(one, rows)):
            out.append(rec)
            print(f"[{i+1}/{len(rows)}] {rec.get('sym')} {rec.get('error','')} "
                  f"{rec.get('secs','')}s", flush=True)
    out.sort(key=lambda r: r["sym"])
    tag = "res_subset.json" if only else "res.json"
    json.dump(out, open(os.path.join(OUT, tag), "w"), ensure_ascii=False, indent=1)
    print(f"完成 {len(out)} 只 用时 {time.time()-t0:.0f}s")
