import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, dedup
from match import m24, m24_hits
from collections import Counter
rows = dedup(load())
hits = [(r, m24_hits(r["text"])) for r in rows if m24(r["text"])]
print(f"M24 命中 {len(hits):,} / {len(rows):,} = {len(hits)/len(rows):.1%}\n")
print("## 独家触发词 —— 该词是这条帖子唯一的 M24 命中，删掉它这条就不再进 PO3\n")
sole = Counter(ps[0] for _, ps in hits if len(ps) == 1)
print(f"  {'独家条数':>8}{'占 M24':>8}   词")
for p, k in sole.most_common(20):
    print(f"  {k:>8,}{k/len(hits):>8.1%}   {p}")
print(f"\n  仅一个词触发的帖子共 {sum(sole.values()):,}（{sum(sole.values())/len(hits):.0%} of M24）")

print("\n## \\bwar\\b 的搭配（前 20）\n")
import re
rx = re.compile(r"(\w+\s+)?\bwar\b(\s+\w+)?", re.I)
c = Counter()
for r, ps in hits:
    for m in rx.finditer(r["text"]):
        c[" ".join(m.group(0).lower().split())] += 1
for p, k in c.most_common(20): print(f"  {k:>6}  {p}")

print("\n## Hormuz / 伊朗冲突的集中度\n")
h = [r for r, ps in hits if any("Hormuz" in p for p in ps)]
print(f"  Hormuz 类命中 {len(h):,}（占 M24 {len(h)/len(hits):.1%}）")
mc = Counter(r["ts"][:7] for r in h)
for m in sorted(mc): print(f"    {m}  {mc[m]:>5}")

print("\n## sanctions? 的独家命中样例（判噪声用）\n")
s = [r for r, ps in hits if ps == [r"sanctions?"]]
random.seed(7)
for r in random.sample(s, min(8, len(s))): print(f"  @{r['handle']:16} {r['text'][:150]}")

print("\n## M24 命中率随时间（同一词表，语料换了就变）\n")
from collections import defaultdict
mm = defaultdict(lambda: [0, 0, 0])
for r in rows:
    k = r["ts"][:7]; mm[k][0] += 1
for r, ps in hits:
    k = r["ts"][:7]; mm[k][1] += 1
    if not any("Hormuz" in p or p == r"\bwar\b" for p in ps): mm[k][2] += 1
print(f"  {'月':9}{'条数':>7}{'M24':>8}{'去掉 war/Hormuz 后':>20}")
for k in sorted(mm):
    n, h, h2 = mm[k]
    print(f"  {k:9}{n:>7,}{h/n:>8.1%}{h2/n:>20.1%}")
tot = sum(v[0] for v in mm.values()); th = sum(v[1] for v in mm.values()); th2 = sum(v[2] for v in mm.values())
print(f"  {'合计':9}{tot:>7,}{th/tot:>8.1%}{th2/tot:>20.1%}")
