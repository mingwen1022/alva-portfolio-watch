"""DR 族重跑引擎（扩建加密样本池 25 只）。

判据：相对基准倍数的 95% 区间下界 > 1.0  ∧  独立块数 >= 5

口径（R28 定稿）
  V_t     = sqrt(mean(r^2))，**原始** 5 日已实现波动，不除以 sigma_rob
            对齐 A（PV 可比）: r_{t+1..t+5}
            对齐 B（告警到达时刻，00:00 UTC）: r_{t..t+4}
  基准    = sigma_rob 十分位分层；剔除任一触发日 ±5 天；基准纳入自助重抽
  倍数    = median( V_t / base_{decile(t)} )
  自助    = 触发侧整块自助（相邻触发间隔 < 5 日归一块）
            基准侧按十分位内的移动块自助（块长 5）
  种子固定 SEED

资金费率归一
  1) 单位：2025-12-04T18:00Z 之前为百分数、之后为小数（差 100 倍）。
     切换点逐标的用「幅度骤降 + 持续」检测，25 只全部落在同一时刻。
  2) 结算间隔：多数标的 8h（新口径 3 条/日），ENA/PENGU/TAO/TRUMP 为 4h（6 条/日），
     后者乘 2 归一到 %/8h（其中性值 0.005% 亦随之变 0.01%）。
"""
import os, csv, json, math, datetime
import numpy as np

U = "/Users/ming/project/alva/backtest/universe/data/crypto"
SEED = 20260819
B_DEFAULT = 2000
W_SIG, FWD, PURGE = 90, 5, 5
NDEC = 10
UNIT_CUTOVER = "2025-12-04T18:00"   # 由检测得到，见 detect_cutover()

CRYPTO = sorted(set(f.split("_")[0].split(".")[0] for f in os.listdir(U) if f.endswith(".csv")))


# ---------------- 数据 ----------------
def load_bars(sym, root=U):
    d, o, h, l, c, v = [], [], [], [], [], []
    with open(f"{root}/{sym}.csv") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            d.append(row[0]); o.append(float(row[1])); h.append(float(row[2]))
            l.append(float(row[3])); c.append(float(row[4])); v.append(float(row[5]))
    order = np.argsort(np.array(d))
    d = [d[i] for i in order]
    return dict(dates=d, open=np.array(o)[order], high=np.array(h)[order],
                low=np.array(l)[order], close=np.array(c)[order], vol=np.array(v)[order],
                idx={x: i for i, x in enumerate(d)})


def load_funding_raw(sym):
    """返回 [(iso_ts, raw_value)] 升序"""
    rows = []
    with open(f"{U}/{sym}_funding.csv") as fh:
        rd = csv.reader(fh); next(rd)
        for t, v in rd:
            if v == "": continue
            rows.append((t[:16], float(v)))
    rows.sort()
    return rows


def detect_cutover(rows, k=10, drop=10.0):
    """单位切换时刻。**用固定常量 UNIT_CUTOVER，不做逐标的幅度检测。**

    幅度检测（前后 40 条中位比）在 25 只上给出 2025-11-17 → 2025-12-09 的散布，
    因为窗口跨界时前后各含一半新旧数据。逐条核对原始行后确认真实边界唯一：
    每只标的最后一条旧单位观测 <= 2025-12-04T16:00，第一条新单位观测 >= 2025-12-04T20:00。
    ⚠️ 旧口径「首个 >=3 条/日」在 ENA/PENGU 上误判：它们 2025-12-04 有 3 条，
       其中 00:00 与 16:00 仍是旧单位，只有 20:00 是新单位。
    """
    return UNIT_CUTOVER


def funding_interval_hours(rows, cutover):
    """新口径时段每日结算条数 -> 间隔小时数。3 条/日 = 8h，6 条/日 = 4h。
    交叉验证：旧口径时段 |f| 的众数 8h 标的恒为 0.01、4h 标的恒为 0.005（逐年均成立）。"""
    from collections import Counter
    cnt = Counter(t[:10] for t, _ in rows if t >= cutover)
    if not cnt: return 8
    mode = Counter(cnt.values()).most_common(1)[0][0]
    return {1: 24, 2: 12, 3: 8, 4: 6, 6: 4, 8: 3}.get(mode, 8)


