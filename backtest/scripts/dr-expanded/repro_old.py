"""自检：用旧口径 + 旧数据复现 results-phase5-dr.md 的数字。

旧口径 = V_t = RV5/sigma_rob（r_{t+1..t+5}） · 基准 = 全体非触发日中位（不分层不净化）
         · 整块自助只抽触发侧 · B=2000 · seed=20260819
旧数据 = backtest/data/derivatives/fr_*.csv, oi_*.csv + backtest/data/stocks-daily/*.csv
旧切换点判定 = 首个出现 >=3 条结算的日子（本脚本照抄，用于验证「能否复现」）
"""
import os, sys, csv, math, json, random, datetime, collections
import statistics as st

OLD_D = "/Users/ming/project/alva/backtest/data/derivatives"
OLD_B = "/Users/ming/project/alva/backtest/data/stocks-daily"
W, FWD, SEED, B = 90, 5, 20260819, 2000
SYMS = ["BTC", "ETH", "SOL", "DOGE"]
med = st.median


def load_bars(sym):
    rows = []
    for ln in open(f"{OLD_B}/{sym}.csv"):
        p = ln.strip().split(",")
        if len(p) < 3: continue
        rows.append((p[0], float(p[1]), float(p[2])))
    rows.sort(); return rows


def load_funding(sym):
    byday = collections.defaultdict(list)
    for ln in open(f"{OLD_D}/fr_{sym}.csv"):
        t, v = ln.strip().split(",")
        byday[t[:10]].append((t[11:16], float(v)))
    days = sorted(byday)
    brk = next((d for d in days if len(byday[d]) >= 3), "9999-99-99")
    f00, fmax = {}, {}
    for d, obs in byday.items():
        scale = 100.0 if d >= brk else 1.0
        vals = {tm: v * scale for tm, v in obs}
        if "00:00" in vals: f00[d] = vals["00:00"]
        fmax[d] = max(vals.values(), key=abs)
    return f00, fmax, brk


def load_oi(sym):
    oi = {}
    for ln in open(f"{OLD_D}/oi_{sym}.csv"):
        t, v = ln.strip().split(",")
        oi[t[:10]] = float(v)
    return oi


def build(sym, bars):
    dates = [r[0] for r in bars]; close = [r[1] for r in bars]; n = len(bars)
    r = [None] * n
    for i in range(1, n):
        if close[i-1] > 0 and close[i] > 0: r[i] = math.log(close[i]/close[i-1])
    sig = [None]*n
    for t in range(n):
        w = [r[i] for i in range(max(1, t-W), t) if r[i] is not None]
        if len(w) < 60 or r[t] is None: continue
        m = med(w); s = 1.4826*med([abs(x-m) for x in w])
        if s > 0: sig[t] = s
    V = [None]*n
    for t in range(n):
        if sig[t] is None or t+FWD >= n: continue
        rr = [r[t+k] for k in range(1, FWD+1)]
        if any(x is None for x in rr): continue
        V[t] = math.sqrt(sum(x*x for x in rr)/FWD)/sig[t]
    Vs = [None]*n
    for t in range(n):
        if sig[t] is None or t+FWD-1 >= n: continue
        rr = [r[t+k] for k in range(0, FWD)]
        if any(x is None for x in rr): continue
        Vs[t] = math.sqrt(sum(x*x for x in rr)/FWD)/sig[t]
    return dict(sym=sym, dates=dates, close=close, r=r, sig=sig, V=V, Vs=Vs, n=n,
                idx={d: i for i, d in enumerate(dates)})


def blocks_of(days):
    out, cur = [], []
    for d in days:
        if cur and (d-cur[-1]).days >= 5: out.append(cur); cur = []
        cur.append(d)
    if cur: out.append(cur)
    return out


def ratio_ci(trig_days, Vmap, base_vals, seed=SEED, B=B):
    tv = [Vmap[d] for d in trig_days if d in Vmap]
    if not tv or not base_vals: return None
    base = med(base_vals); pt = med(tv)/base
    dd = sorted(datetime.date.fromisoformat(d) for d in trig_days if d in Vmap)
    blks = blocks_of(dd)
    Vd = {datetime.date.fromisoformat(d): Vmap[d] for d in trig_days if d in Vmap}
    rng = random.Random(seed); boots = []
    for _ in range(B):
        samp = []
        for _ in range(len(blks)): samp.extend(blks[rng.randrange(len(blks))])
        boots.append(med([Vd[x] for x in samp])/base)
    boots.sort()
    return dict(n=len(tv), blocks=len(blks), ratio=round(pt, 3),
                lo=round(boots[int(0.025*B)], 3), hi=round(boots[int(0.975*B)-1], 3))


