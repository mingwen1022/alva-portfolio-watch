"""从 core.json 汇总 MA1 / MA2 / MA3 / 安慰剂 / 功效上界 各表。"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"

per = json.load(open(f"{OUT}/core.json"))
U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
STOCKS = [s for s, r in U.items() if r["asset_class"] == "us_equity" and s != "SPY"
          and s in per and "_err" not in per[s]]
CRYPTO = [s for s, r in U.items() if r["asset_class"] == "crypto" and s in per and "_err" not in per[s]]
RATE_SENS = {"金融", "房地产", "公用事业"}


def col(syms, ev, key="mult"):
    return [per[s][ev][key] for s in syms if per[s].get(ev)]


def q(v):
    v = np.sort(np.array(v, dtype=float))
    return v.min(), np.quantile(v, .25), np.median(v), np.quantile(v, .75), v.max()


def summarize(syms, ev, name):
    r = [per[s][ev] for s in syms if per[s].get(ev)]
    if not r:
        return None
    m = np.array([x["mult"] for x in r])
    lo = np.array([x["lo"] for x in r]); hi = np.array([x["hi"] for x in r])
    blk = np.array([x["blocks"] for x in r]); n = np.array([x["n"] for x in r])
    p = int(sum(1 for x in r if x["pass_"]))
    return dict(name=name, k=len(r), npass=p, ratio=f"{p}/{len(r)}",
                nmed=int(np.median(n)), blkmin=int(blk.min()),
                mmin=m.min(), m25=np.quantile(m, .25), mmed=np.median(m),
                m75=np.quantile(m, .75), mmax=m.max(),
                himed=float(np.median(hi)), himax=float(hi.max()), lomax=float(lo.max()))


def line(d):
    return (f"{d['name']:26s} {d['ratio']:>8s} 触发中位 {d['nmed']:3d} 最小块 {d['blkmin']:3d}  "
            f"倍数 {d['mmin']:.2f} / {d['m25']:.2f} / {d['mmed']:.2f} / {d['m75']:.2f} / {d['mmax']:.2f}  "
            f"区间上界中位 {d['himed']:.2f} 最大 {d['himax']:.2f}")


MAIN = [("CPI", "物价"), ("CORE_CPI", "核心物价"), ("NFP", "就业"),
        ("UNRATE", "失业率"), ("GDP", "产出"), ("FEDFUNDS", "有效联邦基金利率")]

print("=" * 130)
print("MA1 · 发布前 1 交易日（T−1）  ·  92 只美股（91 只非基准）")
print("=" * 130)
print(f"{'指标':26s} {'通过':>8s} {'':>16s}  {'倍数 min/Q1/中位/Q3/max':>44s}  区间上界")
for k, lab in MAIN:
    d = summarize(STOCKS, f"{k}_T-1", f"{lab} MA1(T−1)")
    if d: print(line(d))
print()
for k, lab in MAIN:
    d = summarize(STOCKS, f"{k}_T0", f"{lab} 发布当日(参照)")
    if d: print(line(d))
print()
print("加密 25 只：")
for k, lab in MAIN:
    for sh, tag in (("_T-1", "MA1(T−1)"), ("_T0", "发布当日")):
        d = summarize(CRYPTO, f"{k}{sh}", f"{lab} {tag}")
        if d: print(line(d))

print()
print("=" * 130)
print("阳性对照 · PV1（同一引擎、同一窗口）")
print("=" * 130)
for tag, ev in (("全样本 2018→", "PV1_full"), ("MA 窗口 2020-01→2026-08", "PV1_win")):
    d = summarize(STOCKS, ev, f"PV1 美股 {tag}")
    if d: print(line(d))
    d = summarize(CRYPTO, ev, f"PV1 加密 {tag}")
    if d: print(line(d))

print()
print("=" * 130)
print("MA2 · 实际值偏离（意外度替代两口径 × 两档阈值）")
print("=" * 130)
for k, lab in (("CPI", "物价"), ("NFP", "就业")):
    for mode, ml in (("literal", "原始值口径"), ("delta", "环比口径")):
        for th in ("1.5", "2.0"):
            ev = f"MA2_{k}_{mode}_{th}"
            d = summarize(STOCKS, ev, f"{lab} {ml} ≥{th}")
            if d: print(line(d))

print()
print("=" * 130)
print("安慰剂平移（|k| ≥ 6 才有效；|k| ≤ 5 前瞻窗含真实触发日，仅作剖面）")
print("=" * 130)
for base, lab in (("CPI", "物价发布日"), ("NFP", "就业发布日"), ("GDP", "产出发布日")):
    print(f"\n{lab}：")
    hdr = []
    for k in (-10, -8, -6, -4, -2, -1, 0, 1, 2, 4, 6, 8, 10):
        ev = f"PLACEBO_{base}_{k:+d}" if k != 0 else f"{base}_T0"
        d = summarize(STOCKS, ev, f"k={k:+d}")
        if d:
            hdr.append((k, d["mmed"], d["npass"], d["k"]))
    print("  平移 k    " + " ".join(f"{k:+6d}" for k, *_ in hdr))
    print("  倍数中位  " + " ".join(f"{m:6.2f}" for _, m, *_ in hdr))
    print("  通过数    " + " ".join(f"{p:6d}" for _, _, p, _ in hdr))
    # 加密对照
    hdr2 = []
    for k in (-10, -8, -6, -4, -2, -1, 0, 1, 2, 4, 6, 8, 10):
        ev = f"PLACEBO_{base}_{k:+d}" if k != 0 else f"{base}_T0"
        d = summarize(CRYPTO, ev, "")
        if d: hdr2.append((k, d["mmed"], d["npass"]))
    print("  加密中位  " + " ".join(f"{m:6.2f}" for _, m, _ in hdr2))

print()
print("=" * 130)
print("产出（GDP）发布日的财报季重合复核 · 逐部门 + 加密")
print("=" * 130)
secs = sorted(set(U[s]["sector"] for s in STOCKS))
print(f"{'部门':10s} {'n':>3s} {'GDP当日中位':>12s} {'通过':>6s} {'GDP T−1 中位':>13s} {'通过':>6s} {'物价当日中位':>13s} {'通过':>6s}")
for sec in secs:
    ss = [s for s in STOCKS if U[s]["sector"] == sec]
    row = []
    for ev in ("GDP_T0", "GDP_T-1", "CPI_T0"):
        v = [per[s][ev]["mult"] for s in ss if per[s].get(ev)]
        p = sum(1 for s in ss if (per[s].get(ev) or {}).get("pass_"))
        row += [np.median(v) if v else float("nan"), p]
    print(f"{sec:10s} {len(ss):3d} {row[0]:12.3f} {row[1]:6d} {row[2]:13.3f} {row[3]:6d} {row[4]:13.3f} {row[5]:6d}")
v = [per[s]["GDP_T0"]["mult"] for s in CRYPTO if per[s].get("GDP_T0")]
print(f"{'加密':10s} {len(v):3d} {np.median(v):12.3f}")

print()
print("=" * 130)
print("legacy 口径对照（V=RV5/σ_rob · 全体非触发中位基准）")
print("=" * 130)
for ev in ("CPI_T0", "CPI_T-1", "NFP_T0", "NFP_T-1", "GDP_T0", "GDP_T-1"):
    r = [per[s][ev] for s in STOCKS if per[s].get(ev) and "mult_legacy" in per[s][ev]]
    if not r: continue
    m = np.array([x["mult_legacy"] for x in r])
    p = sum(1 for x in r if x["pass_legacy"])
    m2 = np.array([x["mult"] for x in r]); p2 = sum(1 for x in r if x["pass_"])
    print(f"{ev:12s} legacy 中位 {np.median(m):.3f} 通过 {p}/{len(r)}   |   R28 中位 {np.median(m2):.3f} 通过 {p2}/{len(r)}")
