#!/bin/bash
set -u
U=/private/tmp/claude-501/-Users-ming-project-alva/fd26b124-a1b6-42be-87b6-65b93ca6cc8d/scratchpad/universe
cd "$U"; FILE=$1; BS=${2:-4}
mkdir -p data/crypto raw/deriv_json
ALL=($(cat "$FILE")); n=${#ALL[@]}
for ((i=0;i<n;i+=BS)); do
  batch=$(printf "%s," "${ALL[@]:i:BS}" | sed 's/,$//')
  alva run --local-file scripts/fetch_deriv.js --args "{\"symbols\":\"$batch\"}" --timeout-ms 900000 > "raw/deriv_json/d_$i.json" 2>&1
  python3 - "raw/deriv_json/d_$i.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
if j.get('error'): print('RUNERR',str(j['error'])[:200]); sys.exit()
r=json.loads(j['result'])
for s,v in r.items():
    f,o=v['fund'],v['oi']
    open(f'data/crypto/{s}_funding.csv','w').write('time,funding_rate\n'+f['csv']+('\n' if f['csv'] else ''))
    open(f'data/crypto/{s}_oi.csv','w').write('time,sum_open_interest,sum_open_interest_value\n'+o['csv']+('\n' if o['csv'] else ''))
    print(f"  {s} funding={f['n']} [{f['first']}..{f['last']}] p{f['pages']}{' ERR '+str(f['err']) if f['err'] else ''} | oi={o['n']} [{o['first']}..{o['last']}] p{o['pages']}{' ERR '+str(o['err']) if o['err'] else ''}")
PY
done
