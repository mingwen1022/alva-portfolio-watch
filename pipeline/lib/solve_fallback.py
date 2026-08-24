# -*- coding: utf-8 -*-
"""未验证资产类别的兜底反解。规格见 signal-spec §「未验证的资产类别 · 兜底规则」。

池级扫 θv ∈ [1.0, 6.0]（步长 0.25），选使「池级触发日占比」最接近锚 4.16% 的值。
⚠️ 两侧必须同口径：锚是池级的，候选也按池级算，不能拿逐标的中位去比。
"""
import json, statistics as st
ANCHOR=0.0416; THETA_Z=1.5; W=90
RAW=json.load(open('pipeline/raw/outpool.json'))

def rob(v):
    m=st.median(v); return m, 1.4826*st.median([abs(x-m) for x in v])

series={}
for s,txt in RAW.items():
    rows=sorted((l.split(',')[0], float(l.split(',')[1]), float(l.split(',')[2]))
                for l in txt.strip().split('\n') if l)
    series[s]=rows

# 逐标的预算 z 与 rvol，一次算完，之后只换 θv 门
pre={}
for s,rows in series.items():
    c=[r[1] for r in rows]; v=[r[2] for r in rows]; n=len(c)
    ret=[None]+[c[i]/c[i-1]-1 for i in range(1,n)]
    z=[None]*n; rv=[None]*n
    for i in range(W+1,n):
        m,sg=rob([x for x in ret[i-W:i] if x is not None])
        vm=st.median(v[i-W:i])
        if sg>0: z[i]=(ret[i]-m)/sg
        if vm>0: rv[i]=v[i]/vm
    pre[s]=(z,rv,n)

print(f"池 {len(pre)} 只 ETF · 每只 {min(x[2] for x in pre.values())}–{max(x[2] for x in pre.values())} 根\n")
print(f"{'θv':>5s} {'池级触发日占比':>12s} {'与锚之差':>10s}")
best=None
for k in range(4,25):
    tv=k*0.25
    hit=tot=0
    for s,(z,rv,n) in pre.items():
        for i in range(W+1,n):
            if z[i] is None or rv[i] is None: continue
            tot+=1
            if abs(z[i])>=THETA_Z and rv[i]>=tv: hit+=1
    share=hit/tot
    d=abs(share-ANCHOR)
    mark=''
    if best is None or d<best[2]: best=(tv,share,d); mark=' ←'
    if k%2==0 or d<0.005: print(f"{tv:5.2f} {share:12.2%} {share-ANCHOR:+10.2%}{mark}")
print(f"\n反解结果 θz = {THETA_Z} · θv = {best[0]}  池级触发日占比 {best[1]:.2%}（锚 {ANCHOR:.2%}）")
json.dump({"assetClass":"other","poolSize":len(pre),"theta_z":THETA_Z,"theta_v":best[0],
           "poolShare":round(best[1],5),"anchor":ANCHOR,"members":sorted(pre)},
          open('pipeline/raw/fallback_solved.json','w'), ensure_ascii=False)
