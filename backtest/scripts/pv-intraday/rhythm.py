"""日内节律：逐 slot 的成交量与 |收益| 中位，跨标的取中位。
输出 derived/rhythm_<grid>.csv 与摘要。"""
import sys, json, numpy as np
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run/scripts")
from load_intraday import symbols, to_grid
from engine import build_grid, chain_returns

def rhythm(grid_kind, syms):
    rows = []
    for s in syms:
        try: g = to_grid(s, grid_kind)
        except Exception as e: continue
        if g["D"] < 100: continue
        C, Vv, present, filled = build_grid(g["sess"], g["slot"], g["close"], g["vol"], g["nslots"])
        r = chain_returns(C)
        K = g["nslots"]
        volmed = np.array([np.nanmedian(Vv[:, k][Vv[:, k] > 0]) if (Vv[:, k] > 0).any() else np.nan for k in range(K)])
        absr = np.array([np.nanmedian(np.abs(r[:, k])) for k in range(K)])
        cov = present.mean(axis=0)
        rows.append(dict(sym=s, volmed=volmed / np.nansum(volmed), absr=absr / np.nanmedian(absr),
                         cov=cov, present_rate=float(present.mean()), fill_rate=float(filled.mean()),
                         D=g["D"]))
    return rows

if __name__ == "__main__":
    import csv
    allsyms = symbols()
    us = [s for s in allsyms if to_grid(s)["kind"] == "stock"]
    cr = [s for s in allsyms if s not in us]
    out = {}
    for gk, ss in (("ETH", us), ("RTH", us), ("UTC", cr)):
        if not ss: continue
        rows = rhythm(gk, ss)
        if not rows: continue
        K = len(rows[0]["volmed"])
        vm = np.nanmedian(np.array([r["volmed"] for r in rows]), axis=0)
        am = np.nanmedian(np.array([r["absr"] for r in rows]), axis=0)
        cv = np.nanmedian(np.array([r["cov"] for r in rows]), axis=0)
        out[gk] = dict(n_sym=len(rows), K=K, vol_share=list(np.round(vm, 5)),
                       absr_rel=list(np.round(am, 3)), coverage=list(np.round(cv, 3)),
                       present_rate=float(np.median([r["present_rate"] for r in rows])),
                       fill_rate=float(np.median([r["fill_rate"] for r in rows])),
                       vol_ratio_max_min=float(np.nanmax(vm) / np.nanmin(vm)),
                       absr_ratio_max_min=float(np.nanmax(am) / np.nanmin(am)))
        print(gk, "标的", len(rows), " 量 max/min", round(out[gk]["vol_ratio_max_min"], 1),
              " |r| max/min", round(out[gk]["absr_ratio_max_min"], 1),
              " 覆盖率", round(out[gk]["present_rate"], 3))
    json.dump(out, open("derived/rhythm.json", "w"), indent=1)
