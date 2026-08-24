# -*- coding: utf-8 -*-
"""PV5 盘中 15 分钟 + SPY 基准。σ_rob 与量中位按「同一时刻」取，见 signal-spec PV5。"""
import json, statistics as st, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from asof import asof_cut
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import US, CR, POS, CASH, NAME, LOGO   # ⚠️ 账本单一来源，见 book.py
CLS={**{s:"us_equity" for s in US}, **{s:"crypto" for s in CR}}
TZ={"us_equity":4.75,"crypto":10.0}
TV={"us_equity":2.0,"crypto":3.0}     # signal-spec PV5：加密量能腿是 3.0，不是 2.0
SLOTW=90        # 同一时刻回看多少天
HISTD=502

RTH=("13:30","20:00")   # 9:30–16:00 ET，UTC 表示。美股 PV5 只算盘中
CUT=asof_cut()          # 晚于本轮 asOf 的 bar 一律不算，见 asof.py

def load(s, rth):
    rows=[]
    for l in open(f'pipeline/raw/iv_{s}.csv'):
        t,c,v=l.strip().split(",")
        if t >= CUT: continue                    # ⚠️ 加密没有收盘，这一刀只能自己下
        if rth and not (RTH[0] <= t[11:16] < RTH[1]): continue
        rows.append((t,float(c),float(v)))
    rows.sort(); return rows

def robust(v):
    m=st.median(v); return m, 1.4826*st.median([abs(x-m) for x in v])

