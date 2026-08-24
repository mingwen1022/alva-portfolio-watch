import gzip, json, collections
D="/Users/ming/project/alva/backtest/data/"
conf={r['cid']:r for r in json.load(gzip.open(D+'po-derived/confirm.json.gz'))}
lab={r['id']:r for r in json.load(gzip.open(D+'po-labels/m18_l5fixed.json.gz'))}
cids=list(conf)
ETS=['export-control','monetary','tariff','geopolitical','regulation','personnel','other']
for port in ('P_semi','P_defensive','P_crypto'):
    got=[c for c in cids if conf[c][port]]
    base=sum(1 for c in got if conf[c][port]['c'])/len(got)
    print(f"\n{port} base={base:.3%} n={len(got)}")
    for e in ETS:
        s=[c for c in got if lab[c]['event_type']==e]
        if not s: continue
        r=sum(1 for c in s if conf[c][port]['c'])/len(s)
        print(f"   {e:16} n={len(s):>5}  rate={r:6.1%}  lift={100*(r-base):+5.1f}pp")
# common subsample
common=[c for c in cids if conf[c]['P_semi'] and conf[c]['P_crypto'] and conf[c]['P_defensive']]
print(f"\n=== common subsample n={len(common)} ({len(common)/len(cids):.1%}) ===")
for port in ('P_semi','P_defensive','P_crypto'):
    base=sum(1 for c in common if conf[c][port]['c'])/len(common)
    print(f"{port} base={base:.3%}")
    for e in ETS:
        s=[c for c in common if lab[c]['event_type']==e]
        if not s: continue
        r=sum(1 for c in s if conf[c][port]['c'])/len(s)
        print(f"   {e:16} n={len(s):>5}  rate={r:6.1%}  lift={100*(r-base):+5.1f}pp")
