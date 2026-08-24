# ⑤ 误命中抽查：从 M24 命中条目里随机抽 N 条，人工判读用。固定种子可复现。
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, dedup
from match import m24, m24_hits, m17

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260819
rows = dedup(load())
hits = [r for r in rows if m24(r["text"])]
random.seed(SEED)
smp = random.sample(hits, N)
smp.sort(key=lambda r: r["ts"])
print(f"# M24 命中 {len(hits):,} 条，随机抽 {N} 条（seed={SEED}）\n")
for i, r in enumerate(smp, 1):
    print(f"[{i:02d}] {r['ts'][:16]}  @{r['handle']}  {r['ctype']}  M17={'Y' if m17(r['text']) else 'N'}")
    print(f"     词: {', '.join(m24_hits(r['text']))}")
    print(f"     {r['text'][:330]}")
    print()
