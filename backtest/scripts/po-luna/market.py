"""盘中市场确认 —— registry 附录 A.6（M6 AR_z）+ A.7（Move basis）。

复用 Phase 7 的 15 分钟 bar（scratchpad/intraday-run/raw，2024-08→2026-08，取数 0 credits）。

窗口约定（写死，先定后跑）
  美股  Δ = 30 分钟 = 2 根 RTH bar。设 k* = 第一根 start ≥ t0 的 bar，
        P(t0) = close[k*-1]（帖子发布前最后一个已成交价，杜绝把发帖前的走势算进窗口）
        P(t0+Δ) = close[k*+1]
        要求 1 ≤ k* ≤ 24（RTH 26 槽），否则该帖对美股无窗口
  加密  Δ = 15 分钟 = 1 根 bar，P(t0)=close[k*-1]，P(t0+Δ)=close[k*]，跨 session 连续
  ⚠️ 美股扩展时段不用（Phase 7 实测 50% 的格子算不出 σ_rob）

AR_z = (r_i − β r_m) / σ_AR
  β      同频（2 根 bar）窗口收益对 SPY 的 OLS，用触发前 90 个 session 的样本
  σ_AR   同一批样本 AR 的 1.4826·MAD
  加密    无市场基准（CLAUDE.md：BTC 占全加密市值一半以上，市场模型对它失效）→ β ≡ 0

RVOL(窗口) = 窗口内成交量 ÷ 前 90 个 session 同 slot 同长度窗口成交量的中位
确认 = |AR_z| ≥ 2.0  OR  RVOL ≥ 2.0        ← OR 不是 AND
"""
import os, sys, math
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INTRA = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, os.path.join(INTRA, "scripts"))
import load_intraday as L   # noqa: E402

ET = ZoneInfo("America/New_York")
W_BASE = 90          # 基线 session 数
MINOBS = 60
AR_THR, RVOL_THR = 2.0, 2.0

_grid = {}


