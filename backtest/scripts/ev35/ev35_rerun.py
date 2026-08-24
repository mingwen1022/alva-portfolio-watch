"""EV3 分析师簇 / EV5 议员交易 在新判据下逐标的重算
判据：相对基准倍数的 95% 自助区间下界 > 1.0（唯一判据）
硬规则：逐标的算不池化 · 整块自助 · 固定种子
V_t = sqrt(mean(r_{t+1..t+5}^2)) / σ_rob,t ； σ_rob = 1.4826*MAD（90 日窗，不含当日）
"""
import csv, statistics as st, random, json, sys, os
from datetime import date, datetime, timedelta
from collections import defaultdict

DAILY = "/Users/ming/project/alva/backtest/data/stocks-daily"
HERE  = os.path.dirname(os.path.abspath(__file__))
DATA  = f"{HERE}/data"
B, SEED, COOL, WIN = 2000, 20260819, 45, 30
SYMS = ["NVDA","TSLA","AAPL","MSFT","PLTR","MSTR","SOFI","RIVN","XOM","AMD","KO"]

# ── V 序列（与 bt2/ev_rerun.py 完全一致） ────────────────────────────────
def build(s):
    p = {}
    with open(f"{DAILY}/{s}.csv") as f:
        for x in csv.reader(f):
            if len(x) >= 3: p[date.fromisoformat(x[0])] = (float(x[1]), float(x[2]))
    ds = sorted(p)
    ret = {ds[i]: p[ds[i]][0]/p[ds[i-1]][0]-1 for i in range(1, len(ds))}
    V = {}
    for i in range(91, len(ds)-5):
        w = [ret[ds[j]] for j in range(i-90, i) if ds[j] in ret]
        if len(w) < 60: continue
        m = st.median(w); sg = 1.4826*st.median([abs(x-m) for x in w])
        if sg <= 0 or ds[i] not in ret: continue
        fut = [ds[i+k] for k in range(1, 6)]
        if not all(x in ret for x in fut): continue
        V[ds[i]] = (sum(ret[x]**2 for x in fut)/5)**.5/sg
    return V, ds

def align(dates, ds):
    S = set(ds); o = []
    for d in dates:
        for k in range(8):
            if d+timedelta(days=k) in S: o.append(d+timedelta(days=k)); break
    return sorted(set(o))

def blocks(t):
    o = []; c = []
    for x in sorted(t):
        if c and (x-c[-1]).days < 7: c.append(x)     # 相邻 <5 交易日 ≈ <7 日历日
        else:
            if c: o.append(c)
            c = [x]
    if c: o.append(c)
    return o

