"""独立实现 · 从 plan.md §一 与 pv_engine 文档字符串的规格重写，不 import 仓库代码。

用途：复核 backtest/scripts/andor/arms.json 的 AND vs OR 结论。

规格（plan.md §一 + pv_engine docstring）
  r_t      = ln(c_t / c_{t-1})
  sigma_t  = 1.4826 * MAD(r[t-90 .. t-1])            需 >= 60 个非空样本
  z_t      = (r_t - median(r[t-90..t-1])) / sigma_t
  RVOL_t   = vol_t / median(vol[t-90 .. t-1] > 0)    需 >= 60 个正样本
  V_t      = sqrt(mean(r[t+1..t+5]^2))               任一为空则空；sigma 为空处置空
  基准     = sigma 十分位分层，层内非触发日 V 中位；触发日 ±5 天剔除
  倍数     = median_t( V_t / base[decile(t)] )
  区间     = 整块自助（块 = 相邻触发间隔 < 5 交易日），基准同步重抽
  判据     = 95% 下界 > 1.0 且 独立块数 >= 5
"""
import csv, math, os
import numpy as np

W = 90
FWD = 5
PURGE = 5
NDEC = 10
SEED = 20260819
NBOOT = 4000

ROOT = "/Users/ming/project/alva/backtest"
DIR_EQ = f"{ROOT}/universe/data/daily"
DIR_CR = f"{ROOT}/universe/data/crypto"
UNIV = f"{ROOT}/universe/universe.csv"


# ---------------------------------------------------------------- 数据
def read_bars(sym, asset):
    d = DIR_CR if asset == "crypto" else DIR_EQ
    rows = []
    with open(os.path.join(d, f"{sym}.csv")) as f:
        for row in csv.DictReader(f):
            try:
                o = float(row["open"]); c = float(row["close"]); v = float(row["volume"])
            except (TypeError, ValueError):
                continue
            rows.append((row["date"], o, c, v))
    rows.sort(key=lambda x: x[0])
    dates = [x[0] for x in rows]
    return (dates,
            np.array([x[1] for x in rows], float),
            np.array([x[2] for x in rows], float),
            np.array([x[3] for x in rows], float))


def roster(include_benchmark=False):
    out = []
    for r in csv.DictReader(open(UNIV)):
        if r["stratum"] == "benchmark" and not include_benchmark:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------- 指标
def indicators(close, vol, ann):
    n = len(close)
    r = np.full(n, np.nan)
    good = (close[:-1] > 0) & (close[1:] > 0)
    r[1:][good] = np.log(close[1:][good] / close[:-1][good])

    sigma = np.full(n, np.nan)
    z = np.full(n, np.nan)
    rvol = np.full(n, np.nan)
    center = np.full(n, np.nan)
    for t in range(n):
        win = r[max(1, t - W):t]
        win = win[np.isfinite(win)]
        if win.size >= 60 and np.isfinite(r[t]):
            med = np.median(win)
            s = 1.4826 * np.median(np.abs(win - med))
            if s > 0:
                sigma[t] = s
                center[t] = med
                z[t] = (r[t] - med) / s
        wv = vol[max(0, t - W):t]
        wv = wv[wv > 0]
        if wv.size >= 60:
            mv = np.median(wv)
            if mv > 0:
                rvol[t] = vol[t] / mv

    V = np.full(n, np.nan)
    sq = r ** 2
    for t in range(n - FWD):
        seg = sq[t + 1: t + 1 + FWD]
        if np.isnan(seg).any():
            continue
        V[t] = math.sqrt(float(seg.mean()))
    V[np.isnan(sigma)] = np.nan
    return dict(n=n, r=r, sigma=sigma, z=z, rvol=rvol, V=V,
                avol=sigma * math.sqrt(ann), center=center)


def blocks_of(idx, gap=FWD):
    idx = np.sort(np.asarray(idx, int))
    if idx.size == 0:
        return []
    out, cur = [], [idx[0]]
    for i in idx[1:]:
        if i - cur[-1] < gap:
            cur.append(i)
        else:
            out.append(np.array(cur)); cur = [i]
    out.append(np.array(cur))
    return out


