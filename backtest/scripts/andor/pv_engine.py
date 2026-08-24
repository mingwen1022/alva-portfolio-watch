"""PV 族回测引擎 · R28 定稿口径

V         = sqrt(mean(r_{t+1..t+5}^2))          原始 5 日已实现波动，不除 sigma_rob
基准      = 按 sigma_rob 十分位分层，层内取非触发日 V 的中位；剔除触发日 ±5 天
倍数      = median_t( V_t / base[decile(t)] )   逐触发比值的中位
区间      = 整块自助（块 = 相邻触发间隔 < 5 交易日）· 基准同步重抽 · 固定种子
判据      = 95% 区间下界 > 1.0  且  独立块数 >= 5

硬规则：逐标的算，禁止池化。
"""
import math, os, csv
import numpy as np

W, FWD = 90, 5          # 基线窗口 · 前瞻窗口
PURGE = 5               # 基准净化半径
SEED, NBOOT = 20260819, 4000
NDEC = 10               # sigma 分层层数

ROOT = "/Users/ming/project/alva/backtest"
D_UNIV_EQ = f"{ROOT}/universe/data/daily"
D_UNIV_CR = f"{ROOT}/universe/data/crypto"
D_LEGACY  = f"{ROOT}/data/stocks-daily"


# ---------- 数据 ----------
def load_legacy(sym):
    """旧篮子：无表头 date,close,volume"""
    ds, cs, vs = [], [], []
    for ln in open(f"{D_LEGACY}/{sym}.csv"):
        p = ln.strip().split(",")
        if len(p) < 3: continue
        ds.append(p[0]); cs.append(float(p[1])); vs.append(float(p[2]))
    o = np.argsort(ds)
    return [ds[i] for i in o], np.array(cs)[o], np.array(vs)[o]


def load_universe(sym, asset):
    """新样本池：有表头 date,open,high,low,close,volume"""
    d = D_UNIV_CR if asset == "crypto" else D_UNIV_EQ
    ds, cs, vs = [], [], []
    with open(f"{d}/{sym}.csv") as f:
        rd = csv.DictReader(f)
        for row in rd:
            try:
                c = float(row["close"]); v = float(row["volume"])
            except (TypeError, ValueError):
                continue
            ds.append(row["date"]); cs.append(c); vs.append(v)
    o = np.argsort(ds)
    return [ds[i] for i in o], np.array(cs)[o], np.array(vs)[o]


# ---------- 指标 ----------
def indicators(close, vol, ann):
    n = len(close)
    r = np.full(n, np.nan)
    ok = (close[:-1] > 0) & (close[1:] > 0)
    r[1:][ok] = np.log(close[1:][ok] / close[:-1][ok])

    sigma = np.full(n, np.nan); z = np.full(n, np.nan)
    rvol = np.full(n, np.nan)
    for t in range(n):
        lo = max(1, t - W)
        w = r[lo:t]; w = w[~np.isnan(w)]
        if len(w) >= 60 and not np.isnan(r[t]):
            m = np.median(w); mad = np.median(np.abs(w - m)); sr = 1.4826 * mad
            if sr > 0:
                sigma[t] = sr; z[t] = (r[t] - m) / sr
        lo2 = max(0, t - W)
        wv = vol[lo2:t]; wv = wv[wv > 0]
        if len(wv) >= 60:
            mv = np.median(wv)
            if mv > 0: rvol[t] = vol[t] / mv

    # V = 原始 5 日已实现波动
    V = np.full(n, np.nan)
    for t in range(n - FWD):
        fut = r[t + 1: t + 1 + FWD]
        if np.isnan(fut).any(): continue
        V[t] = math.sqrt(float(np.mean(fut ** 2)))
    V[np.isnan(sigma)] = np.nan          # 无基线的日子不参与
    avol = sigma * math.sqrt(ann)
    return dict(r=r, sigma=sigma, z=z, rvol=rvol, V=V, avol=avol, n=n)


def pv1_trigger(ind, thz, thv):
    z, rv = ind["z"], ind["rvol"]
    m = (~np.isnan(z)) & (~np.isnan(rv)) & (np.abs(z) >= thz) & (rv >= thv)
    return np.flatnonzero(m)


def blocks_of(idx, gap=FWD):
    """相邻触发间隔 < gap 个交易日 -> 同一块"""
    idx = np.sort(np.asarray(idx))
    if len(idx) == 0: return []
    out, cur = [], [idx[0]]
    for i in idx[1:]:
        if i - cur[-1] < gap: cur.append(i)
        else: out.append(np.array(cur)); cur = [i]
    out.append(np.array(cur))
    return out


# ---------- 相对基准倍数 + 整块自助 ----------
def ratio_ci(ind, trig, purge_from=None, nboot=NBOOT, seed=SEED, ndec=NDEC):
    """purge_from: 用于净化基准的触发日集合（默认与 trig 相同）。
    安慰剂平移时传入 实际触发日 ∪ 平移后触发日。"""
    V, sigma = ind["V"], ind["sigma"]
    n = ind["n"]
    valid = np.flatnonzero((~np.isnan(V)) & (~np.isnan(sigma)))
    if len(valid) < 200: return None

    # sigma 十分位（用全部有效日定切点）
    sv = sigma[valid]
    qs = np.quantile(sv, np.linspace(0, 1, ndec + 1)[1:-1])
    dec = np.full(n, -1)
    dec[valid] = np.searchsorted(qs, sv, side="right")

    pf = trig if purge_from is None else purge_from
    purge = np.zeros(n, bool)
    for t in np.asarray(pf, int):
        purge[max(0, t - PURGE): min(n, t + PURGE + 1)] = True

    T = np.array([t for t in trig if not np.isnan(V[t]) and not np.isnan(sigma[t])], int)
    if len(T) < 3: return None

    basepool = [valid[(dec[valid] == d) & (~purge[valid])] for d in range(ndec)]
    gpool = np.concatenate([p for p in basepool if len(p)]) if any(len(p) for p in basepool) else np.array([], int)
    if len(gpool) < 100: return None
    gmed = float(np.median(V[gpool]))
    base = np.array([float(np.median(V[p])) if len(p) >= 10 else gmed for p in basepool])
    if (base <= 0).any(): return None

    ratios = V[T] / base[dec[T]]
    point = float(np.median(ratios))

    bl = blocks_of(T)
    rng = np.random.default_rng(seed)
    nb = len(bl)
    # 基准同步重抽：层内有放回，一次性向量化
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
    lo = float(reps[int(0.025 * nboot)]); hi = float(reps[int(0.975 * nboot)])
    return dict(n=int(len(T)), blocks=int(nb), mult=point, lo=lo, hi=hi,
                base_med=float(np.median(base)), nbase=int(len(gpool)),
                boot_med=float(reps[nboot // 2]),
                pass_=bool(lo > 1.0 and nb >= 5))
