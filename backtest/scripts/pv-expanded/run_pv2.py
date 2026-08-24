"""PV2 放量强度（修饰符）：PV1 触发内按 RVOL 分档，检验强度是否单调。
股票 普通 [2,3) / 强 [3,∞)；另给三档 [2,3) [3,5) [5,∞)。
加密 θv 本就是 3.0，PV1 触发全部落进「强」，另用 4.5 做探索性切点。"""
import json, numpy as np, statistics as st
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci

def sub(ind,T,lo,hi):
    rv=ind["rvol"]
    S=[t for t in T if lo<=rv[t]<hi]
    if len(S)<3: return None
    return ratio_ci(ind,S,purge_from=T,nboot=2000)

out=[]
for r in roster():
    ind=prep(r); asset=ind["asset"]
    T=[t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(ind["V"][t])]
    if len(T)<6: continue
    bins=([("普通 2.0–3.0",2.0,3.0),("强 ≥3.0",3.0,1e9),
           ("中 3.0–5.0",3.0,5.0),("很强 ≥5.0",5.0,1e9)] if asset=="us_equity" else
          [("普通 3.0–4.5",3.0,4.5),("强 ≥4.5",4.5,1e9),
           ("中 4.5–7.0",4.5,7.0),("很强 ≥7.0",7.0,1e9)])
    rec=dict(sym=ind["sym"],asset=asset,vol_tier=ind["vol_tier"],size_tier=ind["size_tier"],
             sector=ind["sector"],n_trig=len(T),bins={})
    for nm,lo,hi in bins:
        res=sub(ind,T,lo,hi)
        if res: rec["bins"][nm]=dict(n=res["n"],blocks=res["blocks"],mult=round(res["mult"],3),
                                     lo=round(res["lo"],3),passed=bool(res["pass_"]))
    out.append(rec)
json.dump(out,open("pv2_per_ticker.json","w"),indent=1,ensure_ascii=False)

def show(asset,pair,triple):
    rows=[x for x in out if x["asset"]==asset]
    ok=[x for x in rows if all(b in x["bins"] for b in pair)]
    d=[x["bins"][pair[1]]["mult"]-x["bins"][pair[0]]["mult"] for x in ok]
    print(f"\n{asset}  可比标的 {len(ok)}/{len(rows)}")
    for b in pair+triple:
        v=[x["bins"][b]["mult"] for x in rows if b in x["bins"]]
        n=[x["bins"][b]["n"] for x in rows if b in x["bins"]]
        if v: print(f"  {b:<14} 标的 {len(v):>3}  触发中位 {st.median(n):>5.0f}  倍数中位 {st.median(v):.3f}"
                    f"  四分位 [{np.percentile(v,25):.2f}, {np.percentile(v,75):.2f}]")
    if d:
        print(f"  逐标的配对差（强 − 普通）：中位 {st.median(d):+.3f}   强 > 普通 的比例 "
              f"{sum(1 for x in d if x>0)}/{len(d)} = {sum(1 for x in d if x>0)/len(d)*100:.0f}%")
    ok3=[x for x in rows if all(b in x["bins"] for b in [pair[0]]+triple)]
    mono=sum(1 for x in ok3 if x["bins"][pair[0]]["mult"]<x["bins"][triple[0]]["mult"]<x["bins"][triple[1]]["mult"])
    if ok3: print(f"  三档严格单调的标的：{mono}/{len(ok3)} = {mono/len(ok3)*100:.0f}%（随机期望 17%）")

show("us_equity",["普通 2.0–3.0","强 ≥3.0"],["中 3.0–5.0","很强 ≥5.0"])
show("crypto",["普通 3.0–4.5","强 ≥4.5"],["中 4.5–7.0","很强 ≥7.0"])