# ---------------------------------------------------------------- 倍数 + 区间
def _decile(sigma, valid, ndec=NDEC):
    sv = sigma[valid]
    cuts = np.quantile(sv, np.linspace(0, 1, ndec + 1)[1:-1])
    dec = np.full(len(sigma), -1, int)
    dec[valid] = np.searchsorted(cuts, sv, side="right")
    return dec


def ratio_ci(ind, trig, purge_from=None, nboot=NBOOT, seed=SEED, ndec=NDEC,
             fixed_basepool=None):
    """fixed_basepool: 若给定，直接用该 basepool（用于「共用基准」诊断）。"""
    V, sigma, n = ind["V"], ind["sigma"], ind["n"]
    valid = np.flatnonzero(np.isfinite(V) & np.isfinite(sigma))
    if valid.size < 200:
        return None
    dec = _decile(sigma, valid, ndec)

    T = np.array([t for t in np.asarray(trig, int)
                  if np.isfinite(V[t]) and np.isfinite(sigma[t])], int)
    if T.size < 3:
        return None

    if fixed_basepool is None:
        pf = T if purge_from is None else np.asarray(purge_from, int)
        blocked = np.zeros(n, bool)
        for t in pf:
            blocked[max(0, t - PURGE): min(n, t + PURGE + 1)] = True
        basepool = [valid[(dec[valid] == d) & (~blocked[valid])] for d in range(ndec)]
    else:
        basepool = fixed_basepool

    filled = [p for p in basepool if len(p)]
    if not filled:
        return None
    gpool = np.concatenate(filled)
    if gpool.size < 100:
        return None
    gmed = float(np.median(V[gpool]))
    base = np.array([float(np.median(V[p])) if len(p) >= 10 else gmed for p in basepool])
    if (base <= 0).any():
        return None

    point = float(np.median(V[T] / base[dec[T]]))

    bl = blocks_of(T)
    nb = len(bl)
    rng = np.random.default_rng(seed)
    bb = np.empty((nboot, ndec))
    for d in range(ndec):
        pv = V[basepool[d]]
        if len(pv) >= 10:
            ii = rng.integers(0, len(pv), size=(nboot, len(pv)))
            bb[:, d] = np.median(pv[ii], axis=1)
        else:
            bb[:, d] = gmed
    blV = [V[b] for b in bl]
    blD = [dec[b] for b in bl]
    reps = np.empty(nboot)
    for b in range(nboot):
        pick = rng.integers(0, nb, nb)
        vv = np.concatenate([blV[j] for j in pick])
        dd = np.concatenate([blD[j] for j in pick])
        reps[b] = np.median(vv / bb[b][dd])
    reps.sort()
    lo = float(reps[int(0.025 * nboot)])
    hi = float(reps[int(0.975 * nboot)])
    return dict(n=int(T.size), blocks=int(nb), mult=point, lo=lo, hi=hi,
                pass_=bool(lo > 1.0 and nb >= 5), base=base, dec=dec, T=T,
                nbase=int(gpool.size), base_med=float(np.median(base)))


# ---------------------------------------------------------------- 标的准备
def prep(row):
    sym = row["symbol"]
    asset = "crypto" if row["asset_class"] == "crypto" else "us_equity"
    ann = 365 if asset == "crypto" else 252
    dates, o, c, v = read_bars(sym, asset)
    ind = indicators(c, v, ann)
    E = np.isfinite(ind["V"]) & np.isfinite(ind["sigma"]) & \
        np.isfinite(ind["z"]) & np.isfinite(ind["rvol"])
    ind["E"] = E
    ind["Eidx"] = np.flatnonzero(E)
    ind["sym"] = sym; ind["asset"] = asset; ind["ann"] = ann
    ind["dates"] = dates; ind["open"] = o; ind["close"] = c; ind["vol"] = v
    ind["thv"] = 3.0 if asset == "crypto" else 2.0
    ind["years"] = ind["Eidx"].size / ann
    av = ind["avol"][np.isfinite(ind["avol"])]
    ind["sigma_ann"] = float(np.median(av)) if av.size else float("nan")
    s = ind["sigma_ann"]
    ind["vol_tier"] = ("低波 <25%" if s < 0.25 else
                       "中波 25-50%" if s < 0.50 else "高波 >50%")
    for k in ("sector", "size_tier", "stratum"):
        ind[k] = row[k]
    ind["advol"] = float(row["avg_dollar_vol_usd"]) if row["avg_dollar_vol_usd"] else float("nan")
    return ind


