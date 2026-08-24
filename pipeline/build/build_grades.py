# -*- coding: utf-8 -*-
"""逐标的投递上限 signalGrades。契约见 output-schema §六。

⚠️ 必须用全历史，不能截到 502 根 —— 换窗口结论会翻。
"""
import json, statistics as st, random, math
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import US, CR, OT, POS, CASH, NAME, LOGO   # ⚠️ 账本单一来源，见 book.py
# ⚠️ 「其他」也要判。投递上限问的是「这条规则在这只票上验过没有」——
#    阈值是不是兜底解出来的，与这个问题无关，两者是各自独立的一道门。
#    θv 必须取它自己那一档：拿美股的 2.0 去跑 ETF，等于在判一条它运行时不会用的规则。
_FB = json.load(open('pipeline/raw/fallback_solved.json'))
THETA_Z=1.5; TV={"us":2.0,"cr":3.0,"ot":_FB["theta_v"]}; FWD=5; W=90
# ⚠️ B 从 2000 提到 20000，且**每只标的独立播种**。两处都是必须的：
#
#   顺序依赖    原来全程共用一条随机流，于是每只票的抽样都取决于它前面处理了哪些票。
#               实测把 RIVN/SOFI 挪到队首，**TSLA 的区间下界从 1.011 掉到 0.970** ——
#               TSLA 本身一个数没变，只是别人插了队，它的告警就从推手机降成只留页面。
#               「往账本里加一只无关的持仓」不该改变另一只票的投递档位。
#
#   蒙特卡洛噪声  B=2000 时 TSLA 的下界在 10 个种子间落在 0.9702–1.0153，
#               **跨着 1.0**，20% 的种子会把它判成 L2 —— 那个档位是随机数定的，不是数据定的。
#               B=20000 时 10 个种子全部给出 1.0115，噪声消失。
#               判据卡在 1.0 这条硬线上，抽样噪声就必须远小于它到 1.0 的距离。
B=20000; SEED=7

def rob(v):
    m=st.median(v); return m, 1.4826*st.median([abs(x-m) for x in v])

# 全历史。daily.json 只有近三年（端点 limit=1000 截断），
# 而契约明确要求全历史 —— 换窗口结论会翻，实测 802 根 vs 全历史有三只标的档位不同。
RAW=json.load(open('pipeline/raw/daily_full.json'))
def load(s):
    rows=[]
    for l in RAW[s].strip().split("\n"):
        p=l.split(",")
        rows.append((p[0], float(p[1]), float(p[2])))
    rows.sort()                      # 端点返回按时间倒序
    return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]

def boot_ci(x):
    if len(x)<2: return [None,None]
    r=random.Random(SEED)          # 每次调用一条新流 —— 结果与标的顺序无关
    md=sorted(st.median(r.choices(x,k=len(x))) for _ in range(B))
    return [round(md[int(.025*B)],3), round(md[int(.975*B)],3)]

out={}
for s in US+CR+OT:
    cls="us" if s in US else ("cr" if s in CR else "ot"); tv=TV[cls]
    d,c,v=load(s); n=len(c)
    ret=[None]+[c[i]/c[i-1]-1 for i in range(1,n)]
    fired=[]
    for i in range(W+1,n-FWD):
        m,sg=rob([x for x in ret[i-W:i] if x is not None])
        if sg<=0: continue
        vm=st.median(v[i-W:i])
        if vm<=0: continue
        if abs((ret[i]-m)/sg)>=THETA_Z and v[i]/vm>=tv: fired.append(i)
    # 触发后 5 日已实现波动 ÷ 平时同长窗口
    base=[]
    for i in range(W+1,n-FWD):
        w=[ret[j] for j in range(i+1,i+1+FWD) if ret[j] is not None]
        if len(w)==FWD: base.append((i, st.pstdev(w)))
    bmap=dict(base); typ=st.median([x for _,x in base]) if base else 0
    mult=[bmap[i]/typ for i in fired if i in bmap and typ>0]
    # 独立块：相邻触发间隔 < 前瞻窗长算同一块
    blocks=0; prev=-99
    for i in fired:
        if i-prev>=FWD: blocks+=1
        prev=i
    ci=boot_ci(mult)
    if ci[0] is not None and ci[0]>1.0 and blocks>=5: md,vd="L1","usable"
    elif blocks<5:                                     md,vd="L2","insufficient_sample"
    else:                                              md,vd="L2","effect_unclear"
    out[s]={"PV1":{"maxDelivery":md,"verdict":vd,
                   "multiple":round(st.median(mult),3) if mult else None,
                   "ci":ci,"blocks":blocks,"days":n}}
    print(f"{s:6s} 全历史 {n:5d} 根 · 触发 {len(fired):4d} 日 · 块 {blocks:3d} · "
          f"倍数 {out[s]['PV1']['multiple']} · 区间 {ci} → {md} {vd}")

