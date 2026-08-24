"""DR4 代币解锁。

⚠️ 端点只覆盖 2025-08-20 → 2026-12-31，且 BTC/ETH/SOL/DOGE 全部 0 条事件。
   只能换一批有解锁日程的代币来测，且窗口不足 12 个月。
⚠️ value_to_market_cap 是「解锁市值 / 市值」，用的是查询时点的参考价与市值，
   不是解锁当日的 —— 用它做历史筛选带时点污染。
"""
import json, math, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dr_engine import *

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
TOK = {"arbitrum": "ARB", "optimism": "OP", "sui": "SUI", "aptos": "APT",
       "starknet": "STRK", "sei-network": "SEI", "immutable-x": "IMX",
       "avalanche-2": "AVAX", "axie-infinity": "AXS"}
PCT = 3.0
LEAD = 7

U = json.load(open(f"{DATA}/unlock_events.json"))
out = {}
for tid, sym in TOK.items():
    p = f"{DATA}/px_{sym}.csv"
    if not os.path.exists(tid) and not os.path.exists(p):
        continue
    bars = load_bars(sym, path=p)
    S = build(sym, bars)
    Vmap = {S["dates"][i]: S["V"][i] for i in range(S["n"]) if S["V"][i] is not None}
    dates = sorted(Vmap)
    if not dates:
        out[sym] = {"err": "no V"}; continue
    evs = U.get(tid, {}).get("events", [])
    rows = []
    for e in evs:
        d = datetime.date.fromisoformat(e["d"][:10])
        pct = max(e["cliff_pct"] or 0, e["lin_pct"] or 0)
        rows.append((d, pct))
    rows.sort()

    def trig_set(lead, minpct):
        s = set()
        for d, pct in rows:
            if pct <= minpct:
                continue
            t = (d - datetime.timedelta(days=lead)).isoformat()
            if t in Vmap and dates[0] <= t <= dates[-1]:
                s.add(t)
        return s

    rec = {"n_events": len(rows), "n_gt3": sum(1 for _, p2 in rows if p2 > PCT),
           "span": [dates[0], dates[-1]], "days": len(dates)}
    for tag, lead, mp in [("T-7_gt3", LEAD, PCT), ("T-7_all", LEAD, -1),
                          ("T-1_gt3", 1, PCT), ("T-1_all", 1, -1)]:
        t = trig_set(lead, mp)
        if not t:
            rec[tag] = None; continue
        base = [Vmap[x] for x in dates if x not in t]
        td = sorted(datetime.date.fromisoformat(x) for x in t)
        Vd = {datetime.date.fromisoformat(x): Vmap[x] for x in t}
        rec[tag] = ratio_ci(td, Vd, base)
    rec["gt3_dates"] = sorted(d.isoformat() for d, p2 in rows if p2 > PCT)
    rec["pct_values"] = [round(p2, 2) for _, p2 in rows]
    out[sym] = rec

print(json.dumps(out, ensure_ascii=False, indent=1))
