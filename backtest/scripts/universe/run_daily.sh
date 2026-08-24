#!/bin/bash
# usage: run_daily.sh <symbols-file> <kind> <outdir> <batchsize>
set -u
U=/private/tmp/claude-501/-Users-ming-project-alva/fd26b124-a1b6-42be-87b6-65b93ca6cc8d/scratchpad/universe
cd "$U"
FILE=$1; KIND=$2; OUT=$3; BS=${4:-8}
mkdir -p "$OUT" raw/daily_json
mapfile -t ALL < "$FILE" 2>/dev/null || ALL=($(cat "$FILE"))
n=${#ALL[@]}
for ((i=0;i<n;i+=BS)); do
  batch=$(printf "%s," "${ALL[@]:i:BS}" | sed 's/,$//')
  echo "[$((i/BS+1))] $batch"
  alva run --local-file scripts/fetch_daily.js --args "{\"symbols\":\"$batch\",\"kind\":\"$KIND\"}" --timeout-ms 600000 \
    > "raw/daily_json/${KIND}_$i.json" 2>&1
  python3 - "raw/daily_json/${KIND}_$i.json" "$OUT" <<'PY'
import json,sys,os
p,out=sys.argv[1],sys.argv[2]
j=json.load(open(p))
if j.get('error'): print('  RUNERR',str(j['error'])[:200]); sys.exit()
r=json.loads(j['result'])
for s,v in r.items():
    if isinstance(v,dict) and 'csv' in v:
        open(os.path.join(out,s+'.csv'),'w').write('date,open,high,low,close,volume\n'+v['csv']+'\n')
        print(f'  {s} {v["n"]}')
    else:
        print(f'  {s} FAIL {v}')
PY
done
