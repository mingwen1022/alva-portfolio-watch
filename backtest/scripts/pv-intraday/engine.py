"""盘中 PV1 回测引擎 · 与日线 pv_engine.py 同口径，slot 维度泛化

数据被组织成 (session, slot) 网格。日线是 slot=1 的特例 —— 该退化情形必须
复现已审核的日线数字（selfcheck.py）。

M2' z_rob   同一 slot 前 90 个 session 的收益 med / MAD，严格不含当日
M3' RVOL    今日 session 内截至 slot k 的累计量 ÷ 前 90 个 session 同位置累计量中位
V           前瞻窗已实现波动，原始量，不除 sigma_rob
基准        按 (cell) 分层取非触发 bar 的 V 中位；净化剔除触发点邻域
倍数        median_t( V_t / base[cell(t)] )
区间        整块自助，基准同步重抽，固定种子
判据        95% 下界 > 1.0  且  独立块数 >= 5
"""
import math, csv, os
import numpy as np

W_BASE = 90          # 基线：前 90 个 session（同 slot）
MINOBS = 60          # 基线最少有效样本
SEED, NBOOT = 20260819, 2000
NDEC = 10


# ---------------- 网格构造 ----------------
def build_grid(sess_idx, slot_idx, close, vol, nslots, ffill=True):
    """把散列 bar 铺到 (D, K) 网格；缺口在该 session 已观测跨度内前向填充（量记 0）。
    返回 C, V(量), present(bool), filled(bool)"""
    D = int(sess_idx.max()) + 1
    C = np.full((D, nslots), np.nan)
    Vv = np.full((D, nslots), np.nan)
    C[sess_idx, slot_idx] = close
    Vv[sess_idx, slot_idx] = vol
    present = ~np.isnan(C)
    filled = np.zeros_like(present)
    if ffill:
        for d in range(D):
            row = C[d]
            idx = np.flatnonzero(present[d])
            if len(idx) == 0:
                continue
            lo, hi = idx[0], idx[-1]
            last = row[lo]
            for k in range(lo, hi + 1):
                if np.isnan(row[k]):
                    row[k] = last
                    Vv[d, k] = 0.0
                    filled[d, k] = True
                else:
                    last = row[k]
    return C, Vv, present, filled


def chain_returns(C):
    """按时间顺序把网格展平成链，r = ln(C_t / C_prev)。跨 session 的第一根
    bar 携带隔夜跳空（附录 A.7：盘前/盘中对比前一交易日收盘）。"""
    D, K = C.shape
    flat = C.reshape(-1)
    r = np.full(D * K, np.nan)
    ok = np.flatnonzero(~np.isnan(flat))
    for j in range(1, len(ok)):
        a, b = ok[j - 1], ok[j]
        if flat[a] > 0 and flat[b] > 0:
            r[b] = math.log(flat[b] / flat[a])
    return r.reshape(D, K)


# ---------------- M 层 ----------------
def indicators(C, Vv, nslots, cum_rvol=True):
    """同 slot 滚动基线。返回 r/sigma/z/rvol 网格 (D,K)。"""
    D, K = C.shape
    r = chain_returns(C)
    sigma = np.full((D, K), np.nan)
    z = np.full((D, K), np.nan)
    rvol = np.full((D, K), np.nan)

    cum = np.nancumsum(np.where(np.isnan(Vv), 0.0, Vv), axis=1) if cum_rvol else Vv

    for k in range(K):
        col = r[:, k]
        colv = cum[:, k]
        for d in range(D):
            lo = max(0, d - W_BASE)
            w = col[lo:d]; w = w[~np.isnan(w)]
            if len(w) >= MINOBS and not np.isnan(col[d]):
                m = np.median(w); mad = np.median(np.abs(w - m)); sr = 1.4826 * mad
                if sr > 0:
                    sigma[d, k] = sr; z[d, k] = (col[d] - m) / sr
            wv = colv[lo:d]; wv = wv[wv > 0]
            if len(wv) >= MINOBS:
                mv = np.median(wv)
                if mv > 0 and colv[d] > 0:
                    rvol[d, k] = colv[d] / mv
    return dict(r=r, sigma=sigma, z=z, rvol=rvol, D=D, K=K)


# ---------------- 前瞻窗 ----------------
def fwd_vol(r, fwd, session_bound=True, mode="fixed"):
    """mode='fixed' : 触发后 fwd 根 bar
       mode='toclose': 触发后到 session 收盘（长度可变）
    session_bound=True 时窗口不跨 session。返回 V(D,K) 与 窗口长度 L(D,K)。"""
    D, K = r.shape
    V = np.full((D, K), np.nan)
    L = np.zeros((D, K), int)
    flat = r.reshape(-1)
    for d in range(D):
        for k in range(K):
            if mode == "fixed":
                if session_bound:
                    if k + fwd >= K: continue
                    seg = r[d, k + 1: k + 1 + fwd]
                else:
                    s = d * K + k
                    if s + fwd >= D * K: continue
                    seg = flat[s + 1: s + 1 + fwd]
            else:
                if k + 1 >= K: continue
                seg = r[d, k + 1:]
            if len(seg) == 0 or np.isnan(seg).any(): continue
            V[d, k] = math.sqrt(float(np.mean(seg ** 2)))
            L[d, k] = len(seg)
    return V, L


# ---------------- 触发 / 块 ----------------
def trigger(ind, thz, thv):
    z, rv = ind["z"], ind["rvol"]
    m = (~np.isnan(z)) & (~np.isnan(rv)) & (np.abs(z) >= thz) & (rv >= thv)
    return m


