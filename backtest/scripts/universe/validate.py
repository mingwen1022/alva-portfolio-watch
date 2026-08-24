#!/usr/bin/env python3
import json,os,csv,math
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def load(sym,d='data/daily'):
    p=f'{d}/{sym}.csv'
    if not os.path.exists(p): return None
    rows=list(csv.DictReader(open(p)))
    return rows
def check(sym, minbars, d='data/daily'):
    r=load(sym,d)
    if not r: return False,'missing'
    n=len(r)
    if n<minbars: return False,f'bars={n}<{minbars}'
    if r[-1]['date']<'2026-08-01': return False,f'last={r[-1]["date"]}'
    z=sum(1 for x in r if float(x['volume'] or 0)<=0)
    if z/n>0.05: return False,f'zerovol={z/n:.1%}'
    return True,f'bars={n}'
if __name__=='__main__':
    rows=json.load(open('raw/selection_us.json'))
    for r in rows:
        mb=120 if r['stratum']=='recent_ipo' else 250
        ok,msg=check(r['symbol'],mb)
        if not ok: print('FAIL',r['symbol'],r['stratum'],r.get('sector'),r.get('size_tier'),r.get('cell_idx'),msg)
