#!/usr/bin/env python3
"""Deterministic replacement per universe-rules.md section 8."""
import json,os,sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0,'scripts')
from validate import check
cells=json.load(open('raw/cells_us.json'))
rows=json.load(open('raw/selection_us.json'))
log=json.load(open('raw/replace_log.json')) if os.path.exists('raw/replace_log.json') else []
# rebuild recent-ipo candidate ordering
R=json.loads(json.load(open('raw/screen.json'))['result'])['out']
S=json.loads(json.load(open('raw/sectors.json'))['result'])
IPO=json.loads(json.load(open('raw/ipo.json'))['result'])['rows']
sector={}
for k in sorted(S.keys()):
    for s in S[k]: sector.setdefault(s,k)
col=lambda k:{a:b for a,b in R[k]}
mcap=col('mcap26');addv=col('addv');ma20=col('ma20');vol90=col('vol90');beta=col('beta');mcap18=col('mcap18')
ipo={}
for s,v in IPO:
    if s not in ipo or v<ipo[s]: ipo[s]=v
pref=lambda s: s in mcap and s in addv and s in ma20 and addv[s]>=5e6 and ma20[s]>=3 and mcap[s]>=300e6
tier=lambda m:'large' if m>=10e9 else ('mid' if m>=2e9 else 'small')
core_syms={r['symbol'] for r in rows if r['stratum'].startswith('core')}
ipo_cand=[s for s in sector if s not in core_syms and pref(s) and '2023-08-19'<=ipo.get(s,'')<'2026-08-19']
ipo_cand.sort(key=lambda s:(-addv[s],s))

need=[]
taken={r['symbol'] for r in rows}
for r in rows:
    mb=120 if r['stratum']=='recent_ipo' else 250
    ok,msg=check(r['symbol'],mb)
    if ok: continue
    if r['stratum'].startswith('core'):
        c=cells[f"{r['sector']}|{r['size_tier']}"]
        order=list(range(r['cell_idx']+1,len(c)))+list(range(r['cell_idx']-1,-1,-1))
        cands=[c[i] for i in order if c[i] not in taken]
    else:
        i=ipo_cand.index(r['symbol']) if r['symbol'] in ipo_cand else -1
        cands=[s for s in ipo_cand if s not in taken]
    # try candidates whose data we already have; otherwise emit fetch request
    picked=None
    for s in cands:
        ok2,msg2=check(s,mb)
        if ok2: picked=s; break
        if not os.path.exists(f'data/daily/{s}.csv'):
            need.append(s)
            if len(need)>=30: break
    if picked:
        log.append(dict(out=r['symbol'],reason=msg,into=picked,stratum=r['stratum'],
                        sector=r.get('sector'),size_tier=r.get('size_tier')))
        taken.discard(r['symbol']); taken.add(picked)
        r['symbol']=picked; r['mcap']=mcap.get(picked); r['mcap18']=mcap18.get(picked)
        r['addv']=addv.get(picked); r['vol90']=vol90.get(picked); r['beta']=beta.get(picked)
        r['ipo']=ipo.get(picked,''); r['sector']=sector.get(picked,r.get('sector'))
        if r['stratum'].startswith('core'):
            r['cell_idx']=cells[f"{r['sector']}|{r['size_tier']}"].index(picked)
        r['replaced']=True
if need:
    print('NEED_FETCH '+','.join(dict.fromkeys(need)))
else:
    json.dump(rows,open('raw/selection_us.json','w'),indent=1)
    json.dump(log,open('raw/replace_log.json','w'),indent=1)
    print('DONE replacements:',len(log))
    for l in log: print('  ',l['out'],'->',l['into'],'(',l['reason'],')')
