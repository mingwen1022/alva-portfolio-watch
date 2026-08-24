"""数据审计：资金费率单位切换点 · 覆盖 · 每日观测数 · OI 币本位可得性。"""
import os, csv, json, collections, statistics as st

U = "/Users/ming/project/alva/backtest/universe/data/crypto"
SYMS = sorted(set(f.split("_")[0].split(".")[0] for f in os.listdir(U) if f.endswith(".csv")))

def read_funding(sym):
    byday = collections.defaultdict(list)
    with open(f"{U}/{sym}_funding.csv") as fh:
        rd = csv.reader(fh); next(rd)
        for t, v in rd:
            if v == "": continue
            byday[t[:10]].append((t[11:16], float(v)))
    return byday

def read_oi(sym):
    coin, val = {}, {}
    with open(f"{U}/{sym}_oi.csv") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            t = row[0][:10]
            if row[1] not in ("", None): coin[t] = float(row[1])
            if row[2] not in ("", None): val[t] = float(row[2])
    return coin, val

out = {}
for s in SYMS:
    bd = read_funding(s)
    days = sorted(bd)
    cnt = collections.Counter(len(v) for v in bd.values())
    brk3 = next((d for d in days if len(bd[d]) >= 3), None)
    brk2 = next((d for d in days if len(bd[d]) >= 2), None)
    # 前后各 30 日 median|f| 比（归一后应连续）
    def med_abs(ds, scale):
        vals = [abs(v)*scale for d in ds for _, v in bd[d]]
        return st.median(vals) if vals else None
    i = days.index(brk3) if brk3 else None
    pre = days[max(0, i-30):i] if i else []
    post = days[i:i+30] if i else []
    coin, val = read_oi(s)
    out[s] = dict(
        n_fund_days=len(days), fund_start=days[0], fund_end=days[-1],
        obs_per_day=dict(sorted(cnt.items())),
        brk_ge3=brk3, brk_ge2=brk2,
        med_abs_pre30_pct=round(med_abs(pre, 1.0), 6) if pre else None,
        med_abs_post30_pct=round(med_abs(post, 100.0), 6) if post else None,
        oi_days=len(val), oi_start=min(val) if val else None, oi_end=max(val) if val else None,
        oi_coin_available=len(coin),
    )
print(json.dumps(out, ensure_ascii=False, indent=1))
