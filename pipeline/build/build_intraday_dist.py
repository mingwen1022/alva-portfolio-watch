# -*- coding: utf-8 -*-
"""盘中幅度分位。分位必须取同一时刻（data-pipeline §九），全天混排会被开收盘那两根压制。

⚠️ 全部槽位都落盘。原来只落「今天触发过的那几个」，理由是「96 个全存等于 95 个白存」——
   那句话在**本地一次性构建**时成立，在**运行期**不成立：
   哪个槽位会触发，要到触发那一刻才知道。
   实测后果：SOL 在 00:30 触发，而落盘的只有 09:00，
   卡上「这个幅度算大吗」整块变成「本次运行没有这个时刻的基线」。
"""
import statistics as st, json, collections, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from asof import asof_cut
from book import US, CR, POS, CASH, NAME, LOGO   # ⚠️ 账本单一来源，见 book.py
CLS={**{s:"us" for s in US},**{s:"cr" for s in CR}}
RTH=("13:30","20:00"); BINS=24; MIN_N=30
CUT=asof_cut()          # 与 build_pv5.py 同一刀，见 asof.py

def load(s):
    cls=CLS[s]; rows=[]
    for l in open(f'pipeline/raw/iv_{s}.csv'):
        l=l.strip()
        if not l: continue
        t,c,v=l.split(",")
        if t >= CUT: continue
        if cls=="us" and not (RTH[0]<=t[11:16]<RTH[1]): continue
        rows.append((t,float(c),float(v)))
    rows.sort()
    return [(rows[i][0], rows[i][1]/rows[i-1][1]-1) for i in range(1,len(rows))
            if not (cls=="us" and rows[i][0][:10]!=rows[i-1][0][:10])]

def hist(v):
    lo,hi=min(v),max(v); w=(hi-lo)/BINS or 1e-9
    c=[0]*BINS
    for x in v: c[min(BINS-1,int((x-lo)/w))]+=1
    return {"from":round(lo,6),"binWidth":round(w,6),"counts":c}

F='mock/data/findings.json'; fj=json.load(open(F))
pv5=[f for f in fj['findings'] if f['signalId']=='PV5']

# ⚠️ **全部槽位都算**，不只今天触发过的那几个。
#    原来的注释是「96 个全存等于 95 个白存」—— 那句话在**本地一次性构建**时成立，
#    在**运行期**不成立：哪个槽位会触发，要到触发那一刻才知道。
#    实测后果：SOL 在 00:30 触发，而落盘的槽位里只有 09:00，
#    卡上「这个幅度算大吗」整块变成「本次运行没有这个时刻的基线」。
#    存全量的代价是每只标的多几十个直方图，读一次就够，比缺一个便宜得多。
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import US as _US, CR as _CR
need = {sym: None for sym in _US + _CR}      # None = 该标的的全部槽位

B='mock/data/baselines.json'; bl=json.load(open(B))
for s,slots in need.items():
    r=load(s); by=collections.defaultdict(list); by_t={}
    for t,x in r: by[t[11:16]].append(x); by_t[t]=x
    d={}
    for slot in sorted(slots if slots is not None else by.keys()):
        v=by.get(slot) or []
        if len(v)<MIN_N: continue      # 样本不足的槽位直接不落盘，界面据此说「暂无」
        a=sorted(abs(x) for x in v)
        # ⚠️ `top` 是该槽位**绝对幅度最大的 20 根**，降序。
        #    运行期的盘中 producer 靠它算 sizeRank —— 它手里只有当天的 bar，
        #    没有这个槽位的历史总体。存全量是 每标的 96 槽 × 135 根，太大；
        #    而排名只在很靠前时才有意义（「135 根里第 1」），
        #    掉出前 20 就说「不在这个时刻的前 20」——那是真话，也够用。
        d[slot]={"n":len(v),"p50":round(a[len(a)//2],5),"p95":round(a[int(len(a)*.95)],5),
                 "top":[round(x,5) for x in sorted(a, reverse=True)[:20]],
                 "histogram":hist(v)}
    bl[s].setdefault('distribution',{})
    bl[s]['distributionBar']={"unit":"15min","tz":"UTC","slots":d}
    # sizeRank：同一时刻、同方向
    for f in pv5:
        if f['symbol']!=s: continue
        slot=f['trigger']['barSlot']; v=by.get(slot) or []
        if len(v)<MIN_N: f['context']['sizeRank']=None; continue
        # ⚠️ 用总体里的原值,不用 measured.move —— 后者已四舍五入到 5 位,
        #    跟总体比时那根 bar 自己会掉出去,rank 变 0。rank 至少是 1
        mv=by_t.get(f['triggeredAt'][:16])
        if mv is None: f['context']['sizeRank']=None; continue
        rank=sum(1 for x in v if x<=mv) if mv<0 else sum(1 for x in v if x>=mv)
        assert rank>=1, f"{s} {slot} rank={rank} 这根 bar 不在自己的总体里"
        f['context']['sizeRank']={"rank":rank,"of":len(v),"unit":"bars"}   # slot 不重复存,取 trigger.barSlot
        print(f"{s} {slot}  move {mv:+.4%}  第 {rank} / {len(v)} 根同一时刻")

json.dump(bl,open(B,'w'),ensure_ascii=False,indent=1)
json.dump(fj,open(F,'w'),ensure_ascii=False,indent=1)
print('baselines 字节', len(json.dumps(bl)))