def funding_validate(rows, cutover, ih):
    """归一后众数应两侧都是 0.01 %/8h"""
    from collections import Counter
    k8 = 8.0 / ih
    pre = [round(abs(v) * k8, 6) for t, v in rows if t < cutover]
    post = [round(abs(v) * 100.0 * k8, 6) for t, v in rows if t >= cutover]
    f = lambda a: Counter(a).most_common(1)[0] if a else None
    return dict(mode_pre=f(pre), mode_post=f(post), n_pre=len(pre), n_post=len(post))


def load_funding(sym):
    """归一到 %/8h。返回 f00（date -> 00:00 值）· fmax（date -> 当日 |最大| 带符号）· meta"""
    rows = load_funding_raw(sym)
    cut = detect_cutover(rows) or UNIT_CUTOVER
    ih = funding_interval_hours(rows, cut)
    k8 = 8.0 / ih                      # 4h -> 2.0 ; 8h -> 1.0
    f00, fday = {}, {}
    for t, v in rows:
        scale = (100.0 if t >= cut else 1.0) * k8
        x = v * scale
        d = t[:10]
        fday.setdefault(d, []).append((t[11:16], x))
        if t[11:16] == "00:00":
            f00[d] = x
    fmax = {d: max(vs, key=lambda p: abs(p[1]))[1] for d, vs in fday.items()}
    nobs = {d: len(v) for d, v in fday.items()}
    return f00, fmax, dict(cutover=cut, interval_h=ih, k8=k8, nobs=nobs,
                           n_days=len(fday), start=rows[0][0], end=rows[-1][0])


def load_oi(sym):
    """OI 只有美元名义额（sum_open_interest 全空）。返回 date -> 名义美元额"""
    val = {}
    with open(f"{U}/{sym}_oi.csv") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            if row[2] not in ("", None):
                val[row[0][:10]] = float(row[2])
    return val


# ---------------- 波动量 ----------------
def build(sym, bars=None):
    b = bars or load_bars(sym)
    close = b["close"]; n = len(close)
    r = np.full(n, np.nan)
    r[1:] = np.log(close[1:] / close[:-1])
    sig = np.full(n, np.nan)
    for t in range(n):
        lo = max(1, t - W_SIG)
        w = r[lo:t]
        w = w[~np.isnan(w)]
        if len(w) < 60 or np.isnan(r[t]): continue
        m = np.median(w)
        s = 1.4826 * np.median(np.abs(w - m))
        if s > 0: sig[t] = s
    # 原始 5 日已实现波动，两种对齐
    def rv(shift):
        out = np.full(n, np.nan)
        for t in range(n):
            a, z = t + shift, t + shift + FWD
            if a < 0 or z > n: continue
            w = r[a:z]
            if np.isnan(w).any(): continue
            out[t] = math.sqrt(float(np.mean(w * w)))
        return out
    # z_rob 与 RVOL（PV1 自检用）
    z = np.full(n, np.nan); rvol = np.full(n, np.nan)
    vol = b["vol"]
    for t in range(n):
        lo = max(1, t - W_SIG); w = r[lo:t]; w = w[~np.isnan(w)]
        if len(w) >= 60 and not np.isnan(r[t]) and not np.isnan(sig[t]):
            z[t] = (r[t] - np.median(w)) / sig[t]
        vw = vol[max(0, t - W_SIG):t]; vw = vw[vw > 0]
        if len(vw) >= 60 and np.median(vw) > 0: rvol[t] = vol[t] / np.median(vw)
    return dict(sym=sym, dates=b["dates"], idx=b["idx"], close=close, open=b["open"],
                r=r, sigma=sig, V_fwd=rv(1), V_same=rv(0), z=z, rvol=rvol, n=n)


# ---------------- 自助 ----------------
def blocks_from_idx(idxs, gap=FWD):
    idxs = sorted(idxs); out, cur = [], []
    for i in idxs:
        if cur and i - cur[-1] >= gap:
            out.append(cur); cur = []
        cur.append(i)
    if cur: out.append(cur)
    return out


