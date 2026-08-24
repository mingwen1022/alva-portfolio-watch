import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, dedup, TIER
from match import m17, m24
rows = dedup(load())
for r in rows: r["u"] = m17(r["text"]) or m24(r["text"])

def rep(name, v, days):
    n = len(v); u = sum(1 for r in v if r["u"])
    if not n: return
    print(f"  {name:34}{n:>9,}{u:>9,}{u/n:>8.1%}{-(-u//15):>9,}{u/days:>10.1f}{-(-int(u/days)//15):>9}")

print(f"  {'范围':34}{'总条数':>9}{'粗筛通过':>9}{'通过率':>8}{'回测批次':>9}{'条/天':>10}{'线上批/天':>9}")
D20 = 596   # 2025-01-01 → 2026-08-20
D37 = 111   # 2026-05-01 → 2026-08-20
rep("全部 29 账号 · 20 个月", rows, D20)
rep("官方政策机构 12 账号 · 20 个月", [r for r in rows if r["tier"] == "官方政策机构"], D20)
rep("官方+当事人+央行 22 账号 · 20 月", [r for r in rows if r["tier"] != "财经媒体与快讯"], D20)
rep("全部 · 密集窗 2026-05→08", [r for r in rows if r["ts"] >= "2026-05-01"], D37)
rep("官方政策机构 · 密集窗", [r for r in rows if r["tier"] == "官方政策机构" and r["ts"] >= "2026-05-01"], D37)
rep("官方+当事人+央行 · 密集窗", [r for r in rows if r["tier"] != "财经媒体与快讯" and r["ts"] >= "2026-05-01"], D37)
print()
print("  仅 M17（PO1/PO2 需要的那一路）")
for r in rows: r["u"] = m17(r["text"])
rep("官方+当事人+央行 · 20 个月", [r for r in rows if r["tier"] != "财经媒体与快讯"], D20)
rep("全部 29 账号 · 20 个月", rows, D20)
