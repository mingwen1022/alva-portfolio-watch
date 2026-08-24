#!/usr/bin/env python3
"""Mechanical US equity selection per universe-rules.md sections 3-4."""
import json, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

S   = json.loads(json.load(open('raw/sectors.json'))['result'])
R   = json.loads(json.load(open('raw/screen.json'))['result'])['out']
IPO = json.loads(json.load(open('raw/ipo.json'))['result'])['rows']

SECTORS = sorted(S.keys())                       # enumeration order = alpha
sector = {}
for k in SECTORS:
    for s in S[k]:
        sector.setdefault(s, k)                  # first sector wins

col   = lambda k: {a: b for a, b in R[k]}
mcap  = col('mcap26'); mcap18 = col('mcap18')
addv  = col('addv');   ma20   = col('ma20'); vol90 = col('vol90'); beta = col('beta')

ipo = {}
for s, v in IPO:
    if s not in ipo or v < ipo[s]:
        ipo[s] = v

def prefilter(s):
    if s not in mcap or s not in addv or s not in ma20: return False
    return addv[s] >= 5e6 and ma20[s] >= 3 and mcap[s] >= 300e6

def tier(m):
    return 'large' if m >= 10e9 else ('mid' if m >= 2e9 else 'small')

cells = {}
for k in SECTORS:
    for t in ('large', 'mid', 'small'):
        c = [s for s in S[k] if sector[s] == k and prefilter(s) and tier(mcap[s]) == t]
        c.sort(key=lambda s: (-mcap[s], s))
        cells[(k, t)] = c

picked, rows = set(), []
for k in SECTORS:
    for t in ('large', 'mid', 'small'):
        c = cells[(k, t)]; n = len(c)
        idxs = sorted(set([round(0.25*(n-1)), round(0.75*(n-1))]))
        for i in idxs:
            s = c[i]
            picked.add(s)
            rows.append(dict(symbol=s, stratum='core', sector=k, size_tier=t,
                             cell_n=n, cell_idx=i, mcap=mcap[s], mcap18=mcap18.get(s),
                             addv=addv[s], vol90=vol90.get(s), beta=beta.get(s),
                             ipo=ipo.get(s, '')))

# recent IPO stratum
cutoff = '2023-08-19'
cand = [s for s in sector
        if s not in picked and prefilter(s) and ipo.get(s, '') >= cutoff and ipo.get(s, '') < '2026-08-19']
cand.sort(key=lambda s: (-addv[s], s))
for s in cand[:8]:
    picked.add(s)
    rows.append(dict(symbol=s, stratum='recent_ipo', sector=sector[s], size_tier=tier(mcap[s]),
                     cell_n=len(cand), cell_idx=cand.index(s), mcap=mcap[s], mcap18=mcap18.get(s),
                     addv=addv[s], vol90=vol90.get(s), beta=beta.get(s), ipo=ipo.get(s, '')))

LEGACY = ['AAPL','MSFT','NVDA','TSLA','AMD','PLTR','RIVN','SOFI','KO','XOM','MSTR']
for s in LEGACY:
    if s in picked:
        for r in rows:
            if r['symbol'] == s: r['stratum'] += '+legacy'
        continue
    picked.add(s)
    rows.append(dict(symbol=s, stratum='legacy', sector=sector.get(s,''),
                     size_tier=tier(mcap[s]) if s in mcap else '', cell_n='', cell_idx='',
                     mcap=mcap.get(s), mcap18=mcap18.get(s), addv=addv.get(s),
                     vol90=vol90.get(s), beta=beta.get(s), ipo=ipo.get(s,'')))
rows.append(dict(symbol='SPY', stratum='benchmark', sector='', size_tier='', cell_n='', cell_idx='',
                 mcap=None, mcap18=None, addv=None, vol90=None, beta=None, ipo=ipo.get('SPY','')))

json.dump(rows, open('raw/selection_us.json','w'), indent=1)
json.dump({f'{k}|{t}': v for (k,t), v in cells.items()}, open('raw/cells_us.json','w'))
print('total', len(rows), ' core', sum(1 for r in rows if r['stratum'].startswith('core')),
      ' recent_ipo', sum(1 for r in rows if r['stratum']=='recent_ipo'),
      ' legacy', sum(1 for r in rows if 'legacy' in r['stratum']))
print('undersized cells:', [f'{k}|{t}:{len(v)}' for (k,t),v in cells.items() if len(v)<2])
print('recent_ipo picks:', [(r['symbol'], r['ipo'], r['sector']) for r in rows if r['stratum']=='recent_ipo'])