def _wmedian_rows(vals_sorted, w):
    """w: (B, n) 权重（计数）。vals_sorted: (n,) 升序。返回 (B,) 加权中位数（与 np.median 语义一致）"""
    cw = np.cumsum(w, axis=1)
    tot = cw[:, -1]
    half = tot / 2.0
    j = (cw >= half[:, None]).argmax(axis=1)
    lo = vals_sorted[j]
    prev = np.where(j > 0, cw[np.arange(len(j)), np.maximum(j - 1, 0)], 0.0)
    exact = np.isclose(prev, half) & (j > 0)
    # 精确落在分界：取相邻两个非零权重值的平均
    if exact.any():
        hi = lo.copy()
        for b in np.where(exact)[0]:
            k = j[b] - 1
            while k >= 0 and w[b, k] == 0: k -= 1
            if k >= 0: hi[b] = vals_sorted[k]
        lo = np.where(exact, (lo + hi) / 2.0, lo)
    return lo


def block_boot_medians(values, block_ids, nblk, B, rng):
    """整块自助：以块为单位有放回抽 nblk 次，返回 (B,) 中位数"""
    order = np.argsort(values, kind="stable")
    vs = values[order]; bs = block_ids[order]
    counts = rng.multinomial(nblk, np.full(nblk, 1.0 / nblk), size=B).astype(np.float64)
    w = counts[:, bs]
    return _wmedian_rows(vs, w)


def moving_block_ids(n, L=FWD):
    """把 0..n-1 切成长 L 的连续块，返回 (块数, 每个位置的块号)"""
    ids = np.arange(n) // L
    return int(ids.max()) + 1, ids


# ---------------- 主统计 ----------------
def ratio_ci(S, trig_idx, align="fwd", B=B_DEFAULT, seed=SEED,
             eval_idx=None, ndec=NDEC, min_base_per_dec=30,
             use_decile=True, use_purge=True, boot_base=True):
    """相对基准倍数 + 95% 自助区间。

    eval_idx : 该信号「可评估」的日下标（数据齐备的日子）。基准只从其中取。
    use_decile / use_purge / boot_base : 口径开关，用于分解各修正的贡献。
    """
    V = S["V_fwd"] if align == "fwd" else S["V_same"]
    sig = S["sigma"]; n = S["n"]
    ok = np.zeros(n, dtype=bool)
    if eval_idx is None: ok[:] = True
    else: ok[np.asarray(sorted(eval_idx), dtype=int)] = True
    ok &= ~np.isnan(V) & ~np.isnan(sig)

    T = np.array(sorted(i for i in trig_idx if ok[i]), dtype=int)
    if len(T) == 0: return None
    purge = np.zeros(n, dtype=bool)
    if use_purge:
        for i in trig_idx:
            purge[max(0, i - PURGE):min(n, i + PURGE + 1)] = True
    else:
        purge[np.asarray(sorted(set(trig_idx)), dtype=int)] = True
    Nmask = ok & ~purge
    if Nmask.sum() < 100: return None

    # σ 分层：起手十分位，基准日不足 min_base_per_dec 的层与相邻层合并，
    # **绝不因某层基准太薄而丢弃触发**（丢触发会按波动档选择性删样本）。
    if use_decile:
        qs = np.quantile(sig[ok], np.linspace(0, 1, ndec + 1)[1:-1])
        lab = np.digitize(sig, qs)
        groups = [[d] for d in range(ndec)]
        cnts = [int((Nmask & (lab == d)).sum()) for d in range(ndec)]
        while len(groups) > 1 and min(cnts) < min_base_per_dec:
            i = int(np.argmin(cnts))
            j = 1 if i == 0 else (i - 1 if i == len(groups) - 1 else
                                  (i - 1 if cnts[i - 1] <= cnts[i + 1] else i + 1))
            a, b = min(i, j), max(i, j)
            groups[a] = groups[a] + groups[b]; del groups[b]
            cnts[a] = cnts[a] + cnts[b]; del cnts[b]
        remap = np.zeros(ndec, dtype=int)
        for gi, g in enumerate(groups):
            for d in g: remap[d] = gi
        dec = remap[lab]; nd = len(groups)
    else:
        dec = np.zeros(n, dtype=int); nd = 1

    rng = np.random.default_rng(seed)
    base_pt = np.full(nd, np.nan)
    base_boot = np.full((B, nd), np.nan)
    nb = np.zeros(nd, dtype=int)
    for d in range(nd):
        idx = np.where(Nmask & (dec == d))[0]
        nb[d] = len(idx)
        if len(idx) < min_base_per_dec: continue
        v = V[idx]
        base_pt[d] = float(np.median(v))
        if boot_base:
            nblk_b, bids = moving_block_ids(len(idx), FWD)
            base_boot[:, d] = block_boot_medians(v, bids, nblk_b, B, rng)
        else:
            base_boot[:, d] = base_pt[d]

    dT = dec[T]
    good = ~np.isnan(base_pt[dT])
    T = T[good]; dT = dT[good]
    if len(T) == 0: return None
    Wt = V[T] / base_pt[dT]
    pt = float(np.median(Wt))

    blks = blocks_from_idx(T.tolist())
    nblk = len(blks)
    bid_of = {i: k for k, bl in enumerate(blks) for i in bl}
    bidsT = np.array([bid_of[i] for i in T])
    counts = rng.multinomial(nblk, np.full(nblk, 1.0 / nblk), size=B).astype(np.float64)
    wmat = counts[:, bidsT]
    VT = V[T]
    Wboot = VT[None, :] / base_boot[:, dT]
    reps = np.empty(B)
    for b in range(B):
        o = np.argsort(Wboot[b], kind="stable")
        reps[b] = _wmedian_scalar(Wboot[b][o], wmat[b][o])
    reps.sort()
    lo = float(reps[int(0.025 * B)]); hi = float(reps[int(0.975 * B) - 1])
    return dict(n=int(len(T)), n_raw=int(len(set(trig_idx))), blocks=nblk,
                mult=round(pt, 3), lo=round(lo, 3), hi=round(hi, 3),
                pass_=bool(lo > 1.0 and nblk >= 5), pass_ci=bool(lo > 1.0),
                n_base=int(Nmask.sum()), n_strata=int(nd), base_per_dec=nb.tolist(),
                n_dropped=int(len(set(i for i in trig_idx if ok[i])) - len(T)),
                base_med=round(float(np.nanmedian(base_pt)), 5))


