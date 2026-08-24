"""样本外检验 + 经验零标定。

流程（整套在安慰剂日历上原样重跑，所以零里包含了「拟合」这一步）：
  ① 只用 H1（2026-01→04）拟合 S1[事件类型, 部门]
  ② 对任意组合 P：M16_B(e,P) = Σ_i w_i·S1[e, sector_i]，> 0 判高敏
  ③ 在 H2（2026-05→08）上算 Δ = 率(高敏事件) − 率(低敏事件)，同一分母
  ④ 按日成块自助 95% 区间，下界 > 0 记为通过
  ⑤ 通过比例对经验零读：把全部事件时刻整体平移 −7k 日，①–④ 原样重跑
"""
import sys, json
import numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid, port_defs, compute_conf
from an1_theme import to_ep, blockboot

ETS = ["export-control", "monetary", "tariff", "geopolitical", "regulation", "personnel", "other"]
MINN = 15
SHIFTS = [-7 * k for k in range(1, 26)]      # 25 个安慰剂日历，|k| ≥ 7 日 ≫ 前瞻窗 30 分钟


def sector_of(sym, u):
    return u[sym]


def fit_S1(ev, G, eps, sel_h1, basis):
    """只用 H1 事件拟合。返回 S1[e][部门名]。"""
    m = np.array([sel_h1(r) for r in ev])
    et = np.array([r["etype"] for r in ev])
    S1 = {}
    for p in basis:
        v, c = G.query(p, eps)
        vv = v & m
        if vv.sum() < 50:
            continue
        y = c[vv].astype(float); e2 = et[vv]
        base = y.mean()
        for e in ETS:
            k = e2 == e
            if k.sum() < MINN:
                continue
            S1.setdefault(e, {})[p[2:]] = float(y[k].mean() - base)
    return S1


def score(S1, e, members, u):
    """M16_B：等权组合的部门敏感度加权和。缺格按 0（不猜）。"""
    if e not in S1:
        return 0.0
    w = 1.0 / len(members)
    return sum(w * S1[e].get(u.get(s, ""), 0.0) for s in members)


def oos(ev, G, eps, sel_h2, S1, ports, u, boot=True):
    m2 = np.array([sel_h2(r) for r in ev])
    et = np.array([r["etype"] for r in ev])
    days = np.array([r["day"] for r in ev])
    rows = {}
    for p, mem in ports.items():
        sc = np.array([score(S1, e, mem, u) for e in et])
        hi = sc > 0
        v, c = G.query(p, eps)
        vv = v & m2
        if vv.sum() < 50:
            continue
        y = c[vv].astype(float); h = hi[vv]; d = days[vv]
        if h.sum() < 10 or (~h).sum() < 10:
            continue
        dd = float(y[h].mean() - y[~h].mean())
        r = dict(n=int(vv.sum()), n1=int(h.sum()), n0=int((~h).sum()),
                 r1=float(y[h].mean()), r0=float(y[~h].mean()), d=dd,
                 days1=int(len(set(d[h]))))
        if boot:
            bb = blockboot(d, y, h, nboot=1000)
            r["lo"] = float(np.percentile(bb, 2.5)); r["hi"] = float(np.percentile(bb, 97.5))
            r["pass"] = bool(r["lo"] > 0)
        rows[p] = r
    return rows


def main():
    recs, cp = polib.load()
    ev = polib.dedup_events(recs)
    G = confgrid.Grid()
    u = {r["symbol"]: r["sector"] for r in port_defs.load_universe()}
    basis = [p for p in G.names() if p.startswith("B:")]
    meta = json.load(open("grid_meta.json"))
    PORTS = {p: meta[p]["members"] for p in G.names()}
    eps0 = np.array([to_ep(r["ts"]) for r in ev])

    LAY = {"全部": lambda r: True,
           "TierA": lambda r: r["layer"] in ("main18", "cb4"),
           "media7": lambda r: r["layer"] == "media7"}
    report = {}
    for ln, lf in LAY.items():
        h1 = lambda r: lf(r) and polib.half(r) == "H1"
        h2 = lambda r: lf(r) and polib.half(r) == "H2"
        S1 = fit_S1(ev, G, eps0, h1, basis)
        rows = oos(ev, G, eps0, h2, S1, PORTS, u)
        bas = {p: v for p, v in rows.items() if p.startswith("B:")}
        hol = {p: v for p, v in rows.items() if p.startswith("H:")}
        pb = sum(1 for v in bas.values() if v["pass"]); pb_n = len(bas)
        ph = sum(1 for v in hol.values() if v["pass"]); ph_n = len(hol)
        print(f"\n===== 层 {ln} · 样本外（H1 拟合 → H2 检验）=====")
        print(f"  基础组合 通过 {pb}/{pb_n}  Δ 中位 {np.median([v['d'] for v in bas.values()])*100:+.2f}pp")
        print(f"  留出组合 通过 {ph}/{ph_n}  Δ 中位 {np.median([v['d'] for v in hol.values()])*100:+.2f}pp")
        for p, v in sorted(rows.items(), key=lambda x: -x[1]["d"]):
            print(f"    {'✅' if v['pass'] else '  '} {p:10} 高敏 n={v['n1']:>5}(日{v['days1']:>3}) 低敏 n={v['n0']:>5} "
                  f"{v['r1']:6.1%} vs {v['r0']:6.1%}  Δ={v['d']*100:+6.2f}pp CI[{v['lo']*100:+6.2f},{v['hi']*100:+6.2f}]")
        # 经验零
        nulls = []
        for sh in SHIFTS:
            eps = eps0 + sh * 86400
            S1n = fit_S1(ev, G, eps, h1, basis)
            rn = oos(ev, G, eps, h2, S1n, PORTS, u, boot=True)
            bn = {p: v for p, v in rn.items() if p.startswith("B:")}
            hn = {p: v for p, v in rn.items() if p.startswith("H:")}
            nulls.append((sum(1 for v in bn.values() if v["pass"]) / max(len(bn), 1),
                          sum(1 for v in hn.values() if v["pass"]) / max(len(hn), 1),
                          float(np.median([v["d"] for v in rn.values()]))))
        nb = np.array([x[0] for x in nulls]); nh = np.array([x[1] for x in nulls]); nd = np.array([x[2] for x in nulls])
        print(f"  经验零（{len(SHIFTS)} 个平移日历）：")
        print(f"    基础组合通过比例  实测 {pb/max(pb_n,1):.1%}  零均值 {nb.mean():.1%}  零 95 分位 {np.percentile(nb,95):.1%}  "
              f"零中 ≥实测 的比例 {np.mean(nb >= pb/max(pb_n,1)):.1%}")
        print(f"    留出组合通过比例  实测 {ph/max(ph_n,1):.1%}  零均值 {nh.mean():.1%}  零 95 分位 {np.percentile(nh,95):.1%}  "
              f"零中 ≥实测 的比例 {np.mean(nh >= ph/max(ph_n,1)):.1%}")
        obs_d = float(np.median([v["d"] for v in rows.values()]))
        print(f"    Δ 中位            实测 {obs_d*100:+.2f}pp  零均值 {nd.mean()*100:+.2f}pp  零 95 分位 {np.percentile(nd,95)*100:+.2f}pp  "
              f"零中 ≥实测 的比例 {np.mean(nd >= obs_d):.1%}")
        report[ln] = dict(rows=rows, S1=S1, pass_basis=[pb, pb_n], pass_hold=[ph, ph_n],
                          null_basis=nb.tolist(), null_hold=nh.tolist(), null_d=nd.tolist(), obs_d=obs_d)
    json.dump(report, open("an3_oos.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
