#!/bin/bash
set -u
U=/private/tmp/claude-501/-Users-ming-project-alva/fd26b124-a1b6-42be-87b6-65b93ca6cc8d/scratchpad/universe
cd "$U"; FILE=$1; BS=${2:-6}
mkdir -p data/insider data/analyst raw/ins_json
ALL=($(cat "$FILE")); n=${#ALL[@]}
for ((i=0;i<n;i+=BS)); do
  batch=$(printf "%s," "${ALL[@]:i:BS}" | sed 's/,$//')
  alva run --local-file scripts/fetch_ins_an.js --args "{\"symbols\":\"$batch\"}" --timeout-ms 900000 > "raw/ins_json/b_$i.json" 2>&1
  python3 - "raw/ins_json/b_$i.json" <<'PY'
import json,sys,os
j=json.load(open(sys.argv[1]))
if j.get('error'): print('RUNERR',str(j['error'])[:200]); sys.exit()
r=json.loads(j['result'])
for s,v in r.items():
    open(f'data/insider/{s}.csv','w').write('transaction_date|filing_date|transaction_code|is_10b51|is_officer|is_director|owner_name|security_title|shares|price|shares_owned_after\n'+v['ins']+('\n' if v['ins'] else ''))
    open(f'data/analyst/{s}.csv','w').write('publish_time|analyst_company|analyst_name|price_target|adj_price_target|price_when_posted|publisher|title\n'+v['an']+('\n' if v['an'] else ''))
    m=v['meta']; flag=' TRUNC' if (m['ins_trunc'] or m['an_trunc']) else ''
    err=(' ERR '+str(m['ins_err']+m['an_err'])) if (m['ins_err'] or m['an_err']) else ''
    print(f"  {s} insider={v['n_ins']} analyst={v['n_an']}{flag}{err}")
PY
done
