"""R28 两处修正各自的量级（只算点估计，不跑自助）：
E 原始V+不分层+不净化 → D 加净化 → A 再加十分位分层（= 定稿）
另给 F 旧口径（V=RV5/σ_rob，不分层不净化）作对照。"""
import numpy as np, statistics as st
from universe_load import roster, prep
from pv_engine import pv1_trigger, PURGE, NDEC
rows=[]
for r in roster():
    ind=prep(r); V,sig=ind["V"],ind["sigma"]; n=ind["n"]
    valid=np.flatnonzero((~np.isnan(V))&(~np.isnan(sig)))
    T=np.array([t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(V[t])])
    if len(T)<10: continue
    Ts=set(T.tolist()); N=np.array([i for i in valid if i not in Ts])
    sv=sig[valid]; qs=np.quantile(sv,np.linspace(0,1,NDEC+1)[1:-1])
    dec=np.searchsorted(qs,sig,side="right")
    purge=np.zeros(n,bool)
    for t in T: purge[max(0,t-PURGE):min(n,t+PURGE+1)]=True
    P=valid[~purge[valid]]
    E=np.median(V[T])/np.median(V[N])
    D=np.median(V[T])/np.median(V[P])
    pools=[P[dec[P]==d] for d in range(NDEC)]
    base=np.array([np.median(V[p]) if len(p)>=10 else np.median(V[P]) for p in pools])
    A=np.median(V[T]/base[dec[T]])
    Vo=V/sig; F=np.median(Vo[T])/np.median(Vo[N])
    rows.append((ind["sym"],E,D,A,F))
for i,nm in [(1,"E 不分层不净化"),(2,"D 只加净化"),(3,"A 定稿 净化+十分位"),(4,"F 旧口径 V÷σ")]:
    v=[r[i] for r in rows]; print(f"{nm:<20}中位 {st.median(v):.3f}  四分位 [{np.percentile(v,25):.2f}, {np.percentile(v,75):.2f}]")
dp=[r[2]-r[1] for r in rows]; ds=[r[3]-r[2] for r in rows]; df=[r[3]-r[4] for r in rows]
print(f"\n净化的效应（D−E）中位 {st.median(dp):+.3f}，正向占 {sum(1 for x in dp if x>0)}/{len(dp)}")
print(f"十分位分层的效应（A−D）中位 {st.median(ds):+.3f}，正向占 {sum(1 for x in ds if x>0)}/{len(ds)}")
print(f"定稿 vs 旧口径（A−F）中位 {st.median(df):+.3f}，正向占 {sum(1 for x in df if x>0)}/{len(df)}")