def grid(sym):
    """返回 (D,K) 网格：close / vol / present，以及 session 键、slot 起始 epoch。"""
    if sym in _grid:
        return _grid[sym]
    kind, ts, c, v = L.raw_bars(sym)
    if kind == "crypto":
        loc = pd.to_datetime(ts, unit="s", utc=True)
        slot = ((ts % 86400) // 900).astype(int)
        nslots = 96
        daykey = (loc.year * 10000 + loc.month * 100 + loc.day).to_numpy()
        keep = np.ones(len(ts), bool)
    else:
        loc = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York")
        mins = (loc.hour * 60 + loc.minute).to_numpy()
        daykey = (loc.year * 10000 + loc.month * 100 + loc.day).to_numpy()
        start, nslots = 9 * 60 + 30, 26
        slot = (mins - start) // 15
        keep = (slot >= 0) & (slot < nslots) & (((mins - start) % 15) == 0)
        slot = slot.astype(int)
    ts, c, v, slot, daykey = ts[keep], c[keep], v[keep], slot[keep], daykey[keep]
    udays, sess = np.unique(daykey, return_inverse=True)
    D, K = len(udays), nslots
    C = np.full((D, K), np.nan); V = np.full((D, K), np.nan); TS = np.full((D, K), -1, np.int64)
    C[sess, slot] = c; V[sess, slot] = v; TS[sess, slot] = ts
    g = dict(sym=sym, kind=kind, C=C, V=V, TS=TS, days=udays, D=D, K=K)
    _grid[sym] = g
    return g


def _bar_start_epoch(g):
    """每个 (d,k) 的 bar 起始 epoch。缺 bar 的格子按同 session 已知 bar 的等距推。"""
    TS = g["TS"].astype(float).copy()
    TS[TS < 0] = np.nan
    D, K = TS.shape
    for d in range(D):
        row = TS[d]
        idx = np.flatnonzero(~np.isnan(row))
        if len(idx) == 0:
            continue
        anchor = row[idx[0]] - idx[0] * 900
        TS[d] = anchor + np.arange(K) * 900
    return TS


def locate(sym, t0_epoch):
    """把 t0 定位到 (d, k*)：第一根 start ≥ t0 的 bar。返回 None 表示落在网格外。"""
    g = grid(sym)
    if "BS" not in g:
        g["BS"] = _bar_start_epoch(g)
    BS = g["BS"]
    flat = BS.reshape(-1)
    ok = np.flatnonzero(~np.isnan(flat))
    if len(ok) == 0:
        return None
    pos = np.searchsorted(flat[ok], t0_epoch, side="left")
    if pos >= len(ok):
        return None
    j = ok[pos]
    d, k = divmod(int(j), g["K"])
    return d, k


def _win_returns(g, span, benchmark=None):
    """所有 (d,k*) 的窗口收益：r = ln(C[k*+span-1]/C[k*-1])，以及窗口成交量。
    美股 span=2，加密 span=1。返回 R (D,K)、VOL (D,K)，k* 越界为 nan。"""
    C, V, K = g["C"], g["V"], g["K"]
    D = g["D"]
    R = np.full((D, K), np.nan); VOL = np.full((D, K), np.nan)
    for k in range(1, K - span + 1):
        p0 = C[:, k - 1]; p1 = C[:, k + span - 1]
        m = (~np.isnan(p0)) & (~np.isnan(p1)) & (p0 > 0) & (p1 > 0)
        R[m, k] = np.log(p1[m] / p0[m])
        seg = V[:, k:k + span]
        VOL[:, k] = np.where(np.isnan(seg).any(axis=1), np.nan, seg.sum(axis=1))
    return R, VOL


def prep(sym, bench="SPY"):
    """预计算逐 (d,k*) 的 β / σ_AR / RVOL 基线。基线严格只用 d 之前的 session。"""
    g = grid(sym)
    if "prep" in g:
        return g["prep"]
    span = 1 if g["kind"] == "crypto" else 2
    R, VOL = _win_returns(g, span)
    if g["kind"] == "crypto":
        RM = None
    else:
        gb = grid(bench)
        RB, _ = _win_returns(gb, span)
        # 对齐 session 键
        idx = {d: i for i, d in enumerate(gb["days"])}
        RM = np.full_like(R, np.nan)
        for i, d in enumerate(g["days"]):
            j = idx.get(d)
            if j is not None:
                RM[i] = RB[j]
    D, K = R.shape
    beta = np.full((D, K), np.nan)
    sig = np.full((D, K), np.nan)
    volmed = np.full((D, K), np.nan)
    # 逐 session 用「前 W_BASE 个 session 的全部 k」估 β 与 σ_AR（池化 slot）
    for d in range(D):
        lo = max(0, d - W_BASE)
        if d - lo < 20:
            continue
        r = R[lo:d].reshape(-1)
        if RM is None:
            m = ~np.isnan(r)
            if m.sum() < MINOBS:
                continue
            b = 0.0
            ar = r[m]
        else:
            rm = RM[lo:d].reshape(-1)
            m = (~np.isnan(r)) & (~np.isnan(rm))
            if m.sum() < MINOBS:
                continue
            x, y = rm[m], r[m]
            vx = float(np.var(x))
            b = float(np.cov(x, y)[0, 1] / vx) if vx > 0 else 0.0
            ar = y - b * x
        med = float(np.median(ar))
        s = 1.4826 * float(np.median(np.abs(ar - med)))
        if s <= 0:
            continue
        beta[d, :] = b
        sig[d, :] = s
    # RVOL 基线逐 slot（成交量的日内 U 型很强，不能池化）
    for k in range(K):
        col = VOL[:, k]
        for d in range(D):
            lo = max(0, d - W_BASE)
            w = col[lo:d]; w = w[(~np.isnan(w)) & (w > 0)]
            if len(w) >= MINOBS:
                volmed[d, k] = np.median(w)
    out = dict(R=R, VOL=VOL, RM=RM, beta=beta, sig=sig, volmed=volmed, span=span)
    g["prep"] = out
    return out


def confirm(sym, t0_epoch):
    """返回 dict(ar_z, rvol, confirmed, ...) 或 None（无窗口）。"""
    g = grid(sym)
    p = prep(sym)
    loc = locate(sym, t0_epoch)
    if loc is None:
        return None
    d, k = loc
    K, span = g["K"], p["span"]
    if k < 1 or k + span - 1 >= K:
        return None
    r = p["R"][d, k]
    if np.isnan(r) or np.isnan(p["sig"][d, k]):
        return None
    rm = np.nan if p["RM"] is None else p["RM"][d, k]
    b = p["beta"][d, k]
    if p["RM"] is not None and np.isnan(rm):
        return None
    ar = r - (0.0 if p["RM"] is None else b * rm)
    arz = ar / p["sig"][d, k]
    vm = p["volmed"][d, k]; vv = p["VOL"][d, k]
    rv = float(vv / vm) if (vm and vm > 0 and not np.isnan(vv)) else np.nan
    conf = (abs(arz) >= AR_THR) or (not np.isnan(rv) and rv >= RVOL_THR)
    return dict(sym=sym, d=int(d), k=int(k), day=int(g["days"][d]), r=float(r),
                ar=float(ar), ar_z=float(arz), beta=float(b),
                rvol=(None if np.isnan(rv) else rv), confirmed=bool(conf),
                by_ar=bool(abs(arz) >= AR_THR),
                by_rvol=bool(not np.isnan(rv) and rv >= RVOL_THR))


def to_epoch(s):
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


# ---------------- 组合级（PO3 用） ----------------
def portfolio_prep(members, weights=None, bench="SPY"):
    """组合窗口收益 r_p = Σ w_i r_i；β_p = Σ w_i β_i；σ_AR,p 用同一构造在前 90 个 session 上的 MAD。
    RVOL_p = Σ w_i RVOL_i。成员必须同资产类别（网格槽数一致）。"""
    key = ("PORT",) + tuple(members)
    if key in _grid:
        return _grid[key]
    w = np.array(weights if weights else [1.0 / len(members)] * len(members))
    gs = [grid(m) for m in members]
    ps = [prep(m, bench) for m in members]
    kinds = {g["kind"] for g in gs}
    assert len(kinds) == 1, "组合成员必须同资产类别"
    kind = kinds.pop()
    K = gs[0]["K"]
    days = sorted(set(gs[0]["days"]).intersection(*[set(g["days"]) for g in gs[1:]]))
    days = np.array(days)
    D = len(days)
    R = np.zeros((D, K)); RV = np.zeros((D, K)); BE = np.zeros((D, K))
    ok = np.ones((D, K), bool)
    for g, p, wi in zip(gs, ps, w):
        idx = {d: i for i, d in enumerate(g["days"])}
        rows = np.array([idx[d] for d in days])
        r = p["R"][rows]; b = p["beta"][rows]
        vm = p["volmed"][rows]; vv = p["VOL"][rows]
        rv = np.where((vm > 0) & (~np.isnan(vv)), vv / np.where(vm > 0, vm, 1), np.nan)
        ok &= (~np.isnan(r)) & (~np.isnan(b)) & (~np.isnan(rv))
        R += wi * np.nan_to_num(r); BE += wi * np.nan_to_num(b); RV += wi * np.nan_to_num(rv)
    R[~ok] = np.nan; BE[~ok] = np.nan; RV[~ok] = np.nan
    if kind == "crypto":
        RM = None
        AR = R.copy()
    else:
        gb = grid(bench); pb = prep(bench)
        idx = {d: i for i, d in enumerate(gb["days"])}
        RM = np.full((D, K), np.nan)
        for i, d in enumerate(days):
            j = idx.get(int(d))
            if j is not None:
                RM[i] = pb["R"][j]
        AR = R - BE * RM
    SIG = np.full((D, K), np.nan)
    for d in range(D):
        lo = max(0, d - W_BASE)
        if d - lo < 20:
            continue
        a = AR[lo:d].reshape(-1); a = a[~np.isnan(a)]
        if len(a) < MINOBS:
            continue
        med = float(np.median(a)); s = 1.4826 * float(np.median(np.abs(a - med)))
        if s > 0:
            SIG[d, :] = s
    span = 1 if kind == "crypto" else 2
    BS = _bar_start_epoch(gs[0])
    idx0 = {d: i for i, d in enumerate(gs[0]["days"])}
    BSp = np.array([BS[idx0[d]] for d in days])
    out = dict(kind=kind, K=K, days=days, AR=AR, SIG=SIG, RV=RV, BS=BSp, span=span, D=D)
    _grid[key] = out
    return out


def confirm_portfolio(pp, t0_epoch):
    flat = pp["BS"].reshape(-1)
    okk = np.flatnonzero(~np.isnan(flat))
    pos = np.searchsorted(flat[okk], t0_epoch, side="left")
    if pos >= len(okk):
        return None
    j = int(okk[pos]); d, k = divmod(j, pp["K"])
    if k < 1 or k + pp["span"] - 1 >= pp["K"]:
        return None
    ar, s, rv = pp["AR"][d, k], pp["SIG"][d, k], pp["RV"][d, k]
    if np.isnan(ar) or np.isnan(s) or s <= 0:
        return None
    z = ar / s
    conf = (abs(z) >= AR_THR) or ((not np.isnan(rv)) and rv >= RVOL_THR)
    return dict(d=int(d), k=int(k), day=int(pp["days"][d]), ar_z=float(z),
                rvol=(None if np.isnan(rv) else float(rv)), confirmed=bool(conf),
                by_ar=bool(abs(z) >= AR_THR), by_rvol=bool((not np.isnan(rv)) and rv >= RVOL_THR))
