"""三个前瞻窗的统一跑法 + 经验零 + 安慰剂 + 与日线的关系"""
import sys, os, csv, math, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from engine import (ratio_ci, sigma_decile, slot_sigma_cell, purge_fixed,
                    purge_session, indicators, build_grid, fwd_vol, chain_returns)
from prep import prep
from load_intraday import to_grid

DAILY = "/Users/ming/project/alva/backtest/universe/data/daily"
CRY = "/Users/ming/project/alva/backtest/universe/data/crypto"


# ---------- 触发 ----------
def trig_mask(P, thz, thv, rvol_key="rvol"):
    z = P["z"]; rv = P[rvol_key]
    return (~np.isnan(z)) & (~np.isnan(rv)) & (np.abs(z) >= thz) & (rv >= thv)


def valid_mask(P, window):
    V = P[{"A": "VA", "AX": "VAX", "B": "VB"}[window]]
    return (~np.isnan(V)) & (~np.isnan(P["sigma"]))


# ---------- 窗 A / B ----------
def run_window(P, thz, thv, window="A", cell_mode=None, nboot=2000, seed=20260819,
               rvol_key="rvol", shift=0, shift_unit="bar"):
    V = P[{"A":"VA","AX":"VAX","B":"VB"}[window]]
    vm = valid_mask(P, window)
    tm0 = trig_mask(P, thz, thv, rvol_key)
    D, K = V.shape
    if shift:
        if shift_unit == "bar":
            flat = tm0.reshape(-1)
            sh = np.zeros_like(flat)
            if shift < 0: sh[:shift] = flat[-shift:]
            else: sh[shift:] = flat[:-shift]
            tm = sh.reshape(D, K)
        else:  # session
            tm = np.zeros_like(tm0)
            if shift < 0: tm[:shift] = tm0[-shift:]
            else: tm[shift:] = tm0[:-shift]
    else:
        tm = tm0
    tm = tm & vm
    if cell_mode is None:
        cell_mode = "sigma" if window == "A" else "slot_sigma"
    if cell_mode == "sigma":
        cell = sigma_decile(P["sigma"], vm)
    else:
        cell = slot_sigma_cell(P["sigma"], vm, K, ndec=5)
    # 净化用 实际触发 ∪ 平移后触发
    pm_src = (tm0 & vm) | tm
    pm = purge_fixed(pm_src, 5) if window in ("A", "AX") else purge_session(pm_src)
    return ratio_ci(V, cell, tm, pm, nboot=nboot, seed=seed, block_gap=1)


# ---------- 窗 C：日线 ----------
def load_daily(sym, crypto=False):
    ds, cs, vs = [], [], []
    for row in csv.DictReader(open(f"{CRY if crypto else DAILY}/{sym}.csv")):
        try: c = float(row["close"]); v = float(row["volume"])
        except (TypeError, ValueError): continue
        ds.append(row["date"]); cs.append(c); vs.append(v)
    o = np.argsort(ds)
    return [ds[i] for i in o], np.array(cs)[o], np.array(vs)[o]


def daily_pack(sym, crypto=False):
    ds, c, v = load_daily(sym, crypto)
    D = len(c)
    ind = indicators(c.reshape(D, 1), v.reshape(D, 1), 1, cum_rvol=True)
    Vw, _ = fwd_vol(ind["r"], 5, session_bound=False, mode="fixed")
    Vw[np.isnan(ind["sigma"])] = np.nan
    vm = (~np.isnan(Vw)) & (~np.isnan(ind["sigma"]))
    return dict(dates=ds, ind=ind, V=Vw, vm=vm, D=D,
                dkey={int(d.replace("-", "")): i for i, d in enumerate(ds)})


def run_window_C(dp, trig_days, nboot=2000, seed=20260819, shift=0):
    D = dp["D"]
    tm = np.zeros((D, 1), bool)
    idx = [dp["dkey"][d] for d in trig_days if d in dp["dkey"]]
    idx = [i + shift for i in idx if 0 <= i + shift < D]
    tm[idx, 0] = True
    tm = tm & dp["vm"]
    tm0 = np.zeros((D, 1), bool)
    tm0[[dp["dkey"][d] for d in trig_days if d in dp["dkey"]], 0] = True
    cell = sigma_decile(dp["ind"]["sigma"], dp["vm"])
    pm = purge_fixed((tm0 & dp["vm"]) | tm, 5)
    return ratio_ci(dp["V"], cell, tm, pm, nboot=nboot, seed=seed, block_gap=5)


# ---------- 经验零：保持 slot 图案，随机换 session ----------
def null_run(P, thz, thv, window="A", reps=5, seed=7, nboot=800, rvol_key="rvol"):
    vm = valid_mask(P, window)
    tm = trig_mask(P, thz, thv, rvol_key) & vm
    D, K = tm.shape
    dayhas = np.flatnonzero(tm.any(axis=1))
    if len(dayhas) < 3: return []
    okday = np.flatnonzero(vm.any(axis=1))
    rng = np.random.default_rng(seed)
    out = []
    for rep in range(reps):
        fake = np.zeros_like(tm)
        picks = rng.choice(okday, size=len(dayhas), replace=False) if len(okday) >= len(dayhas) else rng.choice(okday, size=len(dayhas), replace=True)
        for src, dst in zip(dayhas, picks):
            fake[dst] |= tm[src]
        fake = fake & vm
        if fake.sum() < 3: continue
        cell = sigma_decile(P["sigma"], vm) if window in ("A", "AX") else slot_sigma_cell(P["sigma"], vm, K, ndec=5)
        pm = purge_fixed(fake, 5) if window in ("A", "AX") else purge_session(fake)
        V = P[{"A": "VA", "AX": "VAX", "B": "VB"}[window]]
        r = ratio_ci(V, cell, fake, pm, nboot=nboot, seed=20260819 + rep, block_gap=1)
        if r: out.append(r)
    return out


# ---------- 经验零 · 变体 S：保持 session，随机换 slot（保持间距） ----------
def null_run_slot(P, thz, thv, window="A", reps=5, seed=11, nboot=800, rvol_key="rvol"):
    vm = valid_mask(P, window)
    tm = trig_mask(P, thz, thv, rvol_key) & vm
    D, K = tm.shape
    dayhas = np.flatnonzero(tm.any(axis=1))
    if len(dayhas) < 3: return []
    rng = np.random.default_rng(seed)
    cellA = sigma_decile(P["sigma"], vm)
    cellB = slot_sigma_cell(P["sigma"], vm, K, ndec=5)
    V = P[{"A": "VA", "AX": "VAX", "B": "VB"}[window]]
    out = []
    for rep in range(reps):
        fake = np.zeros_like(tm)
        for d in dayhas:
            S = np.flatnonzero(tm[d])
            span = S.max() - S.min()
            room = K - 1 - span
            if room < 0: continue
            o = int(rng.integers(0, room + 1))
            fake[d, S - S.min() + o] = True
        fake = fake & vm
        if fake.sum() < 3: continue
        cell = cellA if window in ("A", "AX") else cellB
        pm = purge_fixed(fake, 5) if window in ("A", "AX") else purge_session(fake)
        r = ratio_ci(V, cell, fake, pm, nboot=nboot, seed=20260819 + rep, block_gap=1)
        if r: out.append(r)
    return out
