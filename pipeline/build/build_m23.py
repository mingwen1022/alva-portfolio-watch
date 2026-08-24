# -*- coding: utf-8 -*-
"""M23 分布可用性检验（决策 #10）。

稳健标准差里的 1.4826 是按正态校准的。分布形状偏离正态时 z_rob 的量纲就变了 ——
均匀分布下 max|z| = 1.35 < 1.5，PV1 永远不会触发，而且是静默的。
ρ = P(|z_rob| ≥ 1.5)，近 2 年滚动窗。有效样本 < 250 日 → ρ = None，走 PV4 覆盖标注。
"""
import json, statistics as st
W=90; HIST=504; MIN_N=250; THETA_Z=1.5
LO, HI = 0.02, 0.40      # 处置分档的两条界
# ⚠️ 上界是 0.40，不是 0.60。判据来源是 registry PV1 降级规则 ②「ρ > 40% → Warning」。
#    这个数曾在五处写成两个值（spec 40 · 本文件 60 · output-schema 40 与 60 各一处 ·
#    页面印给用户 60），而**可执行的这一份用的是宽的那个**。
#    实测 ρ 最高 20.2%，两条界都碰不到，所以谁也没发现 —— 换一只高 ρ 标的就会
#    把本该降 Warning 的判成 pass，也就是把本该留在页面上的推到手机。

def rob(v):
    m=st.median(v); return m, 1.4826*st.median([abs(x-m) for x in v])

RAW=json.load(open('pipeline/raw/daily_full.json'))
B='mock/data/baselines.json'; bl=json.load(open(B))
print(f"{'标的':6s} {'有效样本':>7s} {'ρ':>8s} {'判定'}")
for s in bl:
    rows=sorted((l.split(',')[0],float(l.split(',')[1])) for l in RAW[s].strip().split('\n') if l)
    c=[r[1] for r in rows][-(HIST+W+1):]
    n=len(c); ret=[None]+[c[i]/c[i-1]-1 for i in range(1,n)]
    zs=[]
    for i in range(W+1,n):
        m,sg=rob([x for x in ret[i-W:i] if x is not None])
        if sg>0: zs.append(abs((ret[i]-m)/sg))
    if len(zs)<MIN_N:
        bl[s]['m23']={"rho":None,"verdict":"insufficient_sample","n":len(zs)}
        print(f"{s:6s} {len(zs):7d} {'—':>8s} 样本不足 → PV4 覆盖标注"); continue
    rho=sum(1 for x in zs if x>=THETA_Z)/len(zs)
    v = "pass" if LO<=rho<=HI else ("too_tight" if rho<LO else "too_loose")
    bl[s]['m23']={"rho":round(rho,4),"verdict":v,"n":len(zs)}
    note={"pass":"通过","too_tight":"⚠️ 分布过窄，固定阈值几乎不可能触发",
          "too_loose":"⚠️ 分布过宽，阈值形同虚设"}[v]
    print(f"{s:6s} {len(zs):7d} {rho:8.2%} {note}")
json.dump(bl,open(B,'w'),ensure_ascii=False,indent=1)
