"""三组变体：
  A  全部可判定标的做「当日 |z| 配对基准」控制实验
  B  EV2 只用 2020 年起的交易（is_10b51 字段在 2018/2019 基本为空）
  C  EV1 剔除申报滞后 ≤0 日的记录（坏字段守卫）
  D  符号检验：倍数 >1 的只数是否偏离一半
"""
import sys, os, json, math, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from scrutiny import zmatched
from collections import Counter
from datetime import date

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
FNS = {"EV1": lambda s: insider_triggers(load_insider(s), "P", False, 2, "kth"),
       "EV2": lambda s: insider_triggers(load_insider(s), "S", True, 2, "kth"),
       "EV3": lambda s: analyst_triggers(load_analyst(s))[:2],
       "EV5": lambda s: congress_triggers(load_congress(s))[:2]}
OUT = {}


def binom_p(k, n, p=0.5):
    """双侧二项检验"""
    c = lambda a, b: math.comb(a, b)
    pm = lambda i: c(n, i) * p ** i * (1 - p) ** (n - i)
    obs = pm(k)
    return min(1.0, sum(pm(i) for i in range(n + 1) if pm(i) <= obs * 1.0000001))


# ── A · |z| 配对控制 ────────────────────────────────────────────────
print("### A · 当日 |z| 配对基准（控制「触发当天本身是大波动日」）\n")
print(f"{'信号':<6}{'可判定':>7}{'原口径通过':>11}{'配对后通过':>11}{'配对后倍数中位':>15}{'触发日|z|中位':>13}")
A = {}
for sid, blk in R.items():
    ev = [x for x in blk["rows"] if x["bucket"] in ("通过", "未通过", "反向")]
    rows = []
    for x in ev:
        s = x["sym"]
        S = build(s)
        ti = align(FNS[sid](s)[0], S["ds"])
        zm = zmatched(ti, S)
        if zm:
            rows.append(dict(sym=s, r0=x["r"], lo0=x["lo"], **zm))
    npass0 = sum(1 for x in rows if x["lo0"] > 1.0)
    npass1 = sum(1 for x in rows if x["lo"] > 1.0 and x["nb"] >= 5)
    print(f"{sid:<6}{len(rows):>7}{npass0:>11}{npass1:>11}"
          f"{st.median([x['r'] for x in rows]):>15.3f}{st.median([x['medz'] for x in rows]):>13.2f}")
    A[sid] = rows
    keep = [x for x in rows if x["lo"] > 1.0 and x["nb"] >= 5]
    if keep:
        print("      配对后仍通过：" + " · ".join(
            f"{x['sym']} {x['r']:.2f}[{x['lo']:.2f},{x['hi']:.2f}]" for x in keep))
OUT["zmatch"] = A

# ── D · 符号检验 ────────────────────────────────────────────────────
print("\n### D · 符号检验（倍数 >1 的只数）\n")
print(f"{'信号':<6}{'可判定':>7}{'>1 只数':>9}{'占比':>8}{'中位倍数':>10}{'双侧 p':>9}")
D = {}
for sid, blk in R.items():
    ev = [x for x in blk["rows"] if x["bucket"] in ("通过", "未通过", "反向")]
    k = sum(1 for x in ev if x["r"] > 1)
    p = binom_p(k, len(ev))
    D[sid] = dict(k=k, n=len(ev), p=p, med=st.median([x["r"] for x in ev]))
    print(f"{sid:<6}{len(ev):>7}{k:>9}{k/len(ev)*100:>7.0f}%"
          f"{st.median([x['r'] for x in ev]):>10.3f}{p:>9.3f}")
OUT["sign"] = D

# ── B · EV2 限定 2020 年起 ──────────────────────────────────────────
print("\n### B · EV2 限定 2020 年起的交易（is_10b51 字段 2018 年 0.2% · 2019 年 4.8%）\n")
B_ = []
for x in R["EV2"]["rows"]:
    if x["bucket"] not in ("通过", "未通过", "反向"):
        continue
    s = x["sym"]
    S = build(s)
    txs = [t for t in load_insider(s) if t["td"] >= date(2020, 1, 1)]
    days, _ = insider_triggers(txs, "S", True, 2, "kth")
    r = evaluate(align(days, S["ds"]), S)
    B_.append(dict(sym=s, r0=x["r"], lo0=x["lo"], n0=x["n"], **{k: r.get(k) for k in
                   ("n", "nb", "r", "lo", "hi", "err")}))
ok = [x for x in B_ if x["r"] is not None and x["nb"] >= 5]
print(f"可判定 {len(ok)}/{len(B_)}（其余触发数掉到判据线下）· 通过 "
      f"{sum(1 for x in ok if x['lo']>1.0)} · 反向 {sum(1 for x in ok if x['hi']<1.0)}")
print(f"倍数中位 全期 {st.median([x['r0'] for x in B_]):.3f} → 2020+ {st.median([x['r'] for x in ok]):.3f}")
print(f"触发数合计 全期 {sum(x['n0'] for x in B_)} → 2020+ {sum(x['n'] or 0 for x in B_)}")
OUT["ev2_2020"] = B_

# ── C · EV1 剔除滞后 ≤0 ────────────────────────────────────────────
print("\n### C · EV1 剔除申报滞后 ≤0 日的记录\n")
C = []
for x in R["EV1"]["rows"]:
    s = x["sym"]
    S = build(s)
    txs = [t for t in load_insider(s) if (t["fd"] - t["td"]).days > 0]
    days, _ = insider_triggers(txs, "P", False, 2, "kth")
    r = evaluate(align(days, S["ds"]), S)
    C.append(dict(sym=s, n0=x["n"], nb0=x["nb"], r0=x["r"], lo0=x["lo"],
                  **{k: r.get(k) for k in ("n", "nb", "r", "lo", "hi", "err")}))
ok = [x for x in C if x["r"] is not None and x["nb"] >= 5]
print(f"守卫后仍可判定 {len(ok)} 只（守卫前 {sum(1 for x in C if x['nb0']>=5)} 只）")
print(f"{'标的':<7}{'守卫前 触发/块/倍数':>24}{'守卫后 触发/块/倍数':>24}")
for x in sorted(C, key=lambda x: -(x["nb0"] or 0))[:12]:
    a = f"{x['n0']}/{x['nb0']}/{('%.2f' % x['r0']) if x['r0'] else '—'}"
    b = f"{x['n'] or 0}/{x['nb'] or 0}/{('%.2f' % x['r']) if x['r'] else '—'}"
    print(f"{x['sym']:<7}{a:>24}{b:>24}")
OUT["ev1_lagguard"] = C

json.dump(OUT, open(f"{ROOT}/out/variants.json", "w"), indent=1, ensure_ascii=False, default=str)
