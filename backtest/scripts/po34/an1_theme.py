"""M16-A 结构式主题重叠 · 零拟合。

M16_A(post, 组合) = Σ_i w_i · 1[sector(i) ∈ post.sectors]
基础组合是纯部门等权 → M16_A ∈ {0,1}，即「这条帖点名的部门里有没有我的持仓」

检验：同一组合、同一分母下，匹配事件的确认率是否高于不匹配事件。
安慰剂：把全部事件时刻整体平移 ±7k 日（保留星期与时刻），重算同一统计量。
"""
import sys, json, collections
import numpy as np
from datetime import datetime, timezone
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid

RNG = np.random.default_rng(20260820)
NBOOT = 2000


def to_ep(ts):
    return int(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def blockboot(days, y, m, nboot=NBOOT):
    """按日成块自助，返回 Δ = rate(m) − rate(~m) 的分布。"""
    ud, inv = np.unique(days, return_inverse=True)
    D = len(ud)
    idx_by_day = [np.flatnonzero(inv == i) for i in range(D)]
    out = np.full(nboot, np.nan)
    for b in range(nboot):
        pick = RNG.integers(0, D, D)
        sel = np.concatenate([idx_by_day[i] for i in pick])
        yy, mm = y[sel], m[sel]
        if mm.sum() == 0 or (~mm).sum() == 0:
            continue
        out[b] = yy[mm].mean() - yy[~mm].mean()
    return out[~np.isnan(out)]


def cell(recs, G, port, eps, match, boot=True):
    v, c = G.query(port, eps)
    if v.sum() == 0:
        return None
    y = c[v].astype(float); m = match[v]
    days = np.array([r["day"] for r in recs])[v]
    if m.sum() < 3 or (~m).sum() < 3:
        return None
    d = y[m].mean() - y[~m].mean()
    res = dict(n=int(v.sum()), n1=int(m.sum()), n0=int((~m).sum()),
               r1=float(y[m].mean()), r0=float(y[~m].mean()), d=float(d),
               days1=int(len(set(days[m]))), days0=int(len(set(days[~m]))))
    if boot:
        bb = blockboot(days, y, m)
        res["lo"], res["hi"] = float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))
        res["pass"] = bool(res["lo"] > 0)
    return res


def run(layer_sel, name, ev, G, shifts=(0,)):
    sub = [r for r in ev if layer_sel(r)]
    eps0 = np.array([to_ep(r["ts"]) for r in sub])
    basis = [p for p in G.names() if p.startswith("B:")]
    out = {}
    for sh in shifts:
        eps = eps0 + sh * 86400
        rows = {}
        for p in basis:
            sec = p[2:]
            match = np.array([sec in r["secs"] for r in sub])
            r = cell(sub, G, p, eps, match, boot=(sh == 0))
            if r:
                rows[p] = r
        out[sh] = rows
    return sub, out


if __name__ == "__main__":
    recs, cp = polib.load()
    ev = polib.dedup_events(recs)
    G = confgrid.Grid()
    LAYERS = {
        "全部": lambda r: True,
        "main18": lambda r: r["layer"] == "main18",
        "cb4": lambda r: r["layer"] == "cb4",
        "media7": lambda r: r["layer"] == "media7",
        "TierA(main18+cb4)": lambda r: r["layer"] in ("main18", "cb4"),
    }
    HALVES = {"H1(01-04)": lambda r: polib.half(r) == "H1",
              "H2(05-08)": lambda r: polib.half(r) == "H2",
              "全期": lambda r: True}
    allres = {}
    for hn, hf in HALVES.items():
        for ln, lf in LAYERS.items():
            sub, out = run(lambda r: hf(r) and lf(r), ln, ev, G)
            rows = out[0]
            npass = sum(1 for v in rows.values() if v.get("pass"))
            ds = [v["d"] for v in rows.values()]
            print(f"\n【{hn} · {ln}】 组合数 {len(rows)}  通过 {npass}/{len(rows)}  Δ 中位 {np.median(ds)*100:+.2f}pp" if rows else f"\n【{hn} · {ln}】 无数据")
            for p, v in sorted(rows.items(), key=lambda x: -x[1]["d"]):
                star = "✅" if v.get("pass") else "  "
                print(f"   {star} {p:10} n匹配={v['n1']:>5}(日{v['days1']:>3}) n不匹={v['n0']:>5} "
                      f"率 {v['r1']:6.1%} vs {v['r0']:6.1%}  Δ={v['d']*100:+6.2f}pp  CI[{v['lo']*100:+6.2f},{v['hi']*100:+6.2f}]")
            allres[f"{hn}|{ln}"] = rows
    json.dump(allres, open("an1_theme.json", "w"), ensure_ascii=False, indent=1)
