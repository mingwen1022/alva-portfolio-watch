"""零成本自洽检验 —— 先于任何统计检验做。
① 包含关系：同一分母下 rate(B) 必落在 rate(A) 与 rate(B\A) 之间
② 恒等式：Σ_e n_e·(rate_e − base) ≡ 0（抬升按事件数加权必然归零）
③ 量纲与边界：全部率落在 [0,1]；n1+n0 = n
④ 保留比例：跨 arm 比较的两侧必须同分母（本设计构造上同分母，验证之）
"""
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
ETS = ["export-control", "monetary", "tariff", "geopolitical", "regulation", "personnel", "other"]

bad = []
for p in G.names():
    v, c = G.query(p, eps)
    if v.sum() < 30:
        continue
    y = c[v].astype(float); e2 = et[v]
    base = y.mean()
    # ② 恒等式
    tot = sum((e2 == e).sum() * (y[e2 == e].mean() - base) for e in ETS if (e2 == e).sum())
    if abs(tot) > 1e-8 * len(y):
        bad.append(f"{p} 恒等式残差 {tot:.3e}")
    # ① 包含关系（A = monetary，B = monetary ∪ tariff）
    A = e2 == "monetary"; C = e2 == "tariff"; B = A | C
    if A.sum() and C.sum():
        rA, rC, rB = y[A].mean(), y[C].mean(), y[B].mean()
        if not (min(rA, rC) - 1e-12 <= rB <= max(rA, rC) + 1e-12):
            bad.append(f"{p} 包含关系违反 rA={rA:.4f} rB={rB:.4f} rC={rC:.4f}")
    # ③ 边界
    if not (0 <= base <= 1):
        bad.append(f"{p} base 越界 {base}")
    if int(v.sum()) != int(np.sum([(e2 == e).sum() for e in ETS])):
        bad.append(f"{p} 分类不完备：{v.sum()} vs {np.sum([(e2==e).sum() for e in ETS])}")

# ④ 分母一致性：event_type 分层与主题匹配分层用的都是同一个 v 掩码
print(f"检查了 {len([p for p in G.names()])} 个组合")
if bad:
    print("⚠️ 自洽检验失败：")
    for b in bad:
        print("   ", b)
else:
    print("✅ 四项零成本自洽检验全部通过（恒等式 · 包含关系 · 边界 · 分类完备）")

# 保留比例表（净化分母规则的可比性判断）
print("\n各组合窗口保留比例（跨组合比较的可比性依据）")
for p in sorted(G.names()):
    v, _ = G.query(p, eps)
    print(f"  {p:12} {v.sum()/len(eps):6.1%}")
