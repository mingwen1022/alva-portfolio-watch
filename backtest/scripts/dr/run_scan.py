"""阈值扫描 + 跨标的同日触发 + 00:00 抽样低估程度。

阈值不是本回测要选的（业界给值，回测只验证），扫描只回答一个问题：
现有阈值不通过，是阈值取错了还是信号本身没有可测强度。
"""
import json, datetime, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dr_engine import *

out = {"dr1_scan": {}, "dr3_scan": {}, "dr3coin_scan": {}, "sampling": {}, "cross": {}}
fire = collections.defaultdict(lambda: collections.defaultdict(set))

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
    ds = set(dates); years = len(dates) / 365.0

    def st_of(t):
        t = t & ds
        if not t:
            return None
        base = [Vmap[d] for d in dates if d not in t]
        td = sorted(datetime.date.fromisoformat(d) for d in t)
        Vd = {datetime.date.fromisoformat(d): Vmap[d] for d in t}
        r = ratio_ci(td, Vd, base)
        r["F"] = round(len(t) / years, 1)
        return r

    out["dr1_scan"][sym] = {th: st_of(sig_dr1(f00, dates, th=th))
                            for th in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]}
    out["dr3_scan"][sym] = {th: st_of(sig_dr3(oi, dates, th=th))
                            for th in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]}
    out["dr3coin_scan"][sym] = {th: st_of(sig_dr3(oi, dates, th=th, px=px))
                                for th in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]}

    # 00:00 单点抽样把当日极值低估多少（只有 3 次/日的时段能算）
    era = [d for d in dates if d >= brk and d in f00 and d in fmax and abs(f00[d]) > 1e-6]
    ratios = sorted(abs(fmax[d]) / abs(f00[d]) for d in era)
    need = 0.40 / max(abs(f00[d]) for d in dates if d in f00)   # 要达到 0.40 需要的倍数
    out["sampling"][sym] = dict(
        era_days=len(era), max_f00_all=round(max(abs(f00[d]) for d in dates if d in f00), 4),
        need_multiple_for_0p40=round(need, 2),
        p_ratio_ge_need=round(sum(1 for r in ratios if r >= need) / len(ratios), 4) if ratios else None,
        p_ratio_ge_1p5=round(sum(1 for r in ratios if r >= 1.5) / len(ratios), 4) if ratios else None,
        p_ratio_eq_1=round(sum(1 for r in ratios if r < 1.001) / len(ratios), 4) if ratios else None)

    fire["DR1"][sym] = sig_dr1(f00, dates) & ds
    fire["DR2"][sym] = sig_dr2(f00, dates) & ds
    fire["DR3"][sym] = sig_dr3(oi, dates, px=None) & ds

# 跨标的同日触发：一个组合会同时收到几条
for k in ["DR1", "DR2", "DR3"]:
    cnt = collections.Counter()
    for sym, s in fire[k].items():
        for d in s:
            cnt[d] += 1
    dist = collections.Counter(cnt.values())
    out["cross"][k] = dict(distinct_days=len(cnt), total_fires=sum(cnt.values()),
                           by_n_symbols={str(a): b for a, b in sorted(dist.items())},
                           multi_day_share=round(sum(b for a, b in dist.items() if a >= 2) / len(cnt), 3) if cnt else None,
                           examples_all4=sorted(d for d, c in cnt.items() if c == 4)[:10])

print(json.dumps(out, ensure_ascii=False, indent=1))
