"""EV3 的前瞻波动能否被「当天本来就是大波动日」解释掉
逐触发日配对：该日 |z| 最接近的 40 个非触发日作各自基准，取比值的中位数"""
import csv,random,statistics as st
from datetime import date
from ev35_rerun import build,align,blocks,analyst_triggers,SYMS,B,SEED,DAILY

def zseries(s):
    p={}
    for x in csv.reader(open(f"{DAILY}/{s}.csv")):
        if len(x)>=3: p[date.fromisoformat(x[0])]=float(x[1])
    ds=sorted(p); ret={ds[i]:p[ds[i]]/p[ds[i-1]]-1 for i in range(1,len(ds))}
    Z={}
    for i in range(91,len(ds)):
        w=[ret[ds[j]] for j in range(i-90,i) if ds[j] in ret]
        if len(w)<60 or ds[i] not in ret: continue
        m=st.median(w); sg=1.4826*st.median([abs(x-m) for x in w])
        if sg>0: Z[ds[i]]=abs(ret[ds[i]]-m)/sg
    return Z

K=40
print(f"逐触发日配对：取当日 |z| 最接近的 {K} 个非触发日作该次的基准，倍数 = 比值的中位数")
print(f"{'标的':<7}{'触发':>5}{'触发日|z|中位':>13}{'原倍数':>9}{'配对倍数':>10}{'配对95%区间':>18}{'判定':>8}")
res={}
for s in SYMS:
    V,ds=build(s); Z=zseries(s)
    raw,_,_=analyst_triggers(s,3,True,True); trig=align(raw,ds); T=set(trig)
    tv=[d for d in trig if d in V and d in Z]
    if len(tv)<3: print(f"{s:<7}{len(tv):>5}   样本不足"); continue
    ctrl=[(Z[x],V[x]) for x in V if x not in T and x in Z]
    base_all=st.median([v for _,v in ctrl])
    ratio={}
    for d in tv:
        near=sorted(ctrl,key=lambda p:abs(p[0]-Z[d]))[:K]
        b=st.median([v for _,v in near])
        ratio[d]=V[d]/b if b>0 else None
    tv=[d for d in tv if ratio.get(d)]
    bs=blocks(tv); random.seed(SEED); rs=[]
    for _ in range(B):
        fl=[ratio[x] for _ in range(len(bs)) for x in random.choice(bs)]
        rs.append(st.median(fl))
    rs.sort(); lo,hi=rs[int(.025*B)],rs[int(.975*B)]
    m=st.median([ratio[d] for d in tv])
    print(f"{s:<7}{len(tv):>5}{st.median([Z[d] for d in tv]):>13.2f}"
          f"{st.median([V[d] for d in tv])/base_all:>9.2f}{m:>10.2f}"
          f"{('[%.2f, %.2f]'%(lo,hi)):>18}{('🟡通过' if lo>1 else '未通过'):>8}")
    res[s]=(m,lo,hi)
