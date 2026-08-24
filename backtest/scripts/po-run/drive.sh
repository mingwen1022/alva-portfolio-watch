#!/bin/zsh
# 并行驱动 alva run。用法：drive.sh <jobdir> <outdir> <并行度>
# 已有非空输出的 job 跳过（可中断续跑）。每个 run 的 stats.credits_used 记进 logs/credits.tsv
set -u
JOBDIR=${1:?}; OUT=${2:?}; PAR=${3:-6}
BASE=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$OUT" "$BASE/logs"
run_one() {
  local f=$1
  local n=$(basename "$f" .js)
  local o="$OUT/$n.json"
  if [[ -s "$o" ]]; then return 0; fi
  alva run --local-file "$f" --timeout-ms 900000 > "$o.tmp" 2> "$BASE/logs/$n.err"
  if [[ -s "$o.tmp" ]]; then mv "$o.tmp" "$o"; else rm -f "$o.tmp"; fi
  echo "done $n $(date +%H:%M:%S)" >> "$BASE/logs/drive.log"
}
i=0
for f in "$JOBDIR"/run_*.js; do
  run_one "$f" &
  i=$((i+1))
  if (( i % PAR == 0 )); then wait; fi
done
wait
echo "ALL DONE $(date +%H:%M:%S)" >> "$BASE/logs/drive.log"
