import gzip, json, collections
D="/Users/ming/project/alva/backtest/data/"
conf={r['cid']:r for r in json.load(gzip.open(D+'po-derived/confirm.json.gz'))}
lab={r['id']:r for r in json.load(gzip.open(D+'po-labels/m18_l5fixed.json.gz'))}
cand={r['cid']:r for r in json.load(gzip.open(D+'po-derived/candidates.json.gz'))}
cids=list(conf)
def rate(sel, port):
    got=[c for c in cids if sel(c) and conf[c][port]]
    if not got: return None,0
    return sum(1 for c in got if conf[c][port]['c'])/len(got), len(got)
# try several filters to find baselines 14.5% / 26.6%
filters={
 'all': lambda c: True,
 'passL5': lambda c: lab[c]['verdict']=='pass',
 'tierA': lambda c: conf[c]['layer'] in ('main18','cb4'),
 'tierA_pass': lambda c: conf[c]['layer'] in ('main18','cb4') and lab[c]['verdict']=='pass',
 'main18': lambda c: conf[c]['layer']=='main18',
 'media7': lambda c: conf[c]['layer']=='media7',
}
for n,f in filters.items():
    row=[]
    for p in ('P_semi','P_defensive','P_crypto'):
        r,k=rate(f,p); row.append(f"{p} {('%.1f%%'%(100*r)) if r is not None else '--'} n={k}")
    print(f"{n:14}", ' | '.join(row))
