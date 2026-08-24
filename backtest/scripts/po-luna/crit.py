"""PO 触发的判据：相对基准倍数 95% 下界 > 1.0 ∧ 独立块数 ≥ 5，逐标的算。

复用 Phase 7 的盘中引擎与缓存（同口径：窗 A = 触发后 5 根 bar 的已实现波动，
cell = σ_rob 十分位，净化 ±5 根，块 = session，整块自助）。

与 Phase 7 唯一的差别是**触发从哪来**：那边是 z/RVOL 阈值，这里是帖子时刻。
触发格设在 k*−1（k* = 第一根 start ≥ t0 的 bar），于是前瞻窗恰好是 k*..k*+4 ——
全部在帖子之后，无前视。
"""
import os, sys, json
import numpy as np
import pandas as pd
from datetime import datetime, timezone

INTRA = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, os.path.join(INTRA, "scripts"))
from prep import prep as _prep                     # noqa: E402
from engine import ratio_ci, sigma_decile, purge_fixed   # noqa: E402
import load_intraday as L                          # noqa: E402

D0, D1 = 20260101, 20260820


def kinds():
    idx = L._index()
    return {s: v[0] for s, v in idx.items()}


def load(sym, crypto):
    return _prep(sym, "UTC" if crypto else "RTH")


def post_slots(epochs, crypto):
    """帖子 epoch → (daykey, k*)。美股用美东 RTH 26 槽；加密用 UTC 96 槽。"""
    ts = pd.to_datetime(np.asarray(epochs, dtype=np.int64), unit="s", utc=True)
    if crypto:
        loc = ts
        start, K = 0, 96
    else:
        loc = ts.tz_convert("America/New_York")
        start, K = 9 * 60 + 30, 26
    mins = (loc.hour * 60 + loc.minute + loc.second / 60.0).to_numpy()
    day = (loc.year * 10000 + loc.month * 100 + loc.day).to_numpy()
    kstar = np.ceil((mins - start) / 15.0).astype(int)
    return day, kstar, K


def trig_mask_from_posts(P, epochs, crypto, offset=0):
    """offset=0  触发格 = k*−1，前瞻窗 = k*..k*+4     ← 帖子后立刻起算
    offset=2  触发格 = k*+1，前瞻窗 = k*+2..k*+6   ← 跳过 30 分钟确认窗，
              给「已确认」子集用，否则条件化的窗口与被测的窗口重叠，构造上必然放大"""
    days = P["days"]
    K = int(P["nslots"])
    d_of = {int(d): i for i, d in enumerate(days)}
    day, kstar, _ = post_slots(epochs, crypto)
    tm = np.zeros((len(days), K), bool)
    hit = 0
    for dd, kk in zip(day, kstar):
        i = d_of.get(int(dd))
        if i is None:
            continue
        j = kk - 1 + offset
        if kk < 1 or kk > K - 1 or j < 0 or j > K - 1:
            continue
        tm[i, j] = True
        hit += 1
    return tm, hit


def valid_A(P):
    return (~np.isnan(P["VA"])) & (~np.isnan(P["sigma"]))


def run_sym(P, tm, nboot=2000, seed=20260819):
    vm = valid_A(P)
    t = tm & vm
    if t.sum() < 3:
        return None
    cell = sigma_decile(P["sigma"], vm)
    pm = purge_fixed(t, 5)
    return ratio_ci(P["VA"], cell, t, pm, nboot=nboot, seed=seed, block_gap=1)


def window_mask(P):
    """只保留回测窗口 2026-01→08 的 session（基线仍可用更早的数据）。"""
    days = P["days"]
    K = int(P["nslots"])
    sel = (days >= D0) & (days < D1)
    return np.repeat(sel[:, None], K, axis=1)


def shared_null_calendars(P_ref, tm_ref, reps, seed, mode="day"):
    """构造共用伪日历：保持每天的 slot 图样，把「哪一天」随机换到窗口内另一天。
    返回 reps 个 (day, kslots) 列表 —— 用 daykey 表达，好在各标的间共用。"""
    days = P_ref["days"]
    sel = np.flatnonzero((days >= D0) & (days < D1))
    dayhas = np.flatnonzero(tm_ref.any(axis=1))
    dayhas = np.array([d for d in dayhas if D0 <= days[d] < D1])
    rng = np.random.default_rng(seed)
    out = []
    for rep in range(reps):
        cal = {}
        if mode == "day":
            picks = rng.choice(sel, size=len(dayhas), replace=len(sel) < len(dayhas))
            for src, dst in zip(dayhas, picks):
                cal.setdefault(int(days[dst]), set()).update(np.flatnonzero(tm_ref[src]).tolist())
        else:  # slot：保留哪一天，随机平移当天的 slot 图样
            K = tm_ref.shape[1]
            for d in dayhas:
                S = np.flatnonzero(tm_ref[d])
                span = S.max() - S.min()
                room = K - 1 - span
                if room < 0:
                    continue
                o = int(rng.integers(0, room + 1))
                cal[int(days[d])] = set((S - S.min() + o).tolist())
        out.append(cal)
    return out


def mask_from_calendar(P, cal):
    days = P["days"]; K = int(P["nslots"])
    d_of = {int(d): i for i, d in enumerate(days)}
    tm = np.zeros((len(days), K), bool)
    for dd, ks in cal.items():
        i = d_of.get(int(dd))
        if i is None:
            continue
        for k in ks:
            if 0 <= k < K:
                tm[i, k] = True
    return tm


def calendar_from_mask(P, tm):
    days = P["days"]
    cal = {}
    for i in np.flatnonzero(tm.any(axis=1)):
        if D0 <= days[i] < D1:
            cal[int(days[i])] = set(np.flatnonzero(tm[i]).tolist())
    return cal


def _daykey_meta(daykeys):
    """(月内三分位, 周几) —— 位置匹配安慰剂的分层键。"""
    import datetime as _dt
    out = []
    for d in daykeys:
        y, m, dd = int(d) // 10000, (int(d) // 100) % 100, int(d) % 100
        pos = 0 if dd <= 10 else (1 if dd <= 20 else 2)
        wd = _dt.date(y, m, dd).weekday()
        out.append((pos, wd))
    return out


def position_matched_calendars(P_ref, tm_ref, reps, seed):
    """位置匹配安慰剂：替换日必须与原触发日**同月内三分位 + 同周几**。
    针对 MA 族踩过的坑 —— 「月末最后一个交易日」这条零信息量规则拿到 26/90 通过，
    说明日历位置本身能造出通过。"""
    days = P_ref["days"]
    sel = np.flatnonzero((days >= D0) & (days < D1))
    meta_all = _daykey_meta(days[sel])
    pool = {}
    for i, m in zip(sel, meta_all):
        pool.setdefault(m, []).append(i)
    dayhas = [d for d in np.flatnonzero(tm_ref.any(axis=1)) if D0 <= days[d] < D1]
    meta_hit = _daykey_meta([days[d] for d in dayhas])
    rng = np.random.default_rng(seed)
    out = []
    for rep in range(reps):
        cal = {}
        for src, m in zip(dayhas, meta_hit):
            cands = pool.get(m)
            if not cands:
                continue
            dst = int(rng.choice(cands))
            cal.setdefault(int(days[dst]), set()).update(np.flatnonzero(tm_ref[src]).tolist())
        out.append(cal)
    return out
