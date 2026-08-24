"""逐标的明细：利率敏感样本 + 极值标的 + 多重比较视图。"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
per = json.load(open(f"{OUT}/core.json"))
fomc = json.load(open(f"{OUT}/fomc.json"))
U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
ST = [s for s in U if U[s]["asset_class"] == "us_equity" and s != "SPY" and s in per and "_err" not in per[s]]
EV = [("CPI_T0", "物价当日"), ("CPI_T-1", "物价T−1"), ("NFP_T0", "就业当日"),
      ("FEDFUNDS_T0", "利率当日"), ("GDP_T0", "产出当日"), ("PV1_win", "PV1(对照)")]

SHOW = ["AGNC", "IRM", "HR", "PK", "ALX", "JBGS", "JPM", "BAC", "V", "MA", "CME", "PNFP",
        "HTGC", "CACC", "LNT", "AVA", "MSEX", "TXNM", "VST", "GEV", "HNRG", "JNJ", "KO", "COST",
        "XOM", "NVDA", "TSLA", "AAPL"]
print(f"{'标的':6s} {'部门':8s} {'β':>6s} " + " ".join(f"{l:>16s}" for _, l in EV) + "   FOMC当日")
for s in SHOW:
    if s not in per: continue
    cells = []
    for ev, _ in EV:
        r = per[s].get(ev)
        cells.append(f"{r['mult']:5.2f}[{r['lo']:.2f},{r['hi']:.2f}]{'✓' if r['pass_'] else ' '}" if r else " " * 16)
    f = fomc.get(s, {}).get("0") or fomc.get(s, {}).get(0)
    fs = f"{f['mult']:5.2f}{'✓' if f['pass_'] else ' '}" if f else ""
    b = U[s]["beta"]
    print(f"{s:6s} {U[s]['sector']:8s} {float(b) if b else 0:6.2f} " + " ".join(cells) + f"   {fs}")

print("\n多重比较视图：91 只 × 4 个主检验（物价/就业 × T0/T−1）")
tests = ["CPI_T0", "CPI_T-1", "NFP_T0", "NFP_T-1"]
cnt = {}
for s in ST:
    k = sum(1 for t in tests if (per[s].get(t) or {}).get("pass_"))
    cnt[k] = cnt.get(k, 0) + 1
print(f"  通过 0 项 {cnt.get(0,0)} 只 · 1 项 {cnt.get(1,0)} 只 · 2 项 {cnt.get(2,0)} 只 · 3 项 {cnt.get(3,0)} 只 · 4 项 {cnt.get(4,0)} 只")
print(f"  至少通过 1 项：{sum(v for k,v in cnt.items() if k>0)} 只（4 项独立时随机期望约 {91*(1-0.975**4):.0f} 只）")
who = [s for s in ST if sum(1 for t in tests if (per[s].get(t) or {}).get('pass_')) >= 2]
print(f"  通过 ≥2 项的标的：{who}")

print("\n物价发布当日倍数最高的 8 只（看『通过』长什么样）")
rk = sorted([s for s in ST if per[s].get("CPI_T0")], key=lambda s: -per[s]["CPI_T0"]["mult"])[:8]
for s in rk:
    r = per[s]["CPI_T0"]
    print(f"  {s:6s} {U[s]['sector']:8s} {r['mult']:5.2f} [{r['lo']:.2f}, {r['hi']:.2f}] "
          f"n={r['n']} blocks={r['blocks']} {'PASS' if r['pass_'] else ''}")