def blocks_by_session(sess, gap=1):
    """块 = session。gap>1 时相邻 session 间隔 < gap 也并入同块（日线口径 gap=5）。"""
    us = np.unique(sess)
    out, cur = [], [us[0]]
    for s in us[1:]:
        if s - cur[-1] < gap: cur.append(s)
        else: out.append(cur); cur = [s]
    out.append(cur)
    return out


# ---------------- 相对基准倍数 ----------------
def ratio_ci(V, cell, trig_mask, purge_mask, nboot=NBOOT, seed=SEED, min_cell=10, block_gap=1):
    """V/cell/trig_mask/purge_mask: (D,K) 展平后使用。cell 为整型分层标签，-1 表示无效。
    返回 dict 或 None。块 = session（已在外部按需合并）。"""
    Vf = V.reshape(-1); cf = cell.reshape(-1)
    tf = trig_mask.reshape(-1); pf = purge_mask.reshape(-1)
    D, K = V.shape
    sessf = np.repeat(np.arange(D), K)

    valid = (~np.isnan(Vf)) & (cf >= 0)
    if valid.sum() < 200: return None

    T = np.flatnonzero(valid & tf)
    if len(T) < 3: return None

    ncell = int(cf.max()) + 1
    basepool = []
    for c in range(ncell):
        p = np.flatnonzero(valid & (cf == c) & (~pf) & (~tf))
        basepool.append(p)
    gpool = np.concatenate([p for p in basepool if len(p)]) if any(len(p) for p in basepool) else np.array([], int)
    if len(gpool) < 100: return None
    gmed = float(np.median(Vf[gpool]))
    base = np.array([float(np.median(Vf[p])) if len(p) >= min_cell else gmed for p in basepool])
    if (base <= 0).any() or gmed <= 0: return None

    ratios = Vf[T] / base[cf[T]]
    point = float(np.median(ratios))

    # 块 = session
    ts = sessf[T]
    us = np.unique(ts)
    groups, cur = [], [us[0]]
    for s_ in us[1:]:
        if s_ - cur[-1] < block_gap: cur.append(s_)
        else: groups.append(cur); cur = [s_]
    groups.append(cur)
    bl = [T[np.isin(ts, g)] for g in groups]
    nb = len(bl)

    rng = np.random.default_rng(seed)
    bb = np.empty((nboot, ncell))
    for c in range(ncell):
        pv = Vf[basepool[c]]
        if len(pv) >= min_cell:
            ii = rng.integers(0, len(pv), size=(nboot, len(pv)))
            bb[:, c] = np.median(pv[ii], axis=1)
        else:
            bb[:, c] = gmed
    # 把块按顺序摊平，用 (starts, lens) 做向量化 gather，避免逐块 concat
    flatidx = np.concatenate(bl)
    lens = np.array([len(b) for b in bl])
    starts = np.concatenate(([0], np.cumsum(lens)[:-1]))
    fV = Vf[flatidx]; fC = cf[flatidx]
    reps = np.empty(nboot)
    for b in range(nboot):
        pick = rng.integers(0, nb, nb)
        sl = lens[pick]
        tot = int(sl.sum())
        off = np.concatenate(([0], np.cumsum(sl)[:-1]))
        gidx = np.repeat(starts[pick] - off, sl) + np.arange(tot)
        reps[b] = np.median(fV[gidx] / bb[b][fC[gidx]])
    reps.sort()
    lo = float(reps[int(0.025 * nboot)]); hi = float(reps[int(0.975 * nboot)])
    return dict(n=int(len(T)), blocks=int(nb), mult=point, lo=lo, hi=hi,
                nbase=int(len(gpool)), base_med=float(np.median(base)),
                pass_=bool(lo > 1.0 and nb >= 5))


def sigma_decile(sigma, valid, ndec=NDEC):
    """按 sigma_rob 十分位给出 cell 标签，无效为 -1"""
    f = sigma.reshape(-1); vv = valid.reshape(-1)
    idx = np.flatnonzero(vv & ~np.isnan(f))
    out = np.full(f.shape, -1)
    if len(idx) < 50: return out.reshape(sigma.shape)
    qs = np.quantile(f[idx], np.linspace(0, 1, ndec + 1)[1:-1])
    out[idx] = np.searchsorted(qs, f[idx], side="right")
    return out.reshape(sigma.shape)


def slot_sigma_cell(sigma, valid, nslots, ndec=5):
    """cell = slot × sigma 分位（层内定切点）"""
    D, K = sigma.shape
    out = np.full((D, K), -1)
    c = 0
    for k in range(K):
        col = sigma[:, k]; v = valid[:, k]
        idx = np.flatnonzero(v & ~np.isnan(col))
        if len(idx) < 20:
            if len(idx): out[idx, k] = c
            c += 1
            continue
        qs = np.quantile(col[idx], np.linspace(0, 1, ndec + 1)[1:-1])
        out[idx, k] = c + np.searchsorted(qs, col[idx], side="right")
        c += ndec
    return out


def purge_fixed(trig_mask, radius):
    """展平索引上 ±radius 净化"""
    D, K = trig_mask.shape
    tf = trig_mask.reshape(-1).copy()
    n = len(tf)
    p = np.zeros(n, bool)
    for t in np.flatnonzero(tf):
        p[max(0, t - radius): min(n, t + radius + 1)] = True
    return p.reshape(D, K)


def purge_session(trig_mask):
    """整个 session 被剔除（窗口到收盘时用）"""
    has = trig_mask.any(axis=1)
    return np.repeat(has[:, None], trig_mask.shape[1], axis=1)
