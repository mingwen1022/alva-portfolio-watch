"""⑤ 净化保留比例 与 倍数抬升 的关系 —— 给出可写进 plan.md 的操作界限"""
import json, os
import numpy as np
from scipy import stats
H = os.path.dirname(os.path.abspath(__file__))
R = [r for r in json.load(open(f"{H}/res.json")) if "error" not in r]
ARMS = ["and_base", "price_base", "vol_base", "or_base", "price_eq", "vol_eq",
        "or_eq", "or_scale", "price_eqblk", "price_only", "vol_only"]
xs, ys, tags = [], [], []
for r in R:
    for a in ARMS:
        v = r["arms"].get(a, {})
        if v.get("nbase") and v.get("nbase_np") and v.get("mult") and v.get("mult_np"):
            xs.append(v["nbase"] / v["nbase_np"]); ys.append(v["mult"] / v["mult_np"]); tags.append(a)
xs, ys = np.array(xs), np.array(ys)
print("样本 %d 个（标的 × 对照组）" % len(xs))
print(f"\n{'基准池保留比例':<16}{'个数':>6}{'倍数抬升 own/np 中位':>22}{'P10':>8}{'P90':>8}")
bins = [(0, .15), (.15, .25), (.25, .40), (.40, .55), (.55, .70), (.70, .80), (.80, 1.01)]
for lo, hi in bins:
    m = (xs >= lo) & (xs < hi)
    if m.sum() < 5: continue
    print(f"  [{lo:.2f}, {hi:.2f})      {m.sum():>6}{np.median(ys[m]):>22.3f}"
          f"{np.quantile(ys[m],.1):>8.3f}{np.quantile(ys[m],.9):>8.3f}")
sp = stats.spearmanr(xs, ys)
print(f"\n保留比例 vs 抬升倍率 Spearman {sp.statistic:+.3f} (p={sp.pvalue:.1e}) —— 留得越少，抬得越高")
print(f"\n各对照组的保留比例中位：")
for a in ARMS:
    v = [r["arms"][a]["nbase"]/r["arms"][a]["nbase_np"] for r in R
         if r["arms"].get(a, {}).get("nbase") and r["arms"][a].get("nbase_np")]
    w = [r["arms"][a]["mult"]/r["arms"][a]["mult_np"] for r in R
         if r["arms"].get(a, {}).get("mult") and r["arms"][a].get("mult_np")]
    print(f"  {a:<13} 保留 {np.median(v):>6.1%}   抬升 {np.median(w):>6.3f}×")
# 两条规则保留比例之比 vs 比较偏差
print(f"\n两条规则做比较时，保留比例之比 与 比较结论偏差的关系")
print(f"  {'对照':<14}{'保留比之比':>12}{'own 配对差':>12}{'np 配对差':>12}{'偏差':>10}")
for o in ["price_base", "or_base", "price_eq", "or_eq", "price_eqblk", "vol_base"]:
    rr, do, dn = [], [], []
    for r in R:
        A, B = r["arms"]["and_base"], r["arms"].get(o, {})
        if not (A.get("nbase") and B.get("nbase") and B.get("mult") and B.get("mult_np")): continue
        rr.append((A["nbase"]/A["nbase_np"]) / (B["nbase"]/B["nbase_np"]))
        do.append(A["mult"]-B["mult"]); dn.append(A["mult_np"]-B["mult_np"])
    print(f"  {o:<14}{np.median(rr):>12.2f}{np.median(do):>+12.3f}{np.median(dn):>+12.3f}"
          f"{np.median(do)-np.median(dn):>+10.3f}")