def sig_dr1(f, dates, th):  return set(d for d in dates if d in f and abs(f[d]) >= th)


def sig_dr2(f, dates, th=0.0182, cool=30, debounce=True):
    have = [d for d in dates if d in f]; out, last = set(), None
    for i in range(1, len(have)):
        d, p = have[i], have[i-1]
        if f[d] == 0 or f[p] == 0: continue
        if (f[d] > 0) == (f[p] > 0): continue
        if abs(f[d]) < th: continue
        dd = datetime.date.fromisoformat(d)
        if debounce and last is not None and (dd-last).days < cool: continue
        out.add(d); last = dd
    return out


def sig_dr3(oi, dates, th=0.10, px=None):
    have = [d for d in dates if d in oi and (px is None or (d in px and px[d] > 0))]
    out = set()
    for i in range(1, len(have)):
        d, p = have[i], have[i-1]
        if (datetime.date.fromisoformat(d)-datetime.date.fromisoformat(p)).days != 1: continue
        a = oi[p]/(px[p] if px else 1.0); b = oi[d]/(px[d] if px else 1.0)
        if a <= 0: continue
        if abs(b-a)/a >= th: out.add(d)
    return out


out = {}
for sym in SYMS:
    S = build(sym, load_bars(sym))
    f00, fmax, brk = load_funding(sym)
    oi = load_oi(sym)
    px = {S["dates"][i]: S["close"][i-1] for i in range(1, S["n"])}
    Vmap = {S["dates"][i]: S["V"][i] for i in range(S["n"]) if S["V"][i] is not None}
    Vsmap = {S["dates"][i]: S["Vs"][i] for i in range(S["n"]) if S["Vs"][i] is not None}
    dates = sorted(Vmap)
    lo = max(min(f00), min(oi), dates[0]); hi = min(max(f00), max(oi), dates[-1])
    dates = [d for d in dates if lo <= d <= hi]; ds = set(dates)
    rec = {"brk": brk, "window": [dates[0], dates[-1]], "ndays": len(dates)}
    # DR1 阈值网格
    rec["DR1"] = {}
    for th in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]:
        T = sorted(sig_dr1(f00, dates, th) & ds)
        base = [Vmap[d] for d in dates if d not in set(T)]
        rec["DR1"][str(th)] = ratio_ci(T, Vmap, base) if T else None
    # DR2
    T2 = sorted(sig_dr2(f00, dates) & ds)
    rec["DR2"] = ratio_ci(T2, Vmap, [Vmap[d] for d in dates if d not in set(T2)]) if T2 else None
    T2n = sorted(sig_dr2(f00, dates, debounce=False) & ds)
    rec["DR2_nodebounce"] = ratio_ci(T2n, Vmap, [Vmap[d] for d in dates if d not in set(T2n)]) if T2n else None
    # DR3 网格 + 同日口径 + 币本位
    rec["DR3"] = {}
    for th in [0.05, 0.10, 0.15, 0.20, 0.30]:
        T = sorted(sig_dr3(oi, dates, th) & ds)
        rec["DR3"][str(th)] = ratio_ci(T, Vmap, [Vmap[d] for d in dates if d not in set(T)]) if T else None
    T3 = sorted(sig_dr3(oi, dates, 0.10) & ds)
    rec["DR3_same"] = ratio_ci(T3, Vsmap, [Vsmap[d] for d in dates if d not in set(T3) and d in Vsmap])
    T3c = sorted(sig_dr3(oi, dates, 0.10, px=px) & ds)
    rec["DR3_coin"] = ratio_ci(T3c, Vmap, [Vmap[d] for d in dates if d not in set(T3c)])
    rec["DR3_coin_n"] = len(T3c)
    # 分位
    fa = sorted(abs(f00[d]) for d in dates if d in f00)
    q = lambda p: round(fa[int(p*(len(fa)-1))], 4)
    rec["f_quantiles"] = dict(p50=q(.5), p90=q(.9), p95=q(.95), p99=q(.99), p999=q(.999), max=round(fa[-1], 4))
    out[sym] = rec

print(json.dumps(out, ensure_ascii=False, indent=1))
