"""① 切半映射一致性的经验零   ② 功效：每格能测出多大的效应"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid, stratlib as S
from an1_theme import to_ep
from an3_oos import fit_S1, ETS

recs, cp = polib.load()
ev = polib.dedup_events(recs)
G = confgrid.Grid()
eps0 = np.array([to_ep(r["ts"]) for r in ev])
days = np.array([r["day"] for r in ev])
et = np.array([r["etype"] for r in ev])
half = np.array([polib.half(r) for r in ev])
basis = [p for p in G.names() if p.startswith("B:")]


def consistency(eps, lf):
    S1 = fit_S1(ev, G, eps, lambda r: lf(r) and polib.half(r) == "H1", basis)
    S2 = fit_S1(ev, G, eps, lambda r: lf(r) and polib.half(r) == "H2", basis)
    a, b = [], []
    for e in ETS:
        for p in basis:
            s = p[2:]
            if e in S1 and s in S1[e] and e in S2 and s in S2[e]:
                a.append(S1[e][s]); b.append(S2[e][s])
    if len(a) < 5:
        return None
    a, b = np.array(a), np.array(b)
    return stats.spearmanr(a, b)[0], int(np.sum(np.sign(a) == np.sign(b))), len(a)


print("=" * 78); print("① 切半映射一致性 —— 对经验零读"); print("=" * 78)
for ln, lf in (("全部", lambda r: True), ("TierA", lambda r: r["layer"] in ("main18", "cb4")),
               ("media7", lambda r: r["layer"] == "media7")):
    obs = consistency(eps0, lf)
    nul = []
    for sh in [-7 * k for k in range(1, 26)]:
        x = consistency(eps0 + sh * 86400, lf)
        if x: nul.append(x[0])
    nul = np.array(nul)
    print(f"  {ln:8} 实测 Spearman {obs[0]:+.3f}（同号 {obs[1]}/{obs[2]}）  "
          f"安慰剂均值 {nul.mean():+.3f} sd {nul.std():.3f}  安慰剂中 ≥实测 {np.mean(nul >= obs[0]):.0%}")
    print(f"           ⚠️ 安慰剂日历同样能给出 {np.percentile(nul, 95):+.3f} 的一致性（95 分位）"
          f"，实测落在其 {100*np.mean(nul < obs[0]):.0f} 分位")

print(); print("=" * 78); print("② 功效：各格的 95% 区间半宽 = 能测出的最小效应"); print("=" * 78)
print(f"  {'事件类型':16}{'组合':10}{'n':>6}{'半宽(pp)':>10}  能否检出 registry 声称的 +8pp")
for e, p in [("export-control", "B:科技"), ("export-control", "B:加密"), ("monetary", "B:加密"),
             ("monetary", "B:科技"), ("tariff", "B:科技"), ("geopolitical", "B:加密")]:
    r = S.strat_cell(G, p, et == e, np.ones(len(ev), bool), eps0, days, nboot=1500)
    if not r: continue
    hw = (r["hi"] - r["lo"]) / 2 * 100
    print(f"  {e:16}{p:10}{r['n1']:>6}{hw:>10.2f}  {'✅ 可以' if hw < 8 else '❌ 功效不足，测不了'}")
print()
print("  半宽 > 8pp 的格子上，「没通过」不等于「证伪」—— 属于 🟠 已测未达判据。")
