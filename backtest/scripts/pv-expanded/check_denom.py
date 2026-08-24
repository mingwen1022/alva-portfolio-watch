"""共用分母偏误的核查：触发日是否机械选中 σ_rob 偏低的日子，以及十分位分层是否消掉它。
R28 在 NVDA 上实测全局比 0.844、分层后 0.98–1.03。"""
import numpy as np, statistics as st
from universe_load import roster, prep
from pv_engine import pv1_trigger, NDEC
g=[]; inner=[]
for r in roster():
    ind=prep(r); V,sig=ind["V"],ind["sigma"]
    valid=np.flatnonzero((~np.isnan(V))&(~np.isnan(sig)))
    T=np.array([t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(V[t])])
    if len(T)<10: continue
    ratio=float(np.median(sig[T])/np.median(sig[valid])); g.append((ind["sym"],ratio))
    sv=sig[valid]; qs=np.quantile(sv,np.linspace(0,1,NDEC+1)[1:-1])
    dec=np.searchsorted(qs,sig,side="right")
    for d in range(NDEC):
        a=[t for t in T if dec[t]==d]; b=[i for i in valid if dec[i]==d]
        if len(a)>=5: inner.append(float(np.median(sig[a])/np.median(sig[b])))
rs=[x[1] for x in g]
print(f"触发日 σ_rob 中位 ÷ 全体 σ_rob 中位（{len(g)} 只）：中位 {st.median(rs):.3f}  "
      f"四分位 [{np.percentile(rs,25):.3f}, {np.percentile(rs,75):.3f}]  范围 [{min(rs):.3f}, {max(rs):.3f}]")
print(f"  低于 1.0 的标的 {sum(1 for x in rs if x<1)}/{len(rs)}")
print(f"层内（十分位内）同一比值：中位 {st.median(inner):.3f}  四分位 "
      f"[{np.percentile(inner,25):.3f}, {np.percentile(inner,75):.3f}]  n={len(inner)}")
print("\n偏离最大的六只：", " · ".join(f"{s} {v:.3f}" for s,v in sorted(g,key=lambda x:x[1])[:6]))
