"""DR 族回测引擎 — 逐标的、整块自助、固定种子。

判据：相对基准倍数的 95% 区间下界 > 1.0
  V_t = sqrt(mean(r_{t+1..t+5}^2)) / sigma_rob,t
  sigma_rob,t = 1.4826 * median(|r_i - med|)，90 日窗，不含当日
  相对基准倍数 = median(V | 触发日) / median(V | 非触发日)

块：相邻触发间隔 < 5 日归一块。加密 365 天全年交易 ⇒ 日历日 == 交易日，
    直接用日历日差，与美股「5 个交易日」等价（都对应前瞻窗口重叠）。
"""
import math, os, json, random, statistics as st, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DR = os.path.join(HERE, "..", "data")
BARS = "/Users/ming/project/alva/backtest/data/stocks-daily"

W, FWD, SEED, B = 90, 5, 20260819, 2000
SYMS = ["BTC", "ETH", "SOL", "DOGE"]

TH_DR1 = 0.40      # %/8h
TH_DR2 = 0.0182    # %/8h
TH_DR3 = 0.10      # 24h |ΔOI|/OI


def med(xs):
    return st.median(xs)


# ---------- 数据加载 ----------
def load_bars(sym, path=None):
    rows = []
    for ln in open(path or f"{BARS}/{sym}.csv"):
        p = ln.strip().split(",")
        if len(p) < 3:
            continue
        rows.append((p[0], float(p[1]), float(p[2])))
    rows.sort()
    return rows


def load_funding(sym):
    """returns (f00 dict date->%/8h at 00:00, fmax dict date->max|f| that day, break_date)

    ⚠️ 2025-12-05 起供应商换了口径：采样从 1 次/日 (00:00) 变 3 次/日，
       数值单位从「百分数」变「小数」，相差 100 倍。用水平位移检测切换点，
       不能用「第一个多观测日」—— DOGE 2025-12-04 有 2 条但仍是旧单位。
    """
    byday = collections.defaultdict(list)
    for ln in open(f"{DR}/fr_{sym}.csv"):
        t, v = ln.strip().split(",")
        byday[t[:10]].append((t[11:16], float(v)))
    days = sorted(byday)
    # 切换点 = 第一个出现 3 次结算的日子。旧口径从无 3 次/日（DOGE 2025-12-04 有 2 次，
    # 但值仍是旧单位），所以「>=2 次」或「水平位移」两种检测都会误判，必须用 ==3。
    brk = next((d for d in days if len(byday[d]) >= 3), "9999-99-99")
    f00, fmax = {}, {}
    for d, obs in byday.items():
        scale = 100.0 if d >= brk else 1.0     # 归一到 %/8h
        vals = {tm: v * scale for tm, v in obs}
        if "00:00" in vals:
            f00[d] = vals["00:00"]
        fmax[d] = max(vals.values(), key=abs)
    return f00, fmax, brk


def load_oi(sym):
    oi = {}
    for ln in open(f"{DR}/oi_{sym}.csv"):
        t, v = ln.strip().split(",")
        oi[t[:10]] = float(v)
    return oi


# ---------- 波动量 ----------
def build(sym, bars):
    dates = [r[0] for r in bars]
    close = [r[1] for r in bars]
    n = len(bars)
    r = [None] * n
    for i in range(1, n):
        if close[i - 1] > 0 and close[i] > 0:
            r[i] = math.log(close[i] / close[i - 1])
    sig = [None] * n
    for t in range(n):
        w = [r[i] for i in range(max(1, t - W), t) if r[i] is not None]
        if len(w) < 60 or r[t] is None:
            continue
        m = med(w)
        s = 1.4826 * med([abs(x - m) for x in w])
        if s > 0:
            sig[t] = s
    V = [None] * n
    for t in range(n):
        if sig[t] is None or t + FWD >= n:
            continue
        rr = [r[t + k] for k in range(1, FWD + 1)]
        if any(x is None for x in rr):
            continue
        V[t] = math.sqrt(sum(x * x for x in rr) / FWD) / sig[t]
    return dict(sym=sym, dates=dates, close=close, r=r, sig=sig, V=V, n=n,
                idx={d: i for i, d in enumerate(dates)})


# ---------- 整块自助 ----------
def blocks_of(days):
    """days: sorted list of datetime.date. 相邻间隔 < 5 日 → 同一块"""
    out, cur = [], []
    for d in days:
        if cur and (d - cur[-1]).days >= 5:
            out.append(cur); cur = []
        cur.append(d)
    if cur:
        out.append(cur)
    return out


def ratio_ci(trig_days, Vmap, base_vals, seed=SEED, B=B):
    """trig_days: sorted list of date with a usable V. 返回点估计 + 95% 区间 + 块数"""
    tv = [Vmap[d] for d in trig_days]
    if not tv or not base_vals:
        return None
    base = med(base_vals)
    pt = med(tv) / base
    blks = blocks_of(trig_days)
    rng = random.Random(seed)
    boots = []
    for _ in range(B):
        samp = []
        for _ in range(len(blks)):
            samp.extend(blks[rng.randrange(len(blks))])
        boots.append(med([Vmap[d] for d in samp]) / base)
    boots.sort()
    lo = boots[int(0.025 * B)]
    hi = boots[int(0.975 * B) - 1]
    return dict(n=len(tv), blocks=len(blks), ratio=round(pt, 3),
                lo=round(lo, 3), hi=round(hi, 3), pass_=lo > 1.0,
                medV=round(med(tv), 3), baseV=round(base, 3))


# ---------- 信号 ----------
def sig_dr1(f, dates, th=TH_DR1):
    return set(d for d in dates if d in f and abs(f[d]) >= th)


def sig_dr2(f, dates, th=TH_DR2, cool=30, debounce=True):
    """跨 0（与上一个可用观测比）且 |f| >= th 且近 30 日首次"""
    have = [d for d in dates if d in f]
    out, last = set(), None
    for i in range(1, len(have)):
        d, p = have[i], have[i - 1]
        if f[d] == 0 or f[p] == 0:
            continue
        if (f[d] > 0) == (f[p] > 0):
            continue
        if abs(f[d]) < th:
            continue
        dd = datetime.date.fromisoformat(d)
        if debounce and last is not None and (dd - last).days < cool:
            continue
        out.add(d); last = dd
    return out


def sig_dr3(oi, dates, th=TH_DR3, px=None):
    """px 非空则先把 OI 名义美元额换算成币本位张数 (value / close)"""
    have = [d for d in dates if d in oi and (px is None or (d in px and px[d] > 0))]
    out = set()
    for i in range(1, len(have)):
        d, p = have[i], have[i - 1]
        if (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(p)).days != 1:
            continue
        # px[d] 必须是 d 当日 00:00 时刻的价格 = 前一日收盘。用当日收盘会前视。
        a = oi[p] / (px[p] if px else 1.0)
        b = oi[d] / (px[d] if px else 1.0)
        if a <= 0:
            continue
        if abs(b - a) / a >= th:
            out.add(d)
    return out


def jac(a, b):
    u = len(a | b)
    return round(len(a & b) / u, 3) if u else None
