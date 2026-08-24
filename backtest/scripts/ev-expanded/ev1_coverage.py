"""EV1 覆盖分析：小盘 / 次新股到底有没有把样本量做起来"""
import sys, os, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from collections import defaultdict, Counter

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
by = {x["sym"]: x for x in R["EV1"]["rows"]}
rows = []
for s in [k for k in U if k != "SPY"]:
    txs = load_insider(s)
    P = [x for x in txs if x["code"] == "P"]
    owners = set(x["owner"] for x in P)
    days, _ = insider_triggers(txs, "P", False, 2, "kth")
    lag0 = sum(1 for x in P if (x["fd"] - x["td"]).days <= 0) / len(P) if P else None
    yrs = U[s]["bars"] / 252
    rows.append(dict(sym=s, size=U[s]["size"], new=U[s]["new"], sector=U[s]["sector"],
                     vol=U[s]["vol"], n_ins=U[s]["n_insider"], nP=len(P), nOwner=len(owners),
                     nTrig=len(days), per_yr=len(days) / yrs if yrs else 0,
                     lag0=lag0, nb=by[s]["nb"], bucket=by[s]["bucket"], r=by[s]["r"],
                     lo=by[s]["lo"], yrs=yrs))

print("### EV1 触发覆盖 · 按市值档\n")
print(f"{'档':<8}{'标的数':>6}{'有 P 笔':>8}{'≥1 触发':>9}{'块≥5':>7}{'P 笔中位':>9}{'触发次/年 中位':>14}")
for k in ("large", "mid", "small", ""):
    g = [x for x in rows if x["size"] == k]
    if not g:
        continue
    hp = [x for x in g if x["nP"] > 0]
    ht = [x for x in g if x["nTrig"] > 0]
    hb = [x for x in g if x["nb"] >= 5]
    print(f"{k or '—':<8}{len(g):>6}{len(hp):>8}{len(ht):>9}{len(hb):>7}"
          f"{st.median([x['nP'] for x in g]):>9.0f}"
          f"{(st.median([x['per_yr'] for x in ht]) if ht else 0):>14.2f}")

print("\n### EV1 触发覆盖 · 次新股 vs 其余\n")
print(f"{'层':<8}{'标的数':>6}{'有 P 笔':>8}{'≥1 触发':>9}{'块≥5':>7}{'P 笔中位':>9}{'触发次/年 中位':>14}")
for k, lab in ((True, "次新股"), (False, "其余")):
    g = [x for x in rows if x["new"] == k]
    hp = [x for x in g if x["nP"] > 0]
    ht = [x for x in g if x["nTrig"] > 0]
    hb = [x for x in g if x["nb"] >= 5]
    print(f"{lab:<8}{len(g):>6}{len(hp):>8}{len(ht):>9}{len(hb):>7}"
          f"{st.median([x['nP'] for x in g]):>9.0f}"
          f"{(st.median([x['per_yr'] for x in ht]) if ht else 0):>14.2f}")

print("\n### 旧 11 只 vs 新增 80 只\n")
LEG = set(LEGACY11)
for lab, g in (("旧 11 只", [x for x in rows if x["sym"] in LEG]),
               ("新增 80 只", [x for x in rows if x["sym"] not in LEG])):
    ht = [x for x in g if x["nTrig"] > 0]
    hb = [x for x in g if x["nb"] >= 5]
    print(f"{lab:<10} 标的 {len(g):>3} · ≥1 触发 {len(ht):>3} ({len(ht)/len(g)*100:.0f}%) · "
          f"块≥5 {len(hb):>3} ({len(hb)/len(g)*100:.0f}%)")

print("\n### 块≥5（够判据）的标的逐只\n")
print(f"{'标的':<7}{'部门':<7}{'市值':<7}{'次新':<5}{'P 笔':>6}{'人数':>5}{'触发':>5}{'块':>4}"
      f"{'次/年':>7}{'滞后≤0':>8}{'倍数':>7}{'下界':>7}  判定")
for x in sorted([x for x in rows if x["nb"] >= 5], key=lambda x: -(x["r"] or 0)):
    print(f"{x['sym']:<7}{x['sector'] or '—':<7}{x['size'] or '—':<7}{'是' if x['new'] else '':<5}"
          f"{x['nP']:>6}{x['nOwner']:>5}{x['nTrig']:>5}{x['nb']:>4}{x['per_yr']:>7.2f}"
          f"{(x['lag0'] or 0)*100:>7.0f}%{x['r']:>7.2f}{x['lo']:>7.2f}  {x['bucket']}")

print("\n### 零触发的 37 只：是没人买，还是买的人不成簇\n")
z = [x for x in rows if x["nTrig"] == 0 and x["n_ins"] >= 30]
print(f"零触发且有 Form 4 数据的 {len(z)} 只中：P 笔为 0 的 {sum(1 for x in z if x['nP']==0)} 只 · "
      f"有 P 笔但 owner 只 1 人的 {sum(1 for x in z if x['nP']>0 and x['nOwner']<2)} 只 · "
      f"≥2 人但从未落进同一 30 日窗的 {sum(1 for x in z if x['nOwner']>=2)} 只")

json.dump(rows, open(f"{ROOT}/out/ev1_coverage.json", "w"), indent=1, ensure_ascii=False, default=str)