# ---------------------------------------------------------------- 等触发数校准（独立重写）
def thr_for_count(x, n):
    """在 x 上找阈值 thr，使 #{x >= thr} 尽量等于 n。
    独立路线：在唯一值上按计数搜索（而非直接取第 n 大），用于交叉验证 topn_thr。"""
    if n <= 0:
        return float("inf")
    if n >= x.size:
        return -float("inf")
    xs = np.sort(x)
    u = np.unique(xs)                                   # 升序
    cnt = x.size - np.searchsorted(xs, u, side="left")  # #{x >= u_i}，随 i 单调不增
    ok = np.flatnonzero(cnt >= n)
    if ok.size == 0:
        return float(u[0])
    return float(u[ok[-1]])


def calibrate(ind, n_target):
    az = np.abs(ind["z"])[ind["E"]]
    rv = ind["rvol"][ind["E"]]
    out = {}
    out["qz"] = thr_for_count(az, n_target)
    out["qv"] = thr_for_count(rv, n_target)
    # OR 两腿等尾质量：每腿取 m，并集数关于 m 单调不减
    lo, hi = max(1, (n_target + 1) // 2), n_target
    best = None
    for m in range(lo, hi + 1):
        tz = thr_for_count(az, m); tv = thr_for_count(rv, m)
        u = int(((az >= tz) | (rv >= tv)).sum())
        d = abs(u - n_target)
        if best is None or d < best[0]:
            best = (d, m, tz, tv, u)
        if u >= n_target:
            break
    out["or_m"], out["or_qz"], out["or_qv"], out["or_n"] = best[1], best[2], best[3], best[4]
    # OR 等比例放大
    thz, thv = 1.5, ind["thv"]
    best2 = None
    for a in np.arange(1.0, 8.001, 0.005):
        u = int(((az >= a * thz) | (rv >= a * thv)).sum())
        d = abs(u - n_target)
        if best2 is None or d < best2[0]:
            best2 = (d, float(a), u)
        if u < n_target:
            break
    out["or_a"], out["or_scale_n"] = best2[1], best2[2]
    return out


ARMS = ["and_base", "price_base", "vol_base", "or_base",
        "price_eq", "vol_eq", "or_eq", "or_scale", "price_only", "vol_only", "both_none"]


def masks(ind, cal):
    z = np.abs(ind["z"]); rv = ind["rvol"]; E = ind["E"]; thv = ind["thv"]
    pz = E & (z >= 1.5)
    pv = E & (rv >= thv)
    m = {
        "and_base": pz & pv,
        "price_base": pz,
        "vol_base": pv,
        "or_base": pz | pv,
        "price_eq": E & (z >= cal["qz"]),
        "vol_eq": E & (rv >= cal["qv"]),
        "or_eq": E & ((z >= cal["or_qz"]) | (rv >= cal["or_qv"])),
        "or_scale": E & ((z >= cal["or_a"] * 1.5) | (rv >= cal["or_a"] * thv)),
        # 差集：价格命中但量能未命中 / 量能命中但价格未命中
        "price_only": pz & (~pv),
        "vol_only": pv & (~pz),
    }
    return m


# ---------------------------------------------------------------- 向量化自助（与逐块循环等价）
def _wmedian_rows(vals, cnt):
    """按行求加权中位数，权重为整数重复次数，语义与 np.median(重复展开后的数组) 一致。"""
    order = np.argsort(vals, axis=1, kind="stable")
    sv = np.take_along_axis(vals, order, axis=1)
    sw = np.take_along_axis(cnt, order, axis=1)
    cw = np.cumsum(sw, axis=1)
    L = cw[:, -1]
    p1 = (L - 1) // 2
    p2 = L // 2
    i1 = (cw > p1[:, None]).argmax(axis=1)
    i2 = (cw > p2[:, None]).argmax(axis=1)
    rows = np.arange(vals.shape[0])
    return 0.5 * (sv[rows, i1] + sv[rows, i2])


def ratio_ci_fast(ind, trig, purge_from=None, nboot=NBOOT, seed=SEED, ndec=NDEC,
                  fixed_basepool=None, want_ci=True, chunk=1000):
    V, sigma, n = ind["V"], ind["sigma"], ind["n"]
    valid = np.flatnonzero(np.isfinite(V) & np.isfinite(sigma))
    if valid.size < 200:
        return None
    dec = _decile(sigma, valid, ndec)
    T = np.asarray(trig, int)
    T = T[np.isfinite(V[T]) & np.isfinite(sigma[T])]
    if T.size < 3:
        return None
    if fixed_basepool is None:
        pf = T if purge_from is None else np.asarray(purge_from, int)
        blocked = np.zeros(n, bool)
        for t in pf:
            blocked[max(0, t - PURGE): min(n, t + PURGE + 1)] = True
        basepool = [valid[(dec[valid] == d) & (~blocked[valid])] for d in range(ndec)]
    else:
        basepool = fixed_basepool
    filled = [p for p in basepool if len(p)]
    if not filled:
        return None
    gpool = np.concatenate(filled)
    if gpool.size < 100:
        return None
    gmed = float(np.median(V[gpool]))
    base = np.array([float(np.median(V[p])) if len(p) >= 10 else gmed for p in basepool])
    if (base <= 0).any():
        return None
    point = float(np.median(V[T] / base[dec[T]]))
    bl = blocks_of(T)
    nb = len(bl)
    out = dict(n=int(T.size), blocks=int(nb), mult=point,
               base_med=float(np.median(base)), nbase=int(gpool.size))
    if not want_ci:
        out.update(lo=None, hi=None, pass_=None)
        return out
    rng = np.random.default_rng(seed)
    bb = np.empty((nboot, ndec))
    for d in range(ndec):
        pv = V[basepool[d]]
        if len(pv) >= 10:
            ii = rng.integers(0, len(pv), size=(nboot, len(pv)))
            bb[:, d] = np.median(pv[ii], axis=1)
        else:
            bb[:, d] = gmed
    bid = np.empty(T.size, int)
    pos = {int(t): i for i, t in enumerate(T)}
    for j, b in enumerate(bl):
        for t in b:
            bid[pos[int(t)]] = j
    VT = V[T]; DT = dec[T]
    reps = np.empty(nboot)
    done = 0
    while done < nboot:
        m = min(chunk, nboot - done)
        pick = rng.integers(0, nb, size=(m, nb))
        flat = (pick + np.arange(m)[:, None] * nb).ravel()
        counts = np.bincount(flat, minlength=m * nb).reshape(m, nb)
        cnt = counts[:, bid]
        ratios = VT[None, :] / bb[done:done + m][:, DT]
        reps[done:done + m] = _wmedian_rows(ratios, cnt)
        done += m
    reps.sort()
    lo = float(reps[int(0.025 * nboot)]); hi = float(reps[int(0.975 * nboot)])
    out.update(lo=lo, hi=hi, pass_=bool(lo > 1.0 and nb >= 5))
    return out


def basepool_from(ind, purge_from, ndec=NDEC):
    V, sigma, n = ind["V"], ind["sigma"], ind["n"]
    valid = np.flatnonzero(np.isfinite(V) & np.isfinite(sigma))
    dec = _decile(sigma, valid, ndec)
    blocked = np.zeros(n, bool)
    for t in np.asarray(purge_from, int):
        blocked[max(0, t - PURGE): min(n, t + PURGE + 1)] = True
    return [valid[(dec[valid] == d) & (~blocked[valid])] for d in range(ndec)]
