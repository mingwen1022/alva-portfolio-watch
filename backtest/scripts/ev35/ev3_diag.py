"""EV3 触发点是不是「财报反应」的改名 —— 逐标的诊断"""
import csv,random,statistics as st
from datetime import date,timedelta
from ev35_rerun import build,align,blocks,evaluate,analyst_triggers,SYMS,B,SEED,DAILY

def rets(s):
    p={}
    for x in csv.reader(open(f"{DAILY}/{s}.csv")):
        if len(x)>=3: p[date.fromisoformat(x[0])]=float(x[1])
    ds=sorted(p); return {ds[i]:p[ds[i]]/p[ds[i-1]]-1 for i in range(1,len(ds))},ds

print("触发日与前一日的当日 |收益| 相对该标的常态（=1 表示与常态一致）")
print(f"{'标的':<7}{'触发':>5}{'触发日|r|':>10}{'前一日|r|':>10}{'季度节奏':>10}   触发日期（后 6 个）")
for s in SYMS:
    V,ds=build(s); R,_=rets(s)
    raw,_,_=analyst_triggers(s,3,True,True); trig=align(raw,ds)
    if len(trig)<3: print(f"{s:<7}{len(trig):>5}   样本不足"); continue
    di={d:i for i,d in enumerate(ds)}
    allr=st.median([abs(v) for v in R.values()])
    t0=[abs(R[d]) for d in trig if d in R]
    tm1=[abs(R[ds[di[d]-1]]) for d in trig if d in di and di[d]>0 and ds[di[d]-1] in R]
    gaps=[(trig[i+1]-trig[i]).days for i in range(len(trig)-1)]
    q=sum(1 for g in gaps if 80<=g<=100)/len(gaps) if gaps else 0
    print(f"{s:<7}{len(trig):>5}{st.median(t0)/allr:>10.2f}{st.median(tm1)/allr:>10.2f}{q*100:>9.0f}%   "
          + " ".join(str(d)[2:] for d in trig[-6:]))

print("\n安慰剂：把每只标的的触发日整体平移，看倍数（区间下界>1 标 ✓）")
print(f"{'标的':<7}" + "".join(f"{x:>16}" for x in ["−10 日","−5 日","0（实际）","+5 日","+10 日"]))
for s in SYMS:
    V,ds=build(s); raw,_,_=analyst_triggers(s,3,True,True); trig=align(raw,ds)
    di={d:i for i,d in enumerate(ds)}; row=f"{s:<7}"
    N=[v for d,v in V.items() if d not in set(trig)]
    if not N or len(trig)<3: print(f"{s:<7}   样本不足"); continue
    base=st.median(N)
    for sh in [-10,-5,0,5,10]:
        tv=[]
        for d in trig:
            i=di.get(d)
            if i is None: continue
            j=i+sh
            if 0<=j<len(ds) and ds[j] in V: tv.append(ds[j])
        if len(tv)<3: row+=f"{'—':>16}"; continue
        bs=blocks(tv); random.seed(SEED); rs=[]
        for _ in range(B):
            fl=[V[x] for _ in range(len(bs)) for x in random.choice(bs)]
            rs.append(st.median(fl)/base)
        rs.sort(); lo=rs[int(.025*B)]
        row+=f"{st.median([V[x] for x in tv])/base:>14.2f}{'✓' if lo>1 else ' '} "
    print(row)