def evaluate(trig, V):
    tv = [d for d in trig if d in V]
    T  = [V[d] for d in tv]
    N  = [v for d, v in V.items() if d not in set(trig)]
    if len(T) < 3 or not N: return None
    base = st.median(N); bs = blocks(tv)
    random.seed(SEED); rs = []
    for _ in range(B):
        fl = [V[x] for _ in range(len(bs)) for x in random.choice(bs)]
        rs.append(st.median(fl)/base)
    rs.sort()
    return {"n": len(T), "nb": len(bs), "r": st.median(T)/base,
            "boot_med": rs[B//2], "lo": rs[int(.025*B)], "hi": rs[int(.975*B)],
            "base": base, "n_base": len(N)}

def cooldown(days):
    out = []; last = None
    for d in sorted(set(days)):
        if last is None or (d-last).days >= COOL: out.append(d); last = d
    return out

# ── EV3 分析师簇：M9 ≥ 3 同向机构 / 30 日窗 ────────────────────────────
def load_analyst(s, guard=True):
    """→ [(可知日, 机构, 目标价, 当时股价)]，按时间升序"""
    rows = []
    for line in open(f"{DATA}/analyst/{s}.csv"):
        q = line.rstrip("\n").split("|")
        if len(q) < 8 or not q[0]: continue
        try: ts = datetime.fromisoformat(q[0])
        except Exception: continue
        firm = q[2].strip()
        if not firm: continue
        try: pt = float(q[5] or q[4])
        except Exception: continue
        try: pw = float(q[6])
        except Exception: pw = None
        if pt <= 0: continue
        # 串标的守卫：目标价与当时股价比值离谱的行几乎必是别家公司的新闻被贴上本标的
        if guard and pw and (pt/pw > 4 or pt/pw < 0.25): continue
        d = ts.date()
        if ts.hour >= 20: d = d + timedelta(days=1)   # 美东收盘后发布 → 次日才可交易
        rows.append((d, firm, pt, pw))
    return sorted(rows, key=lambda x: (x[0], x[1]))

def analyst_triggers(s, K=3, directional=True, guard=True):
    rows = load_analyst(s, guard)
    prev = {}; ev = []                      # (日期, 机构, 方向)
    for d, firm, pt, pw in rows:
        if firm in prev:
            p = prev[firm]
            dr = 1 if pt > p else (-1 if pt < p else 0)
            if dr != 0 or not directional: ev.append((d, firm, dr))
        prev[firm] = pt
    raw = []
    for i, (d, _, _) in enumerate(ev):
        lo = d - timedelta(days=WIN)
        if directional:
            for want in (1, -1):
                firms = {f for dd, f, dr in ev if lo <= dd <= d and dr == want}
                if len(firms) >= K: raw.append(d); break
        else:
            firms = {f for dd, f, dr in ev if lo <= dd <= d}
            if len(firms) >= K: raw.append(d)
    return cooldown(raw), len(rows), len(ev)

# ── EV5 议员交易：M11 ≥ 1 / 申报日 ────────────────────────────────────
def load_congress(s):
    rows = []
    try: f = open(f"{DATA}/congress/{s}.csv")
    except FileNotFoundError: return []
    for line in f:
        q = line.rstrip("\n").split("|")
        if len(q) < 4 or not q[1]: continue
        try: fd = date.fromisoformat(q[1][:10])
        except Exception: continue
        try: td = date.fromisoformat(q[0][:10])
        except Exception: td = None
        rows.append((fd, td, q[2], q[3]))
    return sorted(rows)

def congress_triggers(s, K=1):
    rows = load_congress(s)
    fds = sorted({r[0] for r in rows})
    raw = []
    for d in fds:
        lo = d - timedelta(days=WIN)
        if sum(1 for r in rows if lo <= r[0] <= d) >= K: raw.append(d)
    return cooldown(raw), len(rows), len(fds)

# ── 跑 ────────────────────────────────────────────────────────────────
def report(title, fn, note=""):
    print(f"\n{'='*88}\n{title}\n判据：95% 区间下界 > 1.0 · 冷却 {COOL} 日 · 整块自助 {B} 次 · 种子 {SEED}"
          + (f"\n{note}" if note else "") + f"\n{'='*88}")
    print(f"{'标的':<7}{'原始行':>7}{'触发':>6}{'块':>5}{'倍数':>8}{'95% 区间':>18}{'覆盖期':>26}{'判定':>6}")
    res = []
    for s in SYMS:
        V, ds = build(s)
        trig_raw, nraw, extra = fn(s)
        trig = align(trig_raw, ds)
        r = evaluate(trig, V)
        span = f"{trig[0]}→{trig[-1]}" if trig else "—"
        if r is None:
            print(f"{s:<7}{nraw:>7}{len(trig):>6}{'—':>5}{'样本不足':>8}{'—':>18}{span:>26}{'⚪':>6}")
            res.append({"sym": s, "n_raw": nraw, "n": len(trig), "verdict": "样本不足"}); continue
        ok = r["lo"] > 1.0
        ci = "[%.2f, %.2f]" % (r["lo"], r["hi"])
        print(f"{s:<7}{nraw:>7}{r['n']:>6}{r['nb']:>5}{r['r']:>8.2f}{ci:>18}{span:>26}{('🟡通过' if ok else '未通过'):>6}")
        res.append({"sym": s, "n_raw": nraw, "extra": extra, **{k: round(v,4) if isinstance(v,float) else v for k,v in r.items()},
                    "span": span, "pass": ok})
    ps = [x for x in res if x.get("pass")]
    print(f"\n  通过 {len(ps)}/{len(SYMS)} 只" + (f"  →  {', '.join(x['sym'] for x in ps)}" if ps else "  →  无"))
    return res

if __name__ == "__main__":
    OUT = {}
    OUT["EV3 分析师簇 M9≥3 同向"] = report("EV3 分析师簇   M9 ≥ 3 同向机构 · 30 日窗 · 方向口径 B",
        lambda s: analyst_triggers(s, 3, True, True), "口径 B = 同机构相邻两次目标价之差；已剔除目标价/当时股价 ∉ [0.25,4] 的串标的行")
    OUT["EV5 议员交易 M11≥1"] = report("EV5 议员交易   M11 ≥ 1 · 30 日窗 · 触发日 = 申报日",
        lambda s: congress_triggers(s, 1))
    json.dump(OUT, open(f"{HERE}/ev35_rerun.json", "w"), default=str, indent=1, ensure_ascii=False)
