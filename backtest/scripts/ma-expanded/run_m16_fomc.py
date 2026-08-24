"""M16 在 FOMC（手工日历）上的检验 —— registry 把 FOMC 列为 M16 最该起作用的事件。"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
from scipy import stats
from engine import build, norm_V, window_of, to_trading
from run_fomc import FOMC, LO, HI

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
RATE = {"金融", "房地产", "公用事业"}
SEED, NB = 20260819, 4000


def work(arg):
    sym, source = arg
    try:
        s = build(sym, source)
    except Exception:
        return None
    w = window_of(s, LO, HI)
    if w is None:
        return None
    lo, hi = w
    T = sorted(set(i for i in (to_trading(s, d, 0) for d in FOMC) if i is not None and lo <= i <= hi))
    nv, _ = norm_V(s, T, lo, hi)
    if nv is None:
        return None
    return sym, {s["dates"][i]: float(nv[i]) for i in T if not np.isnan(nv[i])}


def paired(A, B, nrm):
    days = sorted(set().union(*[set(nrm[s]) for s in A + B if s in nrm]))
    d = []
    for x in days:
        a = [nrm[s][x] for s in A if s in nrm and x in nrm[s]]
        b = [nrm[s][x] for s in B if s in nrm and x in nrm[s]]
        if len(a) >= 3 and len(b) >= 3:
            d.append(np.mean(a) - np.mean(b))
    d = np.array(d)
    rng = np.random.default_rng(SEED)
    rep = np.sort(d[rng.integers(0, len(d), (NB, len(d)))].mean(axis=1))
    return dict(n=len(d), mean=float(d.mean()), lo=float(rep[int(.025 * NB)]),
                hi=float(rep[int(.975 * NB)]), p=float(stats.wilcoxon(d).pvalue))


if __name__ == "__main__":
    U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
    jobs = [(s, "uni") for s in U if U[s]["asset_class"] == "us_equity" and s != "SPY"]
    jobs += [(s, "crypto") for s in U if U[s]["asset_class"] == "crypto"]
    nrm = {}
    with Pool(9) as p:
        for o in p.imap_unordered(work, jobs):
            if o: nrm[o[0]] = o[1]
    json.dump(nrm, open(f"{OUT}/m16_fomc.json", "w"))
    ST = [s for s in nrm if U[s]["asset_class"] == "us_equity"]
    beta = {s: float(U[s]["beta"]) for s in ST if U[s]["beta"]}
    md = np.median(list(beta.values()))
    groups = [
        ("利率敏感 vs 其余", [s for s in ST if U[s]["sector"] in RATE],
         [s for s in ST if U[s]["sector"] not in RATE]),
        (f"高beta vs 低beta（分界 {md:.2f}）", [s for s in beta if beta[s] > md],
         [s for s in beta if beta[s] <= md]),
        ("registry β>1.2 高敏感 vs 低敏感", [s for s in beta if beta[s] > 1.2],
         [s for s in beta if beta[s] <= 1.2]),
        ("加密 vs 美股", [s for s in nrm if U[s]["asset_class"] == "crypto"], ST),
    ]
    for name, A, B in groups:
        r = paired(A, B, nrm)
        print(f"{name:32s} nA={len(A):3d} nB={len(B):3d}  逐日配对差 {r['mean']:+.4f} "
              f"[{r['lo']:+.4f}, {r['hi']:+.4f}]  Wilcoxon p={r['p']:.3f}  ({r['n']} 个决议日)")
    x = [beta[s] for s in beta]
    y = [float(np.median(list(nrm[s].values()))) for s in beta]
    r, p = stats.spearmanr(x, y)
    print(f"\nbeta 与 FOMC 日归一化 V 中位的 Spearman {r:+.3f} (p={p:.3f}, n={len(x)})")
