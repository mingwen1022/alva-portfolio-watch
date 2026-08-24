"""EV 族回测引擎 · 扩建样本池（92 美股）重跑

判据（现行）：相对基准倍数 95% 区间下界 > 1.0  ∧  独立块数 ≥ 5

口径（R28 定稿）
  V_t      = sqrt(mean(r_{t+1..t+5}^2))            ← 原始 5 日已实现波动，不除以 σ_rob
  σ_rob,t  = 1.4826 × MAD(r 的 90 日窗，不含当日)   ← 只用来分层，不进 V
  基准     = σ_rob 十分位分层；层内基准池 = 非触发日 且 距任一触发日 > 5 个交易日
  每次触发 = V_t / median(层内基准池 V)
  点估计   = median(逐触发倍数)
  自助     = 整块自助（触发）+ 层内重抽（基准），2000 次，固定种子
  块       = 相邻触发间隔 < 5 个交易日归一块
  冷却     = 45 日历日
  触发日   = filing_date / publish 可知日，一律不用 transaction_date
"""
import csv, json, math, os, random, statistics as st, sys
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta

UNI = "/Users/ming/project/alva/backtest/universe"
OLD = "/Users/ming/project/alva/backtest/data"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONG_NEW = f"{ROOT}/data/congress"

FWD, WROB, MINROB = 5, 90, 60
COOL, WIN = 45, 30
B, SEED = 2000, 20260819
NDEC = 10
PURGE = 5          # 触发日 ±5 个交易日不进基准池
GAPMAX = 10        # 相邻两根日线跨度 > 10 天视为数据空洞，该根收益作废

med = st.median


# ───────────────────────── 价格与波动序列 ─────────────────────────
def load_daily(sym, src="new"):
    """→ (dates:list[date], close:list[float])，时间正序"""
    if src == "new":
        p, rows = f"{UNI}/data/daily/{sym}.csv", []
        with open(p) as f:
            rd = csv.reader(f)
            head = next(rd)
            for x in rd:
                if len(x) >= 5:
                    rows.append((date.fromisoformat(x[0]), float(x[4])))
    else:  # 旧 11 只：date,close,volume 无表头
        p, rows = f"{OLD}/stocks-daily/{sym}.csv", []
        for ln in open(p):
            q = ln.strip().split(",")
            if len(q) >= 2:
                rows.append((date.fromisoformat(q[0]), float(q[1])))
    rows.sort()
    return [r[0] for r in rows], [r[1] for r in rows]


def build(sym, src="new", raw_v=True):
    """raw_v=True → V 是原始 RV5（R28 口径）；False → RV5/σ_rob（旧口径，自检用）"""
    ds, cl = load_daily(sym, src)
    n = len(ds)
    r = [None] * n
    for i in range(1, n):
        if (ds[i] - ds[i - 1]).days > GAPMAX:
            continue                      # 数据空洞，收益作废
        if cl[i - 1] > 0 and cl[i] > 0:
            r[i] = math.log(cl[i] / cl[i - 1])
    sig = [None] * n
    for t in range(n):
        w = [r[i] for i in range(max(1, t - WROB), t) if r[i] is not None]
        if len(w) < MINROB:
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
        v = math.sqrt(sum(x * x for x in rr) / FWD)
        V[t] = v if raw_v else v / sig[t]
    z = [None] * n
    for t in range(n):
        if sig[t] and r[t] is not None:
            z[t] = r[t] / sig[t]
    return dict(sym=sym, ds=ds, V=V, sig=sig, r=r, z=z, n=n,
                idx={d: i for i, d in enumerate(ds)})


def align(days, ds):
    """日历日 → 该日或其后 8 天内的第一个交易日索引"""
    idx = {d: i for i, d in enumerate(ds)}
    out = []
    for d in days:
        for k in range(9):
            if d + timedelta(days=k) in idx:
                out.append(idx[d + timedelta(days=k)])
                break
    return sorted(set(out))