out={}
for s in US+CR:
    cls=CLS[s]; tz=TZ[cls]; tv=TV[cls]; b=load(s, cls=='us_equity')
    # 第四项是这根 bar 自己的收盘价。⚠️ 不能用「索引 +1 回查 b」——
    #    美股那一支会按日界过滤掉跨日的那一根，两个列表的下标从那里起就错开了。
    r=[(b[i][0], b[i][1]/b[i-1][1]-1, b[i][2], b[i][1]) for i in range(1,len(b))
       if not (cls=='us_equity' and b[i][0][:10]!=b[i-1][0][:10])]
    slots={}
    for i,(t,ret,vol,_c) in enumerate(r): slots.setdefault(t[11:16],[]).append(i)
    z=[None]*len(r); rv=[None]*len(r)
    for slot,idxs in slots.items():
        for k,i in enumerate(idxs):
            if k<30: continue                     # 同时刻样本不足 30 天不算
            prev=idxs[max(0,k-SLOTW):k]
            m,sg = robust([r[j][1] for j in prev])
            if sg<=0: continue
            z[i]=(r[i][1]-m)/sg
            vm=st.median([r[j][2] for j in prev])
            if vm>0: rv[i]=r[i][2]/vm
    fired=[(r[i][0], round(z[i],2), round(rv[i],2))
           for i in range(len(r)) if z[i] is not None and rv[i] is not None
           and abs(z[i])>=tz and rv[i]>=tv]
    days=sorted({x[0][:10] for x in fired})
    lastday=r[-1][0][:10]
    todaybars=[i for i in range(len(r)) if r[i][0][:10]==lastday and z[i] is not None]
    # ⚠️ 当日触发的**每一根**都要留。只留最强那根会丢掉方向相反的早盘根 ——
    #    实测 DOGE 当日三根：09:00 z=−14.62（向下）· 20:30 +11.15 · 21:30 +18.63，
    #    只留 21:30 之后卡片指向上，而当天第一次触发是向下的。
    #    signal-spec §5.3.1：日内 findings 累积不替换。
    todayFired=[i for i in todaybars if rv[i] is not None and abs(z[i])>=tz and rv[i]>=tv]
    strongest=max(todaybars,key=lambda i:abs(z[i])) if todaybars else None
    # 线 = θz × 该时刻的稳健波动（取最强那根所在时刻）
    line=None
    if strongest is not None:
        sl=r[strongest][0][11:16]; idxs=slots[sl]; k=idxs.index(strongest)
        _,sg=robust([r[j][1] for j in idxs[max(0,k-SLOTW):k]])
        line=tz*sg
    last7=[d for d in days if d>=sorted({x[0][:10] for x in r})[-8]]
    # ── 逐槽位基线 ──
    # ⚠️ 盘中的线是**同一时刻**算出来的：09:45 那根的线来自过去 90 天所有 09:45。
    #    这份数据此前只活在本脚本的内存里，没有落进契约 —— 于是运行时的盘中
    #    producer 每一轮都得重拉 135 天分钟线才能重建它，那是错的架构：
    #    基线属于初始化，运行期只该取当天。
    #    取每个槽位**最近一次**可算的窗口作为该槽位的现行基线。
    slotBase={}
    for slot,idxs in slots.items():
        k=len(idxs)-1
        if k < 30: continue                      # 同时刻样本不足 30 天不出读数
        prev=idxs[max(0,k-SLOTW):k]
        m,sg = robust([r[j][1] for j in prev])
        vm = st.median([r[j][2] for j in prev])
        if sg<=0 or vm<=0: continue
        slotBase[slot]={"med":round(m,8),"sigma":round(sg,8),
                        "vmed":round(vm,4),"n":len(prev)}
    out[s]={"bars":len(r),"tz":tz,"tv":tv,
            "slotBaselines":slotBase,
            "todayBars":len(todaybars),
            "todayZ":round(z[strongest],2) if strongest is not None else None,
            "todayRvol":round(rv[strongest],2) if strongest is not None and rv[strongest] else None,
            "todaySlot":r[strongest][0][11:16] if strongest is not None else None,
            "line":round(line,5) if line else None,
            "firedToday":bool(todayFired),
            "todayFiredBars":[{"slot":r[i][0][11:16],"t":r[i][0],
                               "z":round(z[i],2),"rvol":round(rv[i],2),
                               "move":round(r[i][1],5),
                               # 这根 bar 的收盘价。日线卡印的是当日收盘，
                               # 盘中卡此前什么都不印 —— 不是设计，是契约里没有这个数。
                               "close":r[i][3],
                               "line":round(tz*robust([r[j][1] for j in
                                     slots[r[i][0][11:16]][max(0,slots[r[i][0][11:16]].index(i)-SLOTW):
                                                            slots[r[i][0][11:16]].index(i)]])[1],5)}
                              for i in sorted(todayFired,key=lambda i:r[i][0])],
            "triggerDays":len(days),"last7Days":len(last7),
            "history":[{"d":d,"signalId":"PV5"} for d in days][-60:],
            # ⚠️ 逐日明细也从这里出，别再从另一个文件取。
            #    原来条数出自本文件、明细出自 `pv5_full.json` —— 而后者读的是
            #    `/tmp/full_*.csv`，那些文件早没了，于是它变成一个**重跑不出来的冻结产物**。
            #    加两只新标的时立刻暴露：条数写了 7 条，明细一条没有。
            #    `build_all.py` 的说明里写着「补丁不在这里 = 下次重跑就没了」，就是这个。
            "byDay":{d:[{"slot":x[0][11:16],"z":x[1],"rvol":x[2]}
                        for x in fired if x[0][:10]==d] for d in days}}
json.dump(out,open('pipeline/raw/pv5.json','w'))
print(f"{'标的':6s} {'bar 数':>7s} {'θz':>5s} {'当日最强 z':>10s} {'该根量比':>8s} {'时刻':>6s} {'盘中线':>8s} {'今日':>5s} {'两年天数':>8s} {'近7':>4s}")
for s in US+CR:
    o=out[s]
    ln = f"{o['line']*100:.2f}%" if o['line'] else "—"
    print(f"{s:6s} {o['bars']:7d} {o['tz']:5.2f} {str(o['todayZ']):>10s} {str(o['todayRvol']):>8s} "
          f"{str(o['todaySlot']):>6s} {ln:>8s} "
          f"{'✅' if o['firedToday'] else '—':>5s} {o['triggerDays']:8d} {o['last7Days']:4d}")
