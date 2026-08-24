"""①②③ 分析：共用分母可靠性 · 三套分母一致性 · 切半稳定性"""
import json, os, sys
import numpy as np
from scipy import stats

H = os.path.dirname(os.path.abspath(__file__))
R = [r for r in json.load(open(f"{H}/res.json")) if "error" not in r]
S = {r["sym"]: r for r in json.load(open(f"{H}/supp.json")) if "error" not in r}
RNG = np.random.default_rng(11)
CN = {"and_base": "双确认 AND", "price_base": "仅价格 等阈值", "vol_base": "仅量能 等阈值",
      "or_base": "价格 OR 量能", "price_eq": "仅价格 等触发数", "vol_eq": "仅量能 等触发数",
      "or_eq": "OR 等触发数", "or_scale": "OR 等比例放大", "price_eqblk": "仅价格 等块数",
      "price_only": "价格中·量能未中", "vol_only": "量能中·价格未中"}


def bmed(x, nb=20000):
    x = np.asarray(x, float)
    m = np.median(x[RNG.integers(0, len(x), size=(nb, len(x)))], axis=1); m.sort()
    return float(np.median(x)), float(m[int(.025*nb)]), float(m[int(.975*nb)])


def sgn(d):
    d = np.asarray(d, float); d = d[d != 0]
    k, n = int((d > 0).sum()), len(d)
    return k, n, k/n, stats.binomtest(k, n, .5).pvalue


def hdr(t): print("\n" + "="*80); print(t); print("="*80)


# ------------------------------------------------------- ① cb 分母自身可靠性
hdr("① 共用净化分母 cb 的自身可靠性")
tot_dec, thin_dec, empty_dec, sizes = 0, 0, 0, []
tick_thin = 0
for s, r in S.items():
    p = r["cb_pool"]
    tot_dec += len(p); thin_dec += sum(1 for x in p if x < 10); empty_dec += sum(1 for x in p if x == 0)
    sizes += p
    if any(x < 10 for x in p): tick_thin += 1
print(f"  cb 池共 {tot_dec} 个 sigma 十分位格；其中 <10 天的 {thin_dec} 个 ({thin_dec/tot_dec:.1%})，"
      f"空的 {empty_dec} 个 ({empty_dec/tot_dec:.1%})")
print(f"  {tick_thin}/{len(S)} 只标的至少有一层被抽薄到 <10 天 → 该层回退用全局中位数")
print(f"  cb 池每层天数 中位 {np.median(sizes):.0f}  P10 {np.quantile(sizes,.1):.0f}")
npz = [x for r in S.values() for x in r["np_pool"]]
print(f"  np 池每层天数 中位 {np.median(npz):.0f}  P10 {np.quantile(npz,.1):.0f}  —— 无回退")

nc = [r["null"][a]["med_cb"] for r in R for a in r["null"] if "med_cb" in r["null"][a]]
no = [r["null"][a]["med_own"] for r in R for a in r["null"] if "med_own" in r["null"][a]]
print(f"\n  经验零中位：cb {np.median(nc):.3f}（合并全部对照组）· own {np.median(no):.3f}")
print("  cb 口径下随机触发集的期望倍数不是 1.0，而是约 1.47 —— 判据「下界 > 1.0」在 cb 下失效")
per = {}
for a in ["and_base", "price_eq", "or_eq", "vol_eq", "price_base", "vol_base", "or_base"]:
    v = [r["null"][a]["med_cb"] for r in R if a in r["null"] and "med_cb" in r["null"][a]]
    per[a] = (np.median(v), np.quantile(v, .1), np.quantile(v, .9))
print(f"\n  {'对照组':<18}{'零中位':>8}{'P10':>8}{'P90':>8}")
for a, (m, lo, hi) in per.items():
    print(f"  {CN[a]:<18}{m:>8.3f}{lo:>8.3f}{hi:>8.3f}")
spread = max(m for m, _, _ in per.values()) - min(m for m, _, _ in per.values())
print(f"  各对照组之间零点最大差 {spread:.3f} —— 零点几乎与对照组无关，故 cb 适合做 arm 间相对比较")

# ------------------------------------------------------- ② 三套分母一致性
hdr("② 三套分母的一致性：哪些结论 own / cb / np 同号且显著")
def paired(rows, a, b, key):
    o = []
    for r in rows:
        x, y = r["arms"].get(a, {}), r["arms"].get(b, {})
        if x.get(key) is not None and y.get(key) is not None: o.append(x[key]-y[key])
    return np.array(o)

