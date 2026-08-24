import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, dedup, TIER
from match import m17, m24, m24_hits, M24_BY_GROUP
from collections import Counter

rows_raw = load()
rows = dedup(rows_raw)
for r in rows:
    r["a"] = m17(r["text"]); r["b"] = m24(r["text"])

def quad(v):
    n = len(v)
    if not n: return None
    a = sum(1 for r in v if r["a"]); b = sum(1 for r in v if r["b"])
    both = sum(1 for r in v if r["a"] and r["b"])
    return dict(n=n, m17=a, m24=b, both=both, only17=a-both, only24=b-both,
                neither=n-a-b+both, union=a+b-both)

HDR = (f"{'':26}{'条数':>8}{'M17':>8}{'M24':>8}{'都命中':>8}{'仅M17':>8}{'仅M24':>8}{'都不中':>8}"
       f"{'并集':>8}{'并集条数':>9}")
def line(name, q, w=26):
    if not q: print(f"{name:{w}}{'—':>8}"); return
    n = q["n"]
    print(f"{name:{w}}{n:>8,}{q['m17']/n:>8.1%}{q['m24']/n:>8.1%}{q['both']/n:>8.1%}"
          f"{q['only17']/n:>8.1%}{q['only24']/n:>8.1%}{q['neither']/n:>8.1%}{q['union']/n:>8.1%}{q['union']:>9,}")

print("=" * 108)
print(f"无偏语料 {len(rows_raw):,} 条 → 跨账号去重后 {len(rows):,} 条（重复 {1-len(rows)/len(rows_raw):.1%}，主要是转推链）")
print("=" * 108)
print("\n## ① 四格总表\n"); print(HDR)
line("全部 29 账号", quad(rows))
for t in TIER: line("  " + t, quad([r for r in rows if r["tier"] == t]))
print()
line("密集窗 2026-05→08 全部", quad([r for r in rows if r["ts"] >= "2026-05-01"]))
line("  其中 官方政策机构", quad([r for r in rows if r["ts"] >= "2026-05-01" and r["tier"] == "官方政策机构"]))
print()
for ct in ["original", "quote", "reply", "retweet"]:
    line(f"仅 {ct}", quad([r for r in rows if r["ctype"] == ct]))

print("\n## ② 与有偏语料的对照\n")
bias = []
for f in glob.glob("/Users/ming/project/alva/backtest/data/social/*.tsv"):
    for l in open(f, encoding="utf-8"):
        p = l.rstrip("\n").split("\t")
        if len(p) >= 3 and p[2].strip(): bias.append({"text": p[2]})
for r in bias: r["a"] = m17(r["text"]); r["b"] = m24(r["text"])
print(HDR)
line("有偏（关键词检索）", quad(bias))
line("无偏 全部账号", quad(rows))
line("无偏 官方政策机构", quad([r for r in rows if r["tier"] == "官方政策机构"]))

print("\n## ③ 按账号\n"); print(HDR)
for t, hs in TIER.items():
    for h in hs: line(h, quad([r for r in rows if r["handle"] == h]))

print("\n## ④ M24 触发词频次（去重语料）\n")
c = Counter(p for r in rows if r["b"] for p in m24_hits(r["text"]))
tot = sum(c.values())
for p, k in c.most_common(30): print(f"  {k:>7,}  {k/len(rows):>6.2%}   {p}")
print(f"\n  从未命中的词：")
never = [p for _, p in [(rx, p) for v in M24_BY_GROUP.values() for rx, p in v] if p not in c]
print("   ", " · ".join(never) if never else "（无）")

print("\n## ⑤ M24 三组\n")
for g, pats in M24_BY_GROUP.items():
    hit = sum(1 for r in rows if any(rx.search(r["text"]) for rx, _ in pats))
    print(f"  {g:12}{hit:>8,}{hit/len(rows):>8.1%}")

print("\n## ⑥ LLM 调用量估算（M18 只跑 M17∪M24 通过的条目，官方蓝图 15 条一批）\n")
def est(name, v):
    q = quad(v)
    if not q: return
    u = q["union"]; b = -(-u // 15)
    print(f"  {name:30}{q['n']:>9,}{u:>9,}{u/q['n']:>8.1%}{b:>9,}")
print(f"  {'范围':30}{'总条数':>9}{'粗筛通过':>9}{'通过率':>8}{'LLM 批次':>9}")
est("全部 29 账号 · 20 个月", rows)
est("官方政策机构 · 20 个月", [r for r in rows if r["tier"] == "官方政策机构"])
est("官方政策机构 · 密集窗 3.7 月", [r for r in rows if r["tier"] == "官方政策机构" and r["ts"] >= "2026-05-01"])
est("全部 · 密集窗 3.7 月", [r for r in rows if r["ts"] >= "2026-05-01"])
est("官方+当事人+央行 · 20 月", [r for r in rows if r["tier"] != "财经媒体与快讯"])
