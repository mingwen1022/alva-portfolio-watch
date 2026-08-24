"""小样本诊断：整块自助在块数少时会退化。补一个整块重定位置换检验。

自助只能在观测到的触发块里重采样 —— 块数 k=1 时它只有一个可能的重采样，
区间宽度恒为 0，判据「区间下界 > 1.0」必然通过。k=2~3 时同样近乎必过。
置换检验把同样长度的块随机搬到时间轴别处，用整条序列当参照分布，
在小 k 下仍然有效。
"""
import json, math, datetime, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dr_engine import *

R = 5000


def perm_p(trig_dates, dates, Vmap, seed=SEED, R=R):
    """整块重定位：块长与块内相对位置保持不变，起点随机。返回 p 与随机分布分位"""
    idx = {d: i for i, d in enumerate(dates)}
    tv = [Vmap[d] for d in trig_dates if d in Vmap]
    if not tv:
        return None
    base_all = med([Vmap[d] for d in dates if d in Vmap])
    obs = med(tv) / base_all
    dd = sorted(datetime.date.fromisoformat(d) for d in trig_dates)
    blks = blocks_of(dd)
    offs = [[(x - b[0]).days for x in b] for b in blks]
    n = len(dates)
    rng = random.Random(seed)
    ge = 0; vals = []
    for _ in range(R):
        pool = []
        for off in offs:
            for _try in range(20):
                s0 = rng.randrange(n)
                ii = [s0 + o for o in off]
                if ii[-1] < n:
                    got = [Vmap.get(dates[j]) for j in ii]
                    got = [g for g in got if g is not None]
                    if got:
                        pool.extend(got); break
        if not pool:
            continue
        v = med(pool) / base_all
        vals.append(v)
        if v >= obs:
            ge += 1
    vals.sort()
    return dict(obs=round(obs, 3), p=round((ge + 1) / (len(vals) + 1), 4),
                rand_p50=round(vals[len(vals) // 2], 3),
                rand_p95=round(vals[int(0.95 * (len(vals) - 1))], 3))


def boot_distinct(trig_dates, Vmap, seed=SEED, B=2000):
    dd = sorted(datetime.date.fromisoformat(d) for d in trig_dates)
    blks = blocks_of(dd)
    Vd = {datetime.date.fromisoformat(d): Vmap[d] for d in trig_dates if d in Vmap}
    rng = random.Random(seed)
    vals = set()
    for _ in range(B):
        samp = []
        for _ in range(len(blks)):
            samp.extend(blks[rng.randrange(len(blks))])
        got = [Vd[x] for x in samp if x in Vd]
        if got:
            vals.add(round(med(got), 6))
    return len(blks), len(vals)


out = {}
for sym in SYMS:
    bars = load_bars(sym)
    S = build(sym, bars)
    f00, fmax, brk = load_funding(sym)
    oi = load_oi(sym)
    px = {S["dates"][i]: S["close"][i - 1] for i in range(1, S["n"])}
    Vmap = {S["dates"][i]: S["V"][i] for i in range(S["n"]) if S["V"][i] is not None}
    dates = sorted(Vmap)
    lo = max(min(f00), min(oi), dates[0]); hi = min(max(f00), max(oi), dates[-1])
    dates = [d for d in dates if lo <= d <= hi]
    ds = set(dates)
    sigs = {"DR1": sig_dr1(f00, dates) & ds, "DR2": sig_dr2(f00, dates) & ds,
            "DR3": sig_dr3(oi, dates, px=None) & ds, "DR3_coin": sig_dr3(oi, dates, px=px) & ds}
    sigs["DR123"] = sigs["DR1"] | sigs["DR2"] | sigs["DR3"]
    rec = {}
    for k, t in sigs.items():
        if not t:
            rec[k] = None; continue
        nb, nd = boot_distinct(sorted(t), Vmap)
        rec[k] = dict(n=len(t), blocks=nb, boot_distinct_medians=nd,
                      perm=perm_p(sorted(t), dates, Vmap))
    # 3 次/日时段：当日 max|f| 相对 00:00 抽样的低估程度（只看高费率日）
    era = [d for d in dates if d >= brk and d in f00 and d in fmax and abs(f00[d]) > 1e-6]
    era.sort(key=lambda d: -abs(f00[d]))
    top = era[:max(1, len(era) // 10)]
    rr = sorted(abs(fmax[d]) / abs(f00[d]) for d in top)
    rec["maxday_over_0000_topdecile"] = dict(n=len(rr), p50=round(rr[len(rr) // 2], 2),
                                             p90=round(rr[int(0.9 * (len(rr) - 1))], 2),
                                             max=round(rr[-1], 2))
    out[sym] = rec

print(json.dumps(out, ensure_ascii=False, indent=1))
