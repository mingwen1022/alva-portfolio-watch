"""样本切半复现性：结论是否依赖样本窗口（F 判据当年就是死在这一条上）。
切点 2022-06-30，两段各自独立算通过比例。"""
import json, numpy as np, math, statistics as st
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci

CUT="2022-06-30"
def wil(k,n,z=1.96):
    if n==0: return (0,0)
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0,c-h),min(1,c+h)
out=[]
for r in roster():
    ind=prep(r)
    T=[t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(ind["V"][t])]
    rec=dict(sym=ind["sym"],asset=ind["asset"],vol_tier=ind["vol_tier"],years=round(ind["years"],2),half={})
    d=np.array(ind["dates"])
    for lab,mask in [("前半 ≤2022-06",d<=CUT),("后半 >2022-06",d>CUT)]:
        sub=dict(ind); sub["V"]=np.where(mask,ind["V"],np.nan)
        Ts=[t for t in T if mask[t]]
        res=ratio_ci(sub,Ts,nboot=2000)
        if res: rec["half"][lab]=dict(n=res["n"],blocks=res["blocks"],mult=round(res["mult"],3),
                                      lo=round(res["lo"],3),passed=bool(res["pass_"]))
    out.append(rec)
json.dump(out,open("splithalf.json","w"),indent=1,ensure_ascii=False)
for lab in ["前半 ≤2022-06","后半 >2022-06"]:
    g=[x for x in out if lab in x["half"]]
    k=sum(1 for x in g if x["half"][lab]["passed"]); lo,hi=wil(k,len(g))
    print(f"{lab}：可评估 {len(g)} 只  通过 {k} = {k/len(g)*100:.0f}%  [{lo*100:.0f}%, {hi*100:.0f}%]  "
          f"倍数中位 {st.median(x['half'][lab]['mult'] for x in g):.2f}  触发中位 {st.median(x['half'][lab]['n'] for x in g):.0f}")
both=[x for x in out if len(x["half"])==2]
a=[x["half"]["前半 ≤2022-06"]["passed"] for x in both]; b=[x["half"]["后半 >2022-06"]["passed"] for x in both]
print(f"\n两段都可评估的 {len(both)} 只：两段都通过 {sum(1 for x,y in zip(a,b) if x and y)}  "
      f"只前半 {sum(1 for x,y in zip(a,b) if x and not y)}  只后半 {sum(1 for x,y in zip(a,b) if y and not x)}  "
      f"都不通过 {sum(1 for x,y in zip(a,b) if not x and not y)}")
from scipy import stats as sp
ma=[x["half"]["前半 ≤2022-06"]["mult"] for x in both]; mb=[x["half"]["后半 >2022-06"]["mult"] for x in both]
print(f"两段倍数的 Spearman：{sp.spearmanr(ma,mb).statistic:+.3f}  p={sp.spearmanr(ma,mb).pvalue:.4f}")