# ── PV5 也要评级 ─────────────────────────────────────────────────────────
# ⚠️ **此前只算 PV1。** 后果不是「少一个字段」——`deliveryOf` 里
#    `const g = gr ? gr.maxDelivery : "L2"`，**缺失直接封 L2**。
#    于是 acct1 那本 demo 上**每一条盘中告警都不推手机**，而页面上看不出来:
#    行徽标当时只读 PV1，只有恰好触发的那一条卡片会露出 no push。
#    skill 自己的 `init.js` 是算的（`L.grade(bc, bv, firedBar, …)`），
#    两边不一致就是两把尺子 —— 照它的结构补齐。
#
# ⚠️ 判据与 PV1 **完全同一套**（区间下界 > 1.0 且独立块 ≥ 5），只是跑在 bar 上:
#    W / F 的单位从「天」变成「根」，阈值换成 θ_bar，触发要查同槽位基线。
TZ_BAR={"us":4.75,"cr":10.0}; TV_BAR={"us":2.0,"cr":3.0}
RTH_=("13:30","20:00")
SLOTW_=90

def _iv(sym, rth):
    fp=f'pipeline/raw/iv_{sym}.csv'
    if not os.path.exists(fp): return None
    rows=[]
    for l in open(fp):
        t,c,v=l.strip().split(",")
        if rth and not (RTH_[0] <= t[11:16] < RTH_[1]): continue
        rows.append((t,float(c),float(v)))
    rows.sort(); return rows

def _slot_base(rows):
    """逐槽位基线，取每槽最近 SLOTW_ 个样本 —— 与 init.js 的 slice(-90) 同口径。"""
    slots={}
    for i in range(1,len(rows)):
        if rows[i][0][:10]!=rows[i-1][0][:10]: continue   # 不跨日算收益（美股）
        slots.setdefault(rows[i][0][11:16],[]).append(i)
    base={}
    for k,idxs in slots.items():
        prev=idxs[-SLOTW_:]
        if len(prev)<30: continue
        rr=[rows[j][1]/rows[j-1][1]-1 for j in prev]
        m,sg=rob(rr); vm=st.median([rows[j][2] for j in prev])
        if sg>0 and vm>0: base[k]={"med":m,"sigma":sg,"vmed":vm}
    return base

pv5_out={}; pv5_missing=[]
for s in US+CR+OT:
    cls="us" if s in US else ("cr" if s in CR else "ot")
    if cls=="ot":                       # ETF 不启用 PV5，没有评级是**正确的缺席**
        continue
    rows=_iv(s, cls=="us")
    if not rows: pv5_missing.append(s); continue
    sb=_slot_base(rows)
    if not sb: pv5_missing.append(s); continue
    tz, tv2 = TZ_BAR[cls], TV_BAR[cls]
    n=len(rows); c=[r[1] for r in rows]
    ret=[None]+[c[i]/c[i-1]-1 for i in range(1,n)]
    def fired_bar(t):
        if t<1 or rows[t][0][:10]!=rows[t-1][0][:10]: return False
        b=sb.get(rows[t][0][11:16])
        if not b or ret[t] is None: return False
        return abs((ret[t]-b["med"])/b["sigma"])>=tz and rows[t][2]/b["vmed"]>=tv2
    lo, hi = W+1, n-FWD
    if hi-lo < FWD*5: pv5_missing.append(s); continue
    A=[]
    for t in range(lo,hi):
        w=[ret[j] for j in range(t+1,t+1+FWD) if ret[j] is not None]
        if len(w)==FWD: A.append((t, st.pstdev(w)))
    typ=st.median([a for _,a in A]) if A else 0
    if not typ>0: pv5_missing.append(s); continue
    T=[t for t,_ in A if fired_bar(t)]; amap=dict(A)
    m5=[amap[t]/typ for t in T]
    blk=0; prev=-10**9
    for t in T:
        if t-prev>=FWD: blk+=1
        prev=t
    if len(m5)<2:
        pv5_out[s]={"maxDelivery":"L2","verdict":"insufficient_sample",
                    "multiple":round(m5[0],3) if m5 else None,"ci":None,"blocks":len(m5),"days":n}
    else:
        ci5=boot_ci(m5)
        if ci5[0] is not None and ci5[0]>1.0 and blk>=5: md5,vd5="L1","usable"
        elif blk<5:                                       md5,vd5="L2","insufficient_sample"
        else:                                             md5,vd5="L2","effect_unclear"
        pv5_out[s]={"maxDelivery":md5,"verdict":vd5,"multiple":round(st.median(m5),3),
                    "ci":ci5,"blocks":blk,"days":n}
    g=pv5_out[s]
    print(f"{s:6s} PV5 {n:6d} 根 · 触发 {len(T):4d} 根 · 块 {g['blocks']:3d} · "
          f"倍数 {g['multiple']} · 区间 {g['ci']} → {g['maxDelivery']} {g['verdict']}")

if pv5_missing:
    # ⚠️ 「算不出」和「不适用」要分开说。ETF 是后者，上面直接 continue，不进这个名单。
    print(f"⚠️ PV5 评级算不出（分钟线缺失或样本不足）: {pv5_missing}")

B_='mock/data/baselines.json'; bl=json.load(open(B_))
for s,g in out.items(): bl[s]["signalGrades"]=g
for s,g in pv5_out.items(): bl[s].setdefault("signalGrades",{})["PV5"]=g
json.dump(bl,open(B_,'w'),ensure_ascii=False,indent=1)
