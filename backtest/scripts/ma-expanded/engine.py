"""MA 族重跑引擎（扩池版）。

判据（现行）：相对基准倍数的 95% 区间下界 > 1.0  且  独立块数 >= 5

口径按 revisions.md R28 定稿：
  V_t   = sqrt(mean(r_{t+1..t+5}^2))            原始 5 日已实现波动，**不除以 sigma_rob**
  基准   sigma_rob 十分位分层 + 剔除触发日 ±5 天（净化），基准纳入自助重抽
  自助   整块自助（相邻触发间隔 < 5 交易日归一块），固定种子

同时保留 legacy 口径（V = RV5/sigma_rob，基准 = 全体非触发日中位）用于与历史数字对照。
"""
import os, math, csv, datetime
import numpy as np

ROOT = "/Users/ming/project/alva/backtest"
D_LEGACY = f"{ROOT}/data/stocks-daily"          # date,close,volume 无表头（11 只老样本）
D_UNI = f"{ROOT}/universe/data/daily"           # date,open,high,low,close,volume 有表头（92 只）
D_CRYPTO = f"{ROOT}/universe/data/crypto"

W = 90          # sigma_rob 滚动窗
FWD = 5         # 前瞻窗
MINW = 60       # 窗内最少有效收益数
SEED = 20260819
NBOOT = 4000
NDEC = 10       # sigma 十分位


# ---------------- 数据 ----------------
def load_csv(path):
    dates, close, vol = [], [], []
    with open(path) as f:
        first = True
        for ln in f:
            p = ln.strip().split(",")
            if not p or len(p) < 2:
                continue
            if first:
                first = False
                if not p[0][:1].isdigit():
                    continue
            if len(p) >= 6:
                dates.append(p[0]); close.append(float(p[4])); vol.append(float(p[5]))
            else:
                dates.append(p[0]); close.append(float(p[1])); vol.append(float(p[2]))
    order = np.argsort(np.array(dates))
    dates = [dates[i] for i in order]
    return dates, np.array(close)[order], np.array(vol)[order]


def load(sym, source="uni"):
    if source == "legacy":
        return load_csv(f"{D_LEGACY}/{sym}.csv")
    if source == "crypto":
        return load_csv(f"{D_CRYPTO}/{sym}.csv")
    return load_csv(f"{D_UNI}/{sym}.csv")