# ───────────────────────── 判据计算 ─────────────────────────
def blocks_of(ii):
    out, cur = [], []
    for i in sorted(ii):
        if cur and i - cur[-1] >= FWD:
            out.append(cur); cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def evaluate(trig_idx, S, strat=True, seed=SEED, B=B, purge=PURGE):
    """trig_idx: 交易日索引。返回点估计 / 95% 区间 / 块数"""
    V, sig, n = S["V"], S["sig"], S["n"]
    usable = [i for i in range(n) if V[i] is not None and sig[i] is not None]
    tset = set(i for i in trig_idx if V[i] is not None and sig[i] is not None)
    if len(tset) < 3:
        return dict(n=len(tset), nb=0, err="触发不足 3")
    near = set()
    for i in tset:
        near.update(range(i - purge, i + purge + 1))
    pool = [i for i in usable if i not in near]
    if len(pool) < 50:
        return dict(n=len(tset), nb=0, err="基准池不足")
    T = sorted(tset)
    blks = blocks_of(T)
    rng = random.Random(seed)

    if not strat:                                    # 旧口径：全体非触发日中位，基准固定
        base = med([V[i] for i in pool])
        pt = med([V[i] for i in T]) / base
        boots = []
        for _ in range(B):
            samp = []
            for _ in range(len(blks)):
                samp.extend(blks[rng.randrange(len(blks))])
            boots.append(med([V[i] for i in samp]) / base)
        boots.sort()
        return dict(n=len(T), nb=len(blks), r=pt, lo=boots[int(.025 * B)],
                    hi=boots[int(.975 * B) - 1], base=base)

    # σ_rob 十分位分层：分位点用基准池算
    ss = sorted(sig[i] for i in pool)
    cuts = [ss[int(k * len(ss) / NDEC)] for k in range(1, NDEC)]

    def dec(x):
        lo, hi = 0, len(cuts)
        while lo < hi:
            m = (lo + hi) // 2
            if x >= cuts[m]:
                lo = m + 1
            else:
                hi = m
        return lo

    bypool = defaultdict(list)
    for i in pool:
        bypool[dec(sig[i])].append(V[i])
    tdec = {i: dec(sig[i]) for i in T}
    basemed = {k: med(v) for k, v in bypool.items()}
    ratios = [V[i] / basemed[tdec[i]] for i in T]
    pt = med(ratios)

    keys = sorted(bypool)
    boots = []
    for _ in range(B):
        bm = {k: med(rng.choices(bypool[k], k=len(bypool[k]))) for k in keys}
        samp = []
        for _ in range(len(blks)):
            samp.extend(blks[rng.randrange(len(blks))])
        boots.append(med([V[i] / bm[tdec[i]] for i in samp]))
    boots.sort()
    return dict(n=len(T), nb=len(blks), r=pt, lo=boots[int(.025 * B)],
                hi=boots[int(.975 * B) - 1],
                base=med([basemed[tdec[i]] for i in T]))


def verdict(res):
    if res.get("err"):
        return res["err"]
    return "通过" if (res["lo"] > 1.0 and res["nb"] >= 5) else "未通过"


# ───────────────────────── 触发构造 ─────────────────────────
def cooldown(days, cool=COOL):
    out, last = [], None
    for d in sorted(set(days)):
        if last is None or (d - last).days >= cool:
            out.append(d); last = d
    return out


def load_insider(sym, src="new"):
    p = f"{UNI}/data/insider/{sym}.csv" if src == "new" else f"{OLD}/insider/{sym}.csv"
    if not os.path.exists(p):
        return []
    out = []
    for ln in open(p):
        q = ln.rstrip("\n").split("|")
        if src == "new":
            if len(q) < 7 or q[0] == "transaction_date":
                continue
            td, fd, code, plan, owner = q[0], q[1], q[2], q[3] == "1", q[6]
        else:
            if len(q) < 6:
                continue
            td, fd, code, plan, owner = q[0], q[1], q[2], q[3] == "1", q[5]
        try:
            td_, fd_ = date.fromisoformat(td[:10]), date.fromisoformat(fd[:10])
        except Exception:
            continue
        if not owner:
            continue
        out.append(dict(td=td_, fd=fd_, code=code, plan=plan, owner=owner))
    return out


def insider_triggers(txs, code, drop_plan, K=2, mode="kth"):
    """簇用 transaction_date 30 日窗定义；触发日 = 最早凑够 K 个不同申报人的 filing_date

    mode="kth"  registry M7 定义
    mode="max"  旧 ev_engine 口径（窗口内最晚 filing_date），自检用
    """
    xs = [x for x in txs if x["code"] == code and (not drop_plan or not x["plan"])]
    xs.sort(key=lambda x: x["td"])
    raw = []
    for i, a in enumerate(xs):
        w = [x for x in xs if 0 <= (x["td"] - a["td"]).days < WIN]
        if len(set(x["owner"] for x in w)) < K:
            continue
        if mode == "max":
            raw.append(max(x["fd"] for x in w))
        else:
            seen, ka = set(), None
            for x in sorted(w, key=lambda y: y["fd"]):
                seen.add(x["owner"])
                if len(seen) >= K:
                    ka = x["fd"]; break
            if ka:
                raw.append(ka)
    return cooldown(raw), len(xs)


