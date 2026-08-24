"""分层交叉表：通过比例 + Wilson 区间 + 倍数分布"""
import json, math, numpy as np, statistics as st
from collections import defaultdict
R=json.load(open("pv1_per_ticker.json"))

def wilson(k,n,z=1.96):
    if n==0: return (0,0)
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0,c-h),min(1,c+h))

def line(name,rows):
    n=len(rows); k=sum(1 for x in rows if x["passed"])
    ms=[x["mult"] for x in rows if x["mult"] is not None]
    lo,hi=wilson(k,n)
    fr=[x["freq"] for x in rows if x["freq"] is not None]
    tg=[x["n_trig"] for x in rows]
    return (f"{name:<16}{k:>4}/{n:<4}{k/n*100:>7.0f}%   [{lo*100:>4.0f}%, {hi*100:>4.0f}%]"
            f"{st.median(ms):>8.2f}  [{np.percentile(ms,25):.2f}, {np.percentile(ms,75):.2f}]"
            f"{st.median(tg):>7.0f}{st.median(fr):>8.1f}")

HDR=f"{'分层':<16}{'通过':>9}{'比例':>8}   {'95% Wilson':<14}{'倍数中位':>8}  {'四分位':<16}{'触发':>5}{'次/年':>8}"
def block(title,keyfn,order=None):
    print(f"\n### {title}\n{HDR}")
    g=defaultdict(list)
    for x in R:
        k=keyfn(x)
        if k is not None: g[k].append(x)
    ks=order if order else sorted(g,key=lambda k:-len(g[k]))
    for k in ks:
        if k in g: print(line(str(k),g[k]))

print(HDR); print(line("全体",R))
block("资产类别",lambda x:{"us_equity":"美股","crypto":"加密"}[x["asset"]],["美股","加密"])
block("波动档（本次实算 σ_ann 中位）",lambda x:x["vol_tier"],["低波 <25%","中波 25-50%","高波 >50%"])
block("波动档（universe.csv 全样本口径）",lambda x:x["vol_tier_csv"],["低波 <25%","中波 25-50%","高波 >50%"])
block("市值档（仅美股）",lambda x:x["size_tier"] if x["asset"]=="us_equity" else None,["大盘","中盘","小盘","—"])
block("行业部门（仅美股）",lambda x:x["sector"] if x["asset"]=="us_equity" else None)
block("选取层",lambda x:x["stratum"])

print("\n### 美股 行业 × 波动档 通过数/标的数")
sec=sorted({x["sector"] for x in R if x["asset"]=="us_equity"})
vts=["低波 <25%","中波 25-50%","高波 >50%"]
print(f"{'部门':<10}"+"".join(f"{v:>14}" for v in vts)+f"{'合计':>10}")
for s in sec:
    cells=[]
    for v in vts:
        rr=[x for x in R if x["asset"]=="us_equity" and x["sector"]==s and x["vol_tier"]==v]
        cells.append(f"{sum(1 for x in rr if x['passed'])}/{len(rr)}" if rr else "—")
    rr=[x for x in R if x["asset"]=="us_equity" and x["sector"]==s]
    print(f"{s:<10}"+"".join(f"{c:>14}" for c in cells)+f"{sum(1 for x in rr if x['passed'])}/{len(rr):<10}")

print("\n### 未通过的标的")
print(f"{'标的':<7}{'类别':<8}{'部门':<8}{'波动档':<12}{'市值':<6}{'年':>6}{'触发':>6}{'块':>5}{'倍数':>7}   区间")
for x in sorted(R,key=lambda x:(x["mult"] is None,x["mult"] or 0)):
    if not x["passed"]:
        print(f"{x['sym']:<7}{('美股' if x['asset']=='us_equity' else '加密'):<8}{x['sector']:<8}"
              f"{str(x['vol_tier']):<12}{x['size_tier']:<6}{x['years']:>6.1f}{x['n_trig']:>6}"
              f"{str(x['blocks']):>5}{(x['mult'] or float('nan')):>7.2f}   [{x['lo']}, {x['hi']}]")

print("\n### M23 分布可用性 ρ = P(|z| ≥ 1.5)")
rho=[x["rho"] for x in R]
print(f"全样本 ρ：中位 {st.median(rho):.3f}  范围 [{min(rho):.3f}, {max(rho):.3f}]  "
      f"ρ<2% 的标的 {sum(1 for r in rho if r<0.02)}  ρ>40% 的标的 {sum(1 for r in rho if r>0.40)}")
r2=[x["rho2y"] for x in R]
print(f"近 2 年 ρ：中位 {st.median(r2):.3f}  范围 [{min(r2):.3f}, {max(r2):.3f}]  "
      f"ρ<2% 的标的 {sum(1 for r in r2 if r<0.02)}  ρ>40% 的标的 {sum(1 for r in r2 if r>0.40)}")
lowest=sorted(R,key=lambda x:x["rho"])[:6]
print("ρ 最低六只：" + " · ".join(f"{x['sym']} {x['rho']:.3f}" for x in lowest))
print(f"峰度：中位 {st.median(x['kurt'] for x in R):.1f}  范围 [{min(x['kurt'] for x in R):.1f}, {max(x['kurt'] for x in R):.1f}]")
