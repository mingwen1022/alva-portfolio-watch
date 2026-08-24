"""自检第 2 步：用旧口径（V=RV5/σ_rob · 基准=全体非触发 · 不净化 · 基准不重抽）
复现 plan.md §一 那张已审核的表。目标 XOM 2.70 [1.53,4.87] · SOFI 1.15 [0.90,1.40] 未通过。"""
import numpy as np, json
from pv_engine import load_legacy, indicators, pv1_trigger, blocks_of
REF={"XOM":(2.70,1.53,4.87),"AAPL":(1.97,1.29,3.28),"MSFT":(1.86,1.53,3.61),"NVDA":(1.68,1.40,2.41),
     "MSTR":(1.48,1.27,1.85),"AMD":(1.31,1.11,1.49),"KO":(1.30,1.01,5.83),"PLTR":(1.27,1.12,1.42),
     "RIVN":(1.25,1.06,1.52),"TSLA":(1.21,1.05,1.60),"SOFI":(1.15,0.90,1.40)}
NB,SEED=4000,20260819
out=[]
print(f"{'标的':<6}{'触发':>5}{'块':>4}{'倍数':>7}{'参考':>7}  {'95% 区间':<15}{'参考区间':<15}{'判定':<6}{'参考判定'}")
for s,(rm,rl,rh) in REF.items():
    ds,c,v=load_legacy(s); ind=indicators(c,v,252)
    Vo=ind["V"]/ind["sigma"]
    T=[t for t in pv1_trigger(ind,1.5,2.0) if not np.isnan(Vo[t]) and t>=91]
    valid=np.flatnonzero(~np.isnan(Vo)); Ts=set(T)
    N=[i for i in valid if i not in Ts]
    base=float(np.median(Vo[N])); pt=float(np.median(Vo[T])/base)
    bl=blocks_of(np.array(T)); rng=np.random.default_rng(SEED); nb=len(bl)
    blV=[Vo[b] for b in bl]; reps=np.empty(NB)
    for b in range(NB):
        pick=rng.integers(0,nb,nb); reps[b]=np.median(np.concatenate([blV[j] for j in pick]))/base
    reps.sort(); lo=float(reps[int(.025*NB)]); hi=float(reps[int(.975*NB)])
    ok=lo>1.0 and nb>=5
    print(f"{s:<6}{len(T):>5}{nb:>4}{pt:>7.2f}{rm:>7.2f}  [{lo:.2f}, {hi:.2f}]{'':<3}[{rl:.2f}, {rh:.2f}]{'':<3}"
          f"{'🟢通过' if ok else '❌未通过':<6}{'🟢通过' if rl>1 else '❌未通过'}")
    out.append(dict(sym=s,n=len(T),blocks=nb,mult=pt,lo=lo,hi=hi,ref_mult=rm,ref_lo=rl,ref_hi=rh))
json.dump(out,open("selfcheck_old.json","w"),indent=1,ensure_ascii=False)
