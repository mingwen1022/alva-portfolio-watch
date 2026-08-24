"""安慰剂平移：触发日整体平移 k 个交易日后重算。
|k| 必须 > 前瞻窗 5，否则平移窗含触发日本身。k = ±6/±10/±20/±40 全部合法。
基准净化用「实际触发日 ∪ 平移后触发日」的 ±5，两侧都不污染。"""
import json, numpy as np, statistics as st
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci

KS=[-40,-20,-10,-6,0,6,10,20,40]
out=[]
for r in roster():
    ind=prep(r)
    T=[t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(ind["V"][t])]
    if len(T)<3: continue
    rec=dict(sym=ind["sym"],asset=ind["asset"],vol_tier=ind["vol_tier"],k={})
    for k in KS:
        S=[t+k for t in T]
        S=[t for t in S if 0<=t<ind["n"] and not np.isnan(ind["V"][t]) and not np.isnan(ind["sigma"][t])]
        if len(S)<3: continue
        res=ratio_ci(ind,S,purge_from=sorted(set(T)|set(S)),nboot=1500)
        if res: rec["k"][str(k)]=dict(n=res["n"],blocks=res["blocks"],
                                      mult=round(res["mult"],3),lo=round(res["lo"],3),passed=bool(res["pass_"]))
    out.append(rec)
json.dump(out,open("placebo.json","w"),indent=1,ensure_ascii=False)

print(f"{'平移 k':>7}{'标的数':>7}{'倍数中位':>10}{'倍数四分位':>18}{'通过比例':>10}")
for k in KS:
    ms=[x["k"][str(k)]["mult"] for x in out if str(k) in x["k"]]
    ps=[x["k"][str(k)]["passed"] for x in out if str(k) in x["k"]]
    q1,q3=np.percentile(ms,[25,75])
    print(f"{k:>7}{len(ms):>7}{st.median(ms):>10.3f}   [{q1:.2f}, {q3:.2f}]{'':<6}{sum(ps)/len(ps)*100:>8.1f}%")
