#!/bin/bash
set -u
R=/private/tmp/claude-501/-Users-ming-project-alva/067235b0-b646-4219-bb6d-dbb602425bdf/scratchpad/evrun
cd "$R"
LIST=$1; TAG=$2; BS=${3:-6}
mkdir -p data/congress raw/cong_json
ALL=($(cat "$LIST")); n=${#ALL[@]}
for ((i=0;i<n;i+=BS)); do
  batch=$(printf "%s," "${ALL[@]:i:BS}" | sed 's/,$//')
  alva run --local-file scripts/fetch_congress_batch.js --args "{\"symbols\":\"$batch\"}" --timeout-ms 900000 > "raw/cong_json/${TAG}_$i.json" 2>&1
  python3 - "raw/cong_json/${TAG}_$i.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
if j.get('error'): print('RUNERR',str(j['error'])[:200]); sys.exit()
r=json.loads(j['result'])
for s,v in r.items():
    lines=[l for l in v['csv'].split('\n') if l.strip()]
    lines.sort()
    open(f'data/congress/{s}.csv','w').write('transaction_date|filing_date|name|transaction_type|amounts|issuer|member_type|party|observed_at\n'+'\n'.join(lines)+('\n' if lines else ''))
    print(f"  {s} n={v['n']} raw={v['raw']} capped={v['capped']} err={v['err']}")
PY
done
echo "DONE $TAG"