def load_analyst(sym, src="new", guard=True):
    p = f"{UNI}/data/analyst/{sym}.csv" if src == "new" else f"{OLD}/analyst/{sym}.csv"
    if not os.path.exists(p):
        return []
    rows = []
    for ln in open(p):
        q = ln.rstrip("\n").split("|")
        if src == "new":
            if len(q) < 6 or q[0] == "publish_time":
                continue
            ts_s, firm, pt_s, adj_s, pw_s = q[0], q[1], q[3], q[4], q[5]
        else:
            if len(q) < 8:
                continue
            ts_s, firm, pt_s, adj_s, pw_s = q[0], q[2], q[4], q[5], q[6]
        try:
            ts = datetime.fromisoformat(ts_s)
        except Exception:
            continue
        firm = firm.strip()
        if not firm:
            continue
        try:
            pt = float(adj_s or pt_s)
        except Exception:
            continue
        if pt <= 0:
            continue
        try:
            pw = float(pw_s)
        except Exception:
            pw = None
        if guard and pw and (pt / pw > 4 or pt / pw < 0.25):
            continue
        d = ts.date() + (timedelta(days=1) if ts.hour >= 20 else timedelta(0))
        rows.append((d, firm, pt))
    return sorted(rows, key=lambda x: (x[0], x[1]))


def analyst_triggers(rows, K=3, directional=True):
    prev, ev = {}, []
    for d, firm, pt in rows:
        if firm in prev:
            dr = 1 if pt > prev[firm] else (-1 if pt < prev[firm] else 0)
            if dr != 0 or not directional:
                ev.append((d, firm, dr))
        prev[firm] = pt
    raw = []
    for d, _, _ in ev:
        lo = d - timedelta(days=WIN)
        if directional:
            for want in (1, -1):
                if len({f for dd, f, dr in ev if lo <= dd <= d and dr == want}) >= K:
                    raw.append(d); break
        else:
            if len({f for dd, f, dr in ev if lo <= dd <= d}) >= K:
                raw.append(d)
    return cooldown(raw), len(rows), len(ev)


def load_congress(sym, src="new"):
    p = f"{CONG_NEW}/{sym}.csv" if src == "new" else f"{OLD}/congress/{sym}.csv"
    if not os.path.exists(p):
        return []
    out = []
    for ln in open(p):
        q = ln.rstrip("\n").split("|")
        if len(q) < 4 or q[0] == "transaction_date":
            continue
        try:
            fd = date.fromisoformat(q[1][:10])
        except Exception:
            continue
        out.append(fd)
    return sorted(out)


def congress_triggers(fds, K=1):
    uniq = sorted(set(fds))
    raw = []
    for d in uniq:
        lo = d - timedelta(days=WIN)
        if sum(1 for x in fds if lo <= x <= d) >= K:
            raw.append(d)
    return cooldown(raw), len(fds), len(uniq)


# ───────────────────────── 元数据 ─────────────────────────
def universe():
    rows = list(csv.DictReader(open(f"{UNI}/universe.csv")))
    out = {}
    for r in rows:
        if r["asset_class"] != "us_equity":
            continue
        mc = float(r["mktcap_2026_usd"] or 0)
        tier = r["size_tier"] or ("large" if mc >= 1e10 else "mid" if mc >= 2e9 else "small" if mc > 0 else "")
        out[r["symbol"]] = dict(sector=r["sector"], stratum=r["stratum"], size=tier,
                                vol=r["vol_tier"], ipo=r["ipo_date"], bars=int(r["bars"]),
                                n_insider=int(r["n_insider"] or 0), n_analyst=int(r["n_analyst"] or 0),
                                new=r["stratum"] == "recent_ipo")
    return out


LEGACY11 = ["NVDA", "TSLA", "AAPL", "MSFT", "PLTR", "MSTR", "SOFI", "RIVN", "XOM", "AMD", "KO"]
