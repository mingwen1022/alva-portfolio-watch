"""EV 族数据质量检查：10b5-1 字段覆盖率（按年）· 申报滞后 · 议员滞后"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from collections import Counter, defaultdict

U = universe()
SYMS = [s for s in U if s != "SPY"]
OUT = f"{ROOT}/out"

# ── 1. is_10b51 按年覆盖 ────────────────────────────────────────────
byyear = defaultdict(lambda: [0, 0])          # 年 → [S 笔数, 标记 10b5-1 的笔数]
for s in SYMS:
    for x in load_insider(s):
        if x["code"] != "S":
            continue
        y = x["td"].year
        byyear[y][0] += 1
        byyear[y][1] += 1 if x["plan"] else 0
print("### EV2 的 is_10b51 字段按年覆盖（全部 91 只标的的 S 笔）\n")
print(f"{'年':<6}{'S 笔数':>8}{'标记 10b5-1':>12}{'标记率':>8}")
cov = {}
for y in sorted(byyear):
    n, k = byyear[y]
    cov[y] = k / n if n else 0
    print(f"{y:<6}{n:>8}{k:>12}{k/n*100:>7.1f}%")

# 受影响比例：过滤器实际失效的年份 = 标记率 < 5%
bad = [y for y in cov if cov[y] < 0.05]
tot = sum(byyear[y][0] for y in byyear)
badn = sum(byyear[y][0] for y in bad)
print(f"\n标记率 <5% 的年份 {sorted(bad)}，涉及 S 笔 {badn}/{tot} = {badn/tot*100:.1f}%")

# 受影响的触发比例
aff = {"n_trig": 0, "n_trig_bad": 0}
per_sym = []
for s in SYMS:
    txs = load_insider(s)
    days, _ = insider_triggers(txs, "S", True, 2, "kth")
    xs = sorted([x for x in txs if x["code"] == "S" and not x["plan"]], key=lambda x: x["td"])
    nb = 0
    for d in days:
        # 该触发所依赖的交易大致落在 d 之前 60 日历日内
        w = [x for x in xs if 0 <= (d - x["fd"]).days <= 60]
        if w and all(x["td"].year in bad for x in w):
            nb += 1
    aff["n_trig"] += len(days); aff["n_trig_bad"] += nb
    per_sym.append((s, len(days), nb))
print(f"EV2 触发合计 {aff['n_trig']}，全部依赖失效年份交易的触发 {aff['n_trig_bad']} "
      f"= {aff['n_trig_bad']/max(1,aff['n_trig'])*100:.1f}%")

# ── 2. 内部人申报滞后 ────────────────────────────────────────────
print("\n### 申报滞后 L = filing_date − transaction_date\n")
lag0 = []
for s in SYMS:
    for code, tag in (("P", "EV1"), ("S", "EV2")):
        xs = [x for x in load_insider(s) if x["code"] == code and (code == "P" or not x["plan"])]
        if len(xs) < 5:
            continue
        L = sorted((x["fd"] - x["td"]).days for x in xs)
        z = sum(1 for x in L if x <= 0) / len(L)
        lag0.append(dict(sym=s, sig=tag, n=len(xs), med=L[len(L)//2],
                         p90=L[int(.9*len(L))], mx=L[-1], zero=round(z, 3)))
worst = sorted([x for x in lag0 if x["sig"] == "EV1"], key=lambda x: -x["zero"])[:12]
print("EV1（code=P）滞后 ≤0 日占比最高的 12 只：")
print(f"{'标的':<7}{'笔数':>6}{'中位':>6}{'P90':>6}{'最大':>7}{'滞后≤0 占比':>12}")
for x in worst:
    print(f"{x['sym']:<7}{x['n']:>6}{x['med']:>6}{x['p90']:>6}{x['mx']:>7}{x['zero']*100:>11.0f}%")
n_ev1 = [x for x in lag0 if x["sig"] == "EV1"]
print(f"\nEV1 有 ≥5 笔 P 的标的 {len(n_ev1)} 只，其中滞后≤0 占比 >20% 的 "
      f"{sum(1 for x in n_ev1 if x['zero']>0.2)} 只")

# ── 3. 议员申报滞后 ──────────────────────────────────────────────
print("\n### 议员申报滞后")
allL = []
for s in SYMS:
    p = f"{CONG_NEW}/{s}.csv"
    if not os.path.exists(p):
        continue
    for ln in open(p):
        q = ln.rstrip("\n").split("|")
        if len(q) < 4 or q[0] == "transaction_date":
            continue
        try:
            td, fd = date.fromisoformat(q[0][:10]), date.fromisoformat(q[1][:10])
        except Exception:
            continue
        allL.append((fd - td).days)
allL.sort()
if allL:
    print(f"n={len(allL)} 中位 {allL[len(allL)//2]} 日 · P90 {allL[int(.9*len(allL))]} · "
          f"最大 {allL[-1]} · 负滞后 {sum(1 for x in allL if x<0)} 行 "
          f"({sum(1 for x in allL if x<0)/len(allL)*100:.2f}%)")

json.dump(dict(cov_10b51={str(k): v for k, v in cov.items()}, bad_years=bad,
               affected_tx=badn/tot, trig=aff, lag=lag0),
          open(f"{OUT}/data_quality.json", "w"), indent=1, ensure_ascii=False, default=str)
