"""自算 beta，并用它重做 M16 的 beta 分组。

universe.csv 的 beta 列来自供应商快照（screener/technical-metrics?metric_type=BETA），
XOM = −0.483 · AAPL = 0.74 与常识不符，不能直接用来做敏感度分组。
本脚本自算两个版本：
  全样本 beta      对 SPY 日对数收益的 OLS 斜率（2020-01 → 2026-08 窗口内）
  滚动 beta 中位   90 日滚动 OLS 斜率的中位数（与上一轮 MA 报告同法）
"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
from engine import build, window_of

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
LO, HI = "2020-01-14", "2026-08-12"
W = 90
SEED, NB = 20260819, 4000


def rolling_beta(y, x, w=W):
    """逐日 90 日滚动 OLS 斜率（不含当日），返回中位数"""
    n = len(y)
    out = []
    sx = np.cumsum(np.nan_to_num(x)); sy = np.cumsum(np.nan_to_num(y))
    sxx = np.cumsum(np.nan_to_num(x) ** 2); sxy = np.cumsum(np.nan_to_num(x * y))
    ok = np.cumsum((~np.isnan(x) & ~np.isnan(y)).astype(int))
    for t in range(w, n):
        a, b = t - w, t
        m = ok[b - 1] - ok[a - 1]
        if m < 60:
            continue
        Sx = sx[b - 1] - sx[a - 1]; Sy = sy[b - 1] - sy[a - 1]
        Sxx = sxx[b - 1] - sxx[a - 1]; Sxy = sxy[b - 1] - sxy[a - 1]
        den = Sxx - Sx * Sx / m
        if den > 0:
            out.append((Sxy - Sx * Sy / m) / den)
    return float(np.median(out)) if out else None


if __name__ == "__main__":
    U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
    spy = build("SPY", "uni")
    per = json.load(open(f"{OUT}/core.json"))
    norms = json.load(open(f"{OUT}/norms.json"))
    beta = {}
    for s in U:
        if U[s]["asset_class"] != "us_equity" or s == "SPY" or s not in per or "_err" in per[s]:
            continue
        st = build(s, "uni")
        w = window_of(st, LO, HI)
        if w is None:
            continue
        lo, hi = w
        common = [(st["r"][i], spy["r"][spy["idx"][st["dates"][i]]])
                  for i in range(lo, hi + 1) if st["dates"][i] in spy["idx"]]
        y = np.array([a for a, b in common]); x = np.array([b for a, b in common])
        m = ~np.isnan(x) & ~np.isnan(y)
        full = float(np.polyfit(x[m], y[m], 1)[0])
        beta[s] = dict(full=full, roll=rolling_beta(y, x),
                       vendor=float(U[s]["beta"]) if U[s]["beta"] else None,
                       sector=U[s]["sector"])
    json.dump(beta, open(f"{OUT}/beta.json", "w"), ensure_ascii=False, indent=1)

    v = np.array([beta[s]["vendor"] for s in beta if beta[s]["vendor"] is not None])
    f = np.array([beta[s]["full"] for s in beta if beta[s]["vendor"] is not None])
    r, p = stats.spearmanr(v, f)
    print(f"供应商 beta vs 自算全样本 beta：Spearman {r:+.3f} (p={p:.2g}, n={len(v)})")
    print(f"  供应商 中位 {np.median(v):.2f} 区间 [{v.min():.2f}, {v.max():.2f}]")
    print(f"  自算   中位 {np.median(f):.2f} 区间 [{f.min():.2f}, {f.max():.2f}]")
    for s in ["XOM", "AAPL", "NVDA", "TSLA", "KO", "JPM", "AGNC", "LNT", "V", "MSTR"]:
        if s in beta:
            print(f"  {s:6s} 供应商 {beta[s]['vendor']:6.2f}  自算全样本 {beta[s]['full']:6.2f}  "
                  f"自算滚动中位 {beta[s]['roll']:6.2f}")

    EVENTS = ["CPI_T0", "CPI_T-1", "NFP_T0", "NFP_T-1", "GDP_T0", "FEDFUNDS_T0"]
    LAB = {"CPI_T0": "物价当日", "CPI_T-1": "物价前1日", "NFP_T0": "就业当日",
           "NFP_T-1": "就业前1日", "GDP_T0": "产出当日", "FEDFUNDS_T0": "有效联邦基金利率当日"}
    for key in ("full", "roll"):
        bs = {s: beta[s][key] for s in beta if beta[s][key] is not None}
        md = np.median(list(bs.values()))
        A = [s for s in bs if bs[s] > md]; B = [s for s in bs if bs[s] <= md]
        print(f"\n自算 beta（{'全样本 OLS' if key=='full' else '90 日滚动中位'}）中位 {md:.3f} "
              f"→ 高 {len(A)} 只 / 低 {len(B)} 只")
        print(f"{'事件':16s} {'高beta中位':>10s} {'低beta中位':>10s} {'逐日配对差':>10s} {'95%区间':>20s} {'Spearman':>9s} {'p':>7s}")
        for ev in EVENTS:
            ma = np.median([per[s][ev]["mult"] for s in A if per[s].get(ev)])
            mb = np.median([per[s][ev]["mult"] for s in B if per[s].get(ev)])
            days = sorted(set().union(*[set(norms.get(s, {}).get(ev, {})) for s in bs]))
            d = []
            for x in days:
                a = [norms[s][ev][x] for s in A if x in norms.get(s, {}).get(ev, {})]
                b = [norms[s][ev][x] for s in B if x in norms.get(s, {}).get(ev, {})]
                if len(a) >= 3 and len(b) >= 3:
                    d.append(np.mean(a) - np.mean(b))
            d = np.array(d)
            rng = np.random.default_rng(SEED)
            rep = np.sort(d[rng.integers(0, len(d), (NB, len(d)))].mean(axis=1))
            x_ = [bs[s] for s in bs if per[s].get(ev)]
            y_ = [per[s][ev]["mult"] for s in bs if per[s].get(ev)]
            rr, pp = stats.spearmanr(x_, y_)
            print(f"{LAB[ev]:16s} {ma:10.3f} {mb:10.3f} {d.mean():+10.4f} "
                  f"[{rep[int(.025*NB)]:+.4f}, {rep[int(.975*NB)]:+.4f}] {rr:+9.3f} {pp:7.3f}")