print(f"  {'对照（AND − 对照）':<22}" + "".join(f"{t:>26}" for t in ("own 自身净化", "cb 共用净化", "np 不净化")) + "   判定")
VERD = {}
for o in ["price_base", "or_base", "vol_base", "price_eq", "vol_eq", "or_eq", "or_scale", "price_eqblk"]:
    cells, sig, sgns = [], [], []
    for key in ("mult", "mult_cb", "mult_np"):
        d = paired(R, "and_base", o, key)
        med, lo, hi = bmed(d); k, n, fr, p = sgn(d)
        star = "*" if (lo > 0 or hi < 0) and p < .05 else " "
        cells.append(f"{med:>+8.3f}[{lo:+.2f},{hi:+.2f}]{fr:>5.0%}{star}")
        sig.append((lo > 0 or hi < 0) and p < .05); sgns.append(np.sign(med))
    if len(set(sgns)) > 1: v = "⚠️ 符号随分母翻转"
    elif all(sig): v = "三套一致显著"
    elif not any(sig): v = "三套均不显著"
    else: v = f"仅 {sum(sig)}/3 显著"
    VERD[o] = v
    print(f"  {CN[o]:<22}" + "".join(f"{c:>26}" for c in cells) + f"   {v}")
print("\n  * = 95% 自助区间不含 0 且符号检验 p<0.05；百分比为 AND 赢的比例")

# ------------------------------------------------------- ③ 切半稳定性
hdr("③ 切半稳定性（族级结论：配对差在前后两半是否同号、量级是否相近）")
print(f"  {'对照':<22}{'分母':<6}{'前半 配对差':>22}{'后半 配对差':>22}{'同号':>6}")
for o in ["price_eq", "or_eq", "price_eqblk"]:
    for nm in ("cb", "np"):
        d1, d2 = [], []
        for s, r in S.items():
            h1, h2 = r["half"].get("h1", {}), r["half"].get("h2", {})
            if f"and_base_{nm}" in h1 and f"{o}_{nm}" in h1: d1.append(h1[f"and_base_{nm}"]-h1[f"{o}_{nm}"])
            if f"and_base_{nm}" in h2 and f"{o}_{nm}" in h2: d2.append(h2[f"and_base_{nm}"]-h2[f"{o}_{nm}"])
        m1, l1, u1 = bmed(d1); m2, l2, u2 = bmed(d2)
        k1, n1, f1, p1 = sgn(d1); k2, n2, f2, p2 = sgn(d2)
        same = "是" if np.sign(m1) == np.sign(m2) else "否"
        print(f"  {CN[o]:<22}{nm:<6}{m1:>+8.3f}[{l1:+.2f},{u1:+.2f}]{f1:>5.0%}"
              f"{m2:>+8.3f}[{l2:+.2f},{u2:+.2f}]{f2:>5.0%}{same:>6}")

# ------------------------------------------------------- price_eqblk 的零与特异性
hdr("②b 等块数对照组的经验零与安慰剂特异性（补主表未算的部分）")
EX = {}
for a in ["and_base", "price_eqblk"]:
    exc, spec = [], []
    for s, r in S.items():
        e = r["extra"].get(a, {})
        pl = e.get("placebo", {})
        if "0" not in pl or e.get("null_med") is None: continue
        far = [pl[k] for k in ("-40", "-30", "-20", "-15", "15", "20", "30", "40") if k in pl]
        if len(far) < 4: continue
        exc.append((s, pl["0"] - e["null_med"]))
        spec.append((s, pl["0"] - float(np.median(far))))
    EX[a] = (dict(exc), dict(spec))
    m1, l1, u1 = bmed([x for _, x in exc]); m2, l2, u2 = bmed([x for _, x in spec])
    print(f"  {CN[a]:<18} 扣零超额 {m1:.3f} [{l1:.3f},{u1:.3f}]   安慰剂特异性 {m2:.3f} [{l2:.3f},{u2:.3f}]")
for i, nm in ((0, "扣零超额"), (1, "安慰剂特异性")):
    com = [s for s in EX["and_base"][i] if s in EX["price_eqblk"][i]]
    d = np.array([EX["and_base"][i][s] - EX["price_eqblk"][i][s] for s in com])
    m, l, u = bmed(d); k, n, fr, p = sgn(d)
    print(f"  配对 AND − 等块数 · {nm}: {m:+.3f} [{l:+.3f},{u:+.3f}] AND 赢 {fr:.1%} ({k}/{n}) p={p:.4f}")
