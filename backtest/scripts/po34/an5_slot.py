"""时段混淆的量化 —— ④ 里「盘前 UTC<14 拿到 11/12 通过、Δ +23.9pp」必须先解释掉。"""
import sys, json
import numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid
from an1_theme import to_ep

recs, cp = polib.load()
ev = polib.dedup_events(recs)
G = confgrid.Grid()
eps = np.array([to_ep(r["ts"]) for r in ev])
et = np.array([r["etype"] for r in ev])
meta = json.load(open("grid_meta.json"))


def slots(port):
    """返回每条事件落到的 slot k（网格内）与 valid。"""
    g = G.g[port]; K = meta[port]["K"]
    pos = np.searchsorted(g["sorted"], eps, side="left")
    inr = pos < len(g["ok"])
    j = np.where(inr, g["ok"][np.clip(pos, 0, len(g["ok"]) - 1)], 0)
    v = g["valid"][j] & inr
    c = g["conf"][j] & v
    k = j % K
    return v, c, k


for port in ("B:科技", "B:加密"):
    v, c, k = slots(port)
    K = meta[port]["K"]
    print(f"\n===== {port}（{K} 槽）确认率随 slot 变化 =====")
    print("  slot  事件数   确认率")
    for kk in range(K):
        m = v & (k == kk)
        if m.sum() >= 20:
            print(f"  {kk:>4}  {m.sum():>6}   {c[m].mean():6.1%}")
    m = v
    print(f"  合计  {m.sum():>6}   {c[m].mean():6.1%}")
    # 事件类型的 slot 分布差异
    print("  各事件类型的平均 slot（越小越靠开盘）")
    for e in ["export-control", "monetary", "tariff", "geopolitical", "regulation", "personnel", "other"]:
        mm = v & (et == e)
        if mm.sum() >= 20:
            print(f"    {e:16} n={mm.sum():>5}  平均 slot {k[mm].mean():5.2f}  中位 {np.median(k[mm]):4.1f}  确认率 {c[mm].mean():6.1%}")
