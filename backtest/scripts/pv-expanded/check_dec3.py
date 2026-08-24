"""决策 #3 的依据在新池上的复算：
量能分布形状是否在资产类别之间差得比类别之内更多；
以及 P(RVOL≥θv | |z|≥1.5)（registry 引的 0.22–0.27 低波蓝筹 / 0.43–0.62 高波）。"""
import numpy as np, statistics as st, json
from universe_load import roster, prep
rows=[]
for r in roster():
    ind=prep(r); rv=ind["rvol"]; z=ind["z"]
    ok=(~np.isnan(rv))&(~np.isnan(z))
    rvv=rv[ok]; zz=z[ok]; hit=np.abs(zz)>=1.5
    rec=dict(sym=ind["sym"],asset=ind["asset"],vt=ind["vol_tier"],sz=ind["size_tier"],sec=ind["sector"],
             years=ind["years"],p90=float(np.percentile(rvv,90)),p99=float(np.percentile(rvv,99)),
             pz=float(np.mean(hit)))
    for v in [1.5,2.0,2.5,3.0,3.5]:
        rec[f"pv{v}"]=float(np.mean(rvv>=v))                       # 无条件放量概率
        rec[f"cond{v}"]=float(np.mean(rvv[hit]>=v)) if hit.any() else None   # 条件概率
        rec[f"joint{v}"]=float(np.mean(hit&(rvv>=v)))              # 每日触发概率
    rows.append(rec)
json.dump(rows,open("dec3.json","w"),indent=1,ensure_ascii=False)
L=[x for x in rows if x["years"]>=5]
print("### 每日触发概率（θz=1.5 ∧ RVOL≥θv）—— 资产类别分档把两类拉到同一水平")
print(f"{'组':<16}{'n':>4}"+"".join(f"{'θv='+str(v):>10}" for v in [1.5,2.0,2.5,3.0,3.5]))
for lab,sel in [("美股 ≥5 年",lambda x:x["asset"]=="us_equity"),("加密 ≥5 年",lambda x:x["asset"]=="crypto")]:
    g=[x for x in L if sel(x)]
    print(f"{lab:<16}{len(g):>4}"+"".join(f"{st.median(x[f'joint{v}'] for x in g)*100:>9.2f}%" for v in [1.5,2.0,2.5,3.0,3.5]))
print("\n### RVOL 分布形状（P90 / P99），组间 vs 组内")
print(f"{'组':<16}{'n':>4}{'P90 中位':>10}{'P90 范围':>18}{'P99 中位':>10}{'P99 范围':>18}")
for lab,sel in [("美股 低波",lambda x:x["asset"]=="us_equity" and x["vt"]=="低波 <25%"),
                ("美股 中波",lambda x:x["asset"]=="us_equity" and x["vt"]=="中波 25-50%"),
                ("美股 高波",lambda x:x["asset"]=="us_equity" and x["vt"]=="高波 >50%"),
                ("美股 大盘",lambda x:x["asset"]=="us_equity" and x["sz"]=="大盘"),
                ("美股 小盘",lambda x:x["asset"]=="us_equity" and x["sz"]=="小盘"),
                ("加密",lambda x:x["asset"]=="crypto")]:
    g=[x for x in L if sel(x)]
    if not g: continue
    p9=[x["p90"] for x in g]; p99=[x["p99"] for x in g]
    print(f"{lab:<16}{len(g):>4}{st.median(p9):>10.2f}   [{min(p9):.2f}, {max(p9):.2f}]{'':<4}"
          f"{st.median(p99):>10.2f}   [{min(p99):.2f}, {max(p99):.2f}]")
print("\n### P(RVOL≥θv | |z|≥1.5) —— 量能腿在多大比例上还起筛子作用")
print(f"{'组':<16}{'n':>4}"+"".join(f"{'θv='+str(v):>12}" for v in [2.0,2.5,3.0]))
for lab,sel in [("美股 低波",lambda x:x["asset"]=="us_equity" and x["vt"]=="低波 <25%"),
                ("美股 中波",lambda x:x["asset"]=="us_equity" and x["vt"]=="中波 25-50%"),
                ("美股 高波",lambda x:x["asset"]=="us_equity" and x["vt"]=="高波 >50%"),
                ("加密",lambda x:x["asset"]=="crypto")]:
    g=[x for x in L if sel(x)]
    if not g: continue
    print(f"{lab:<16}{len(g):>4}"+"".join(
        f"   {st.median(x[f'cond{v}'] for x in g):.2f} [{min(x[f'cond{v}'] for x in g):.2f},{max(x[f'cond{v}'] for x in g):.2f}]" for v in [2.0,2.5,3.0]))
