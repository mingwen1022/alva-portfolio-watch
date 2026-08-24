import math, statistics as st, random, glob, os, json
random.seed(20260821)

def load(p):
    rows=[l.split(',') for l in open(p).read().strip().split('\n')]
    return [(r[0], float(r[1]), float(r[2])) for r in rows]

def prep(d):
    """returns list of dicts with date, r, vol, z, rvol, V(fwd5), sigma_decile"""
    n=len(d); out=[]
    r=[None]+[math.log(d[i][1]/d[i-1][1]) for i in range(1,n)]
    for i in range(n):
        if i<91 or i+5>=n: out.append(None); continue
        win=r[i-90:i]
        med=st.median(win); mad=st.median([abs(x-med) for x in win]); sig=1.4826*mad
        if sig<=0: out.append(None); continue
        z=(r[i]-med)/sig
        vwin=[d[j][2] for j in range(i-90,i)]
        vmed=st.median(vwin)
        rv=d[i][2]/vmed if vmed>0 else 0
        fwd=[r[i+k] for k in range(1,6)]
        V=math.sqrt(sum(x*x for x in fwd)/5)
        out.append({'i':i,'d':d[i][0],'z':z,'rvol':rv,'V':V,'sig':sig})
    return [x for x in out if x]

def blocks(idx):
    """count independent blocks: consecutive-ish triggers within 5 days merge"""
    if not idx: return 0
    idx=sorted(idx); b=1
    for a,c in zip(idx,idx[1:]):
        if c-a>5: b+=1
    return b

def ratio_ci(trig, base, B=2000):
    """median(V_trig)/median(V_base), 95% CI by block bootstrap on triggers"""
    if len(trig)<3 or len(base)<20: return None,None,None
    mb=st.median(base)
    pt=st.median(trig)/mb
    lo=[]
    for _ in range(B):
        s=[random.choice(trig) for _ in trig]
        lo.append(st.median(s)/mb)
    lo.sort()
    return pt, lo[int(0.025*B)], lo[int(0.975*B)]

THZ=1.5
GRID=[1.5,2.0,2.5,3.0,3.5,4.0]
files=sorted(glob.glob('cry/*.csv'))
res={g:{'pass':0,'eval':0,'mults':[],'trig':[]} for g in GRID}

for f in files:
    sym=os.path.basename(f)[:-4]
    p=prep(load(f))
    if len(p)<250: continue
    # sigma deciles for baseline matching
    sigs=sorted(x['sig'] for x in p)
    def dec(s):
        k=sum(1 for q in sigs if q<s)
        return min(9,int(10*k/len(sigs)))
    for x in p: x['dec']=dec(x['sig'])
    for thv in GRID:
        trig=[x for x in p if abs(x['z'])>=THZ and x['rvol']>=thv]
        if not trig: continue
        ti={x['i'] for x in trig}
        # purge +-5 around any trigger
        purged=set()
        for i in ti: purged.update(range(i-5,i+6))
        decs={x['dec'] for x in trig}
        base=[x['V'] for x in p if x['i'] not in purged and x['dec'] in decs]
        pt,lo,hi=ratio_ci([x['V'] for x in trig], base)
        if pt is None: continue
        nb=blocks(list(ti))
        res[thv]['eval']+=1
        res[thv]['trig'].append(len(trig))
        if lo is not None and lo>1.0 and nb>=5:
            res[thv]['pass']+=1; res[thv]['mults'].append(pt)

print(f"加密 θv 复核 · θz={THZ} · 25 个币 · 判据：相对基准倍数 95% 下界 > 1.0 且 独立块 ≥ 5\n")
print(f"{'θv':>5}{'可评估':>7}{'通过':>6}{'通过率':>8}{'倍数中位':>10}{'触发中位/币':>12}")
print("─"*50)
for g in GRID:
    r=res[g]
    if r['eval']==0: print(f"{g:>5}      —"); continue
    mm=st.median(r['mults']) if r['mults'] else float('nan')
    tt=st.median(r['trig']) if r['trig'] else 0
    print(f"{g:>5}{r['eval']:>7}{r['pass']:>6}{r['pass']/r['eval']*100:>7.0f}%{mm:>10.3f}{tt:>12.0f}")
