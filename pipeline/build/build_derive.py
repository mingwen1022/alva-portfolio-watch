# -*- coding: utf-8 -*-
"""派生字段：novelty · priority · delivery · benchmark · assetClass · sizeRank.unit。

这些原本是一次性补丁,于是 build.py 一重跑就没了 —— 收成正式阶段。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..')  # build/ → 仓库根
SEV={'critical':3,'warning':2,'info':1}
ORD={'L1':1,'L2':2,'L3':3,'L4':4}
CLS={'NVDA':'us_equity','TSLA':'us_equity','AMD':'us_equity','MSTR':'us_equity',
     'SOUN':'us_equity','BTC':'crypto','SOL':'crypto','DOGE':'crypto'}

def run(book, spy_move=None):
    D=os.path.join(ROOT, book)
    F=f'{D}/findings.json'; fj=json.load(open(F))
    port=json.load(open(f'{D}/portfolio.json'))
    bl=json.load(open(f'{D}/baselines.json'))
    sg=json.load(open(os.path.join(ROOT,'mock/data/signals.json')))['signals']
    st=json.load(open(f'{D}/state.json'))['keys'] if os.path.exists(f'{D}/state.json') else {}
    W={h['symbol']:h['weight'] for h in port['holdings']}
    H={h['symbol']:h for h in port['holdings']}
    today=fj['asOf'][:10]
    for f in fj['findings']:
        s=f['symbol']; sid=f['signalId']
        f['assetClass']=CLS.get(s, f.get('assetClass') or 'other')
        f['trigger'].setdefault('barSlot', None)
        f['trigger'].setdefault('thresholdSource', bl.get(s,{}).get('thresholds',{}).get('source','validated'))
        c=f['context']
        # novelty：状态型持续成立记 0（已经推过了）；其余首次 1.0
        e=st.get(f'{s}:{sid}')
        f['novelty']=0.0 if (e and e.get('since') and e['since'][:10]<today) else 1.0
        f['priority']=round(SEV[f['severity']]*W.get(s,1.0)*f['novelty'],4)
        # benchmark：一种形状，只差 applicable 与三个值是否 null
        b=c.get('benchmark') or {}
        if f['assetClass']=='us_equity' and spy_move is not None:
            c['benchmark']={"symbol":"SPY","benchmarkMove":spy_move,
                            "symbolMove":f['measured'].get('move'),"applicable":True}
        else:
            c['benchmark']={"symbol":None,"benchmarkMove":None,"symbolMove":None,"applicable":False}
        # pnl：④ 那块直接读它，不让界面 join
        h=H.get(s)
        c['pnl']=({"today":round(h['value']-h['value']/(1+h['todayPct']),2) if h.get('todayPct') else None,
                   "shares":h.get('shares'),"lifetime":h.get('lifetimePnl')} if h else None)
        sr=c.get('sizeRank')
        if isinstance(sr,dict): sr.setdefault('unit','bars' if f['unit']=='bar' else 'sessions')
        # delivery：三处上限取最严，并记下是谁压的
        # ⚠️ US 从不降级（signal-spec §US「US 从不降级」）——
        #    degraded 说的是**我们**那套阈值的历史不够硬，而用户线一个字都没借它：
        #    US1/US2 是用户填的价位，US3 量的是这只票自己的高点。
        #    照压的后果是把用户亲手设的止损线拦在手机之外，而高波正是他设它的理由。
        # ⚠️ degraded 的上限是 L2，不是 L3。spec 说的是「不推手机」，
        #    而 L3 是持仓页 —— 那等于连告警流都不进，比「不推手机」多砍一层。
        deg = bl.get(s,{}).get('degraded') and not sid.startswith('US')
        caps={'signal_evidence':(sg.get(sid) or {}).get('maxDelivery'),
              'symbol_grade':((bl.get(s,{}).get('signalGrades') or {}).get(sid) or {}).get('maxDelivery'),
              'degraded':'L2' if deg else None}
        real=[(w,l) for w,l in caps.items() if l]
        if real:
            w,l=max(real,key=lambda x:ORD[x[1]])
            base=(sg.get(sid) or {}).get('maxDelivery') or 'L1'
            f['delivery']={"level":l,"cappedBy":(None if (l==base and w=='signal_evidence') else w)}
        else:
            f['delivery']={"level":"L1","cappedBy":None}
    json.dump(fj,open(F,'w'),ensure_ascii=False,indent=1)
    print(f"{book}: {len(fj['findings'])} 条 · 被压 "
          f"{[(f['symbol'],f['signalId'],f['delivery']) for f in fj['findings'] if f['delivery']['cappedBy']]}")

if __name__=='__main__':
    spy=None
    p=os.path.join(ROOT,'pipeline/raw/spy.csv')
    if os.path.exists(p):
        rows=sorted(l.strip().split(',') for l in open(p) if l.strip())
        if len(rows)>=2: spy=round(float(rows[-1][1])/float(rows[-2][1])-1,5)
    run('mock/data', spy)
    if os.path.exists(os.path.join(ROOT,'mock/data-outpool/findings.json')): run('mock/data-outpool')
