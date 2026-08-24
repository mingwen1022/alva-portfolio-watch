"""M16-B 拟合式：event_type × 部门 敏感度矩阵，只用前半段（2026-01→04）拟合。

S[e,s] = rate_H1(事件类型 e, 部门组合 s) − base_H1(部门组合 s)          单位 pp
M16_B(e, 组合 P) = Σ_i w_i · S[e, sector(i)]                           事前可算
检验：H2 上 M16_B 是否预测得了实际抬升。两条路 ——
  ① 时间存活   同一批基础组合，H1 矩阵 vs H2 矩阵的秩相关
  ② 组合外推   H1 矩阵 → 预测 12 个混合持仓组合在 H2 的抬升
"""
import sys, json, itertools
import numpy as np
from scipy import stats
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid, port_defs, compute_conf
from an1_theme import to_ep, blockboot

ETS = ["export-control", "monetary", "tariff", "geopolitical", "regulation", "personnel", "other"]
MINN = 15   # 单元最少事件数，先写定


def matrix(ev, G, sel, ports):
    """返回 S[e][port] = 抬升(pp)，n[e][port]，以及各组合基准率。共用分母（同一 sel 集合）。"""
    sub = [r for r in ev if sel(r)]
    eps = np.array([to_ep(r["ts"]) for r in sub])
    et = np.array([r["etype"] for r in sub])
    days = np.array([r["day"] for r in sub])
    S, N, BASE, DAYS = {}, {}, {}, {}
    for p in ports:
        v, c = G.query(p, eps)
        if v.sum() < 30:
            continue
        y = c[v].astype(float); e2 = et[v]; d2 = days[v]
        BASE[p] = float(y.mean())
        for e in ETS:
            m = e2 == e
            if m.sum() < MINN:
                continue
            S.setdefault(e, {})[p] = float(y[m].mean() - y.mean())
            N.setdefault(e, {})[p] = int(m.sum())
            DAYS.setdefault(e, {})[p] = int(len(set(d2[m])))
    return S, N, BASE, DAYS


def flat(S, ports):
    k, v = [], []
    for e in ETS:
        for p in ports:
            if e in S and p in S[e]:
                k.append((e, p)); v.append(S[e][p])
    return k, np.array(v)


if __name__ == "__main__":
    recs, cp = polib.load()
    ev = polib.dedup_events(recs)
    G = confgrid.Grid()
    basis = [p for p in G.names() if p.startswith("B:")]
    hold = [p for p in G.names() if p.startswith("H:")]

    LAY = {"全部": lambda r: True,
           "TierA": lambda r: r["layer"] in ("main18", "cb4"),
           "media7": lambda r: r["layer"] == "media7"}
    out = {}
    for ln, lf in LAY.items():
        S1, N1, B1, D1 = matrix(ev, G, lambda r: lf(r) and polib.half(r) == "H1", basis)
        S2, N2, B2, D2 = matrix(ev, G, lambda r: lf(r) and polib.half(r) == "H2", basis)
        k1, v1 = flat(S1, basis); k2, v2 = flat(S2, basis)
        common = [k for k in k1 if k in set(k2)]
        a = np.array([S1[e][p] for e, p in common]); b = np.array([S2[e][p] for e, p in common])
        rho, pr = stats.spearmanr(a, b) if len(common) > 3 else (np.nan, np.nan)
        pear = stats.pearsonr(a, b)[0] if len(common) > 3 else np.nan
        sign = int(np.sum(np.sign(a) == np.sign(b)))
        print(f"\n===== 层 {ln} =====")
        print(f"H1 单元 {len(k1)} · H2 单元 {len(k2)} · 共同 {len(common)}")
        print(f"切半一致性  Spearman {rho:+.3f} (p={pr:.3f}) · Pearson {pear:+.3f} · 同号 {sign}/{len(common)}")
        if len(common):
            bt = stats.binomtest(sign, len(common), 0.5)
            print(f"            同号检验 p={bt.pvalue:.4f}")
        out[ln] = dict(S1=S1, S2=S2, B1=B1, B2=B2, N1=N1, N2=N2, D1=D1, D2=D2,
                       common=[list(x) for x in common], rho=float(rho), sign=sign, ncommon=len(common))
        # 打印矩阵
        print("\nH1 抬升矩阵（pp，括号内是事件数）")
        hdr = "  ".join(f"{p[2:]:>6}" for p in basis)
        print(f"{'':16}{hdr}")
        for e in ETS:
            row = []
            for p in basis:
                if e in S1 and p in S1[e]:
                    row.append(f"{S1[e][p]*100:>+6.1f}")
                else:
                    row.append(f"{'--':>6}")
            print(f"{e:16}{'  '.join(row)}")
        print("\nH2 抬升矩阵（pp）")
        print(f"{'':16}{hdr}")
        for e in ETS:
            row = []
            for p in basis:
                if e in S2 and p in S2[e]:
                    row.append(f"{S2[e][p]*100:>+6.1f}")
                else:
                    row.append(f"{'--':>6}")
            print(f"{e:16}{'  '.join(row)}")
    json.dump(out, open("an2_fit.json", "w"), ensure_ascii=False, indent=1)