def build(sym, source="uni"):
    """-> dict(dates, idx, r, sigma, RV5, V_legacy, dec, n)"""
    dates, close, vol = load(sym, source)
    n = len(dates)
    r = np.full(n, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        good = (close[:-1] > 0) & (close[1:] > 0)
        r[1:][good] = np.log(close[1:][good] / close[:-1][good])

    sigma = np.full(n, np.nan)
    for t in range(n):
        lo = max(1, t - W)
        w = r[lo:t]
        w = w[~np.isnan(w)]
        if len(w) < MINW or np.isnan(r[t]):
            continue
        m = np.median(w)
        s = 1.4826 * np.median(np.abs(w - m))
        if s > 0:
            sigma[t] = s

    RV5 = np.full(n, np.nan)
    for t in range(n - FWD):
        rr = r[t + 1:t + 1 + FWD]
        if np.isnan(rr).any():
            continue
        RV5[t] = math.sqrt(float(np.mean(rr * rr)))
    # 末尾 FWD 天没有完整前瞻窗
    V_legacy = RV5 / sigma

    return dict(sym=sym, dates=dates, idx={d: i for i, d in enumerate(dates)},
                close=close, vol=vol, r=r, sigma=sigma, RV5=RV5,
                V_legacy=V_legacy, n=n)


def zrob(s):
    """当日稳健 z（M2），窗口同 sigma"""
    n = s["n"]; r = s["r"]; z = np.full(n, np.nan)
    for t in range(n):
        lo = max(1, t - W)
        w = r[lo:t]; w = w[~np.isnan(w)]
        if len(w) < MINW or np.isnan(r[t]):
            continue
        m = np.median(w)
        sd = 1.4826 * np.median(np.abs(w - m))
        if sd > 0:
            z[t] = (r[t] - m) / sd
    return z


def rvol(s):
    """M3 相对成交量：当日量 / 前 90 日量中位"""
    n = s["n"]; v = s["vol"]; out = np.full(n, np.nan)
    for t in range(n):
        lo = max(0, t - W)
        w = v[lo:t]; w = w[w > 0]
        if len(w) >= MINW:
            m = np.median(w)
            if m > 0:
                out[t] = v[t] / m
    return out


# ---------------- 块 ----------------
def blocks_of(idxs, gap=FWD):
    """相邻触发（交易日下标）间隔 < gap → 同块"""
    idxs = sorted(idxs); out, cur = [], []
    for i in idxs:
        if cur and i - cur[-1] >= gap:
            out.append(cur); cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


# ---------------- 相对基准倍数 ----------------
def _wmedian(vals, wts):
    o = np.argsort(vals)
    v = vals[o]; w = wts[o]
    cw = np.cumsum(w)
    if cw[-1] <= 0:
        return np.nan
    cw = cw / cw[-1]
    k = int(np.searchsorted(cw, 0.5))
    return float(v[min(k, len(v) - 1)])


def ratio_ci(s, trig_idx, win_lo, win_hi, spec="r28", nboot=NBOOT, seed=SEED,
             purge=FWD, ndec=NDEC):
    """spec: 'r28'（V 原始 + sigma 十分位分层净化基准）或 'legacy'（V/sigma + 全体非触发中位）

    返回 dict(n, blocks, mult, lo, hi, pass_) 或 None
    """
    V = s["RV5"] if spec == "r28" else s["V_legacy"]
    sig = s["sigma"]
    n = s["n"]
    ok = np.zeros(n, bool)
    ok[win_lo:win_hi + 1] = True
    ok &= ~np.isnan(V) & ~np.isnan(sig)

    T = np.array(sorted(i for i in trig_idx if 0 <= i < n and ok[i]), dtype=int)
    if len(T) < 3:
        return None
    bl = blocks_of(T.tolist())

    rng = np.random.default_rng(seed)

    if spec == "legacy":
        trigset = set(int(i) for i in trig_idx)
        base_idx = np.array([i for i in range(n) if ok[i] and i not in trigset], dtype=int)
        if len(base_idx) < 30:
            return None
        base = float(np.median(V[base_idx]))
        if base <= 0:
            return None
        pt = float(np.median(V[T])) / base
        reps = np.empty(nboot)
        for b in range(nboot):
            pick = rng.integers(0, len(bl), len(bl))
            samp = np.concatenate([np.array(bl[j], dtype=int) for j in pick])
            reps[b] = np.median(V[samp]) / base
    else:
        # 净化：剔除任一触发日 ±purge 天
        drop = np.zeros(n, bool)
        for i in trig_idx:
            lo = max(0, int(i) - purge); hi = min(n - 1, int(i) + purge)
            drop[lo:hi + 1] = True
        base_mask = ok & ~drop
        base_idx = np.flatnonzero(base_mask)
        if len(base_idx) < 50:
            return None

        # sigma 十分位（在样本窗内、V 可用的日子上定档）
        pool = np.flatnonzero(ok)
        edges = np.quantile(sig[pool], np.linspace(0, 1, ndec + 1))
        edges[0] = -np.inf; edges[-1] = np.inf
        dec = np.full(n, -1, dtype=int)
        dec[pool] = np.clip(np.searchsorted(edges, sig[pool], side="right") - 1, 0, ndec - 1)

        base_dec = dec[base_idx]
        base_V = V[base_idx]
        # 每档基准日下标，供自助重抽
        by_dec = [base_idx[base_dec == d] for d in range(ndec)]

        def stratified_base(tr_idx, b_by_dec):
            """基准 = 与触发日 sigma 档分布匹配的加权中位"""
            cnt = np.bincount(dec[tr_idx], minlength=ndec).astype(float)
            vals, wts = [], []
            for d in range(ndec):
                if cnt[d] <= 0 or len(b_by_dec[d]) == 0:
                    continue
                vv = V[b_by_dec[d]]
                vals.append(vv)
                wts.append(np.full(len(vv), cnt[d] / len(vv)))
            if not vals:
                return np.nan
            return _wmedian(np.concatenate(vals), np.concatenate(wts))

        b0 = stratified_base(T, by_dec)
        if not (b0 > 0):
            return None
        pt = float(np.median(V[T])) / b0

        reps = np.empty(nboot)
        for b in range(nboot):
            pick = rng.integers(0, len(bl), len(bl))
            samp = np.concatenate([np.array(bl[j], dtype=int) for j in pick])
            # 基准同时重抽（档内有放回）
            bb = [g[rng.integers(0, len(g), len(g))] if len(g) else g for g in by_dec]
            bs = stratified_base(samp, bb)
            reps[b] = np.median(V[samp]) / bs if bs > 0 else np.nan
        reps = reps[~np.isnan(reps)]
        base_idx = base_idx  # keep

    reps = np.sort(reps)
    lo = float(reps[int(0.025 * len(reps))])
    hi = float(reps[min(len(reps) - 1, int(0.975 * len(reps)))])
    return dict(n=int(len(T)), blocks=len(bl), mult=float(pt), lo=lo, hi=hi,
                nbase=int(len(base_idx)),
                pass_=bool(lo > 1.0 and len(bl) >= 5))


def norm_V(s, trig_idx, win_lo, win_hi, purge=FWD, ndec=NDEC):
    """返回按 sigma 十分位归一化的 V（V_t / 该档净化基准中位），用于跨标的合并（M16）。

    仅在同一标的内做归一，跨标的比较的是无量纲比值。
    """
    V = s["RV5"]; sig = s["sigma"]; n = s["n"]
    ok = np.zeros(n, bool); ok[win_lo:win_hi + 1] = True
    ok &= ~np.isnan(V) & ~np.isnan(sig)
    drop = np.zeros(n, bool)
    for i in trig_idx:
        lo = max(0, int(i) - purge); hi = min(n - 1, int(i) + purge)
        drop[lo:hi + 1] = True
    base_idx = np.flatnonzero(ok & ~drop)
    pool = np.flatnonzero(ok)
    if len(base_idx) < 50 or len(pool) < 100:
        return None, None
    edges = np.quantile(sig[pool], np.linspace(0, 1, ndec + 1))
    edges[0] = -np.inf; edges[-1] = np.inf
    dec = np.full(n, -1, dtype=int)
    dec[pool] = np.clip(np.searchsorted(edges, sig[pool], side="right") - 1, 0, ndec - 1)
    m = np.full(ndec, np.nan)
    for d in range(ndec):
        g = base_idx[dec[base_idx] == d]
        if len(g) >= 10:
            m[d] = np.median(V[g])
    out = np.full(n, np.nan)
    for i in pool:
        d = dec[i]
        if d >= 0 and m[d] > 0:
            out[i] = V[i] / m[d]
    return out, dec


# ---------------- 交易日对齐 ----------------
def to_trading(s, day, shift=0):
    """日历日 -> 该标的交易日下标；day 非交易日则取其后第一个交易日；shift 为交易日平移"""
    ds = s["dates"]
    lo, hi = 0, len(ds)
    while lo < hi:
        mid = (lo + hi) // 2
        if ds[mid] < day:
            lo = mid + 1
        else:
            hi = mid
    if lo >= len(ds):
        return None
    i = lo + shift
    if i < 0 or i >= len(ds):
        return None
    return i


def window_of(s, d0, d1):
    """样本窗（下标）"""
    lo = to_trading(s, d0)
    hi = to_trading(s, d1)
    if lo is None:
        return None
    if hi is None:
        hi = s["n"] - 1
    valid = np.flatnonzero(~np.isnan(s["RV5"]) & ~np.isnan(s["sigma"]))
    if len(valid) == 0:
        return None
    lo = max(lo, int(valid[0])); hi = min(hi, int(valid[-1]))
    if hi - lo < 200:
        return None
    return lo, hi
