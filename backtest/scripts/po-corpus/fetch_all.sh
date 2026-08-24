#!/bin/bash
# 逐账号拉满 2025-01-01 → 2026-08-20，自动续页直到 done。产出 data/handles/<handle>.tsv
set -u
D="/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/po-corpus"
SINCE=2025-01-01; UNTIL=2026-08-20
for h in "$@"; do
  out="$D/data/handles/$h.tsv"; : > "$out"
  off=0; done_flag=false; total=0
  for i in $(seq 1 12); do
    alva run --local-file "$D/scripts/fetch_handle.js" \
      --args "{\"handle\":\"$h\",\"since\":\"$SINCE\",\"until\":\"$UNTIL\",\"offset\":$off,\"pages\":60}" \
      --timeout-ms 600000 > "$D/raw/$h.$i.json" 2>&1
    read -r st n nx dn er < <(python3 - "$D/raw/$h.$i.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
r=d.get('result')
r=json.loads(r) if isinstance(r,str) else (r or {})
print(d.get('status'), r.get('n',0), r.get('next',0), r.get('done',False), str(r.get('err') or d.get('error'))[:60].replace(' ','_'))
PY
)
    if [ "$st" != "completed" ]; then echo "$h  FAIL $st $er"; break; fi
    python3 - "$D/raw/$h.$i.json" "$out" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); r=d['result']
r=json.loads(r) if isinstance(r,str) else r
t=r.get('tsv','')
if t: open(sys.argv[2],'a',encoding='utf-8').write(t+'\n')
PY
    total=$((total+n)); off=$nx
    if [ "$dn" = "True" ]; then done_flag=true; break; fi
  done
  echo "$h  n=$total done=$done_flag"
done