def _wmedian_scalar(vs, w):
    cw = np.cumsum(w); tot = cw[-1]; half = tot / 2.0
    j = int(np.searchsorted(cw, half, side="left"))
    if j > 0 and abs(cw[j - 1] - half) < 1e-9:
        k = j - 1
        while k >= 0 and w[k] == 0: k -= 1
        return (vs[j] + vs[k]) / 2.0 if k >= 0 else vs[j]
    return float(vs[j])


def years_of(S, eval_idx, align="fwd"):
    V = S["V_fwd"] if align == "fwd" else S["V_same"]
    idx = np.asarray(sorted(eval_idx), dtype=int)
    return float(np.sum(~np.isnan(V[idx]) & ~np.isnan(S["sigma"][idx]))) / 365.0


# ---------------- 信号 ----------------
def dr1_days(f, days, th):
    return [d for d in days if d in f and abs(f[d]) >= th]


def dr2_days(f, days, th=0.0182, cool=30, debounce=True):
    have = [d for d in days if d in f]
    out, last = [], None
    for i in range(1, len(have)):
        d, p = have[i], have[i - 1]
        if f[d] == 0 or f[p] == 0: continue
        if (f[d] > 0) == (f[p] > 0): continue
        if abs(f[d]) < th: continue
        dd = datetime.date.fromisoformat(d)
        if debounce and last is not None and (dd - last).days < cool: continue
        out.append(d); last = dd
    return out


def dr3_days(oi, days, th=0.10, px=None):
    """px 非空 => 币本位（名义美元额 / 当日 00:00 价格；00:00 价 = 日线 open，无前视）"""
    have = [d for d in days if d in oi and (px is None or (d in px and px[d] > 0))]
    out = []
    for i in range(1, len(have)):
        d, p = have[i], have[i - 1]
        if (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(p)).days != 1:
            continue
        a = oi[p] / (px[p] if px else 1.0)
        b = oi[d] / (px[d] if px else 1.0)
        if a <= 0: continue
        if abs(b - a) / a >= th: out.append(d)
    return out


def to_idx(S, days):
    return [S["idx"][d] for d in days if d in S["idx"]]
