"""汇总分析：分母一致性 · 配对显著性 · 功效 · 经验零 · 安慰剂 · 差集 · 分层 · 告警量"""
import json, os, sys, itertools
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
R = [r for r in json.load(open(os.path.join(HERE, "res.json"))) if "error" not in r]
EQ = [r for r in R if r["asset"] != "crypto"]
CR = [r for r in R if r["asset"] == "crypto"]
RNG = np.random.default_rng(7)

ARMS = ["and_base", "price_base", "vol_base", "or_base",
        "price_eq", "vol_eq", "or_eq", "or_scale", "price_eqblk",
        "price_only", "vol_only"]
CN = {"and_base": "双确认 AND", "price_base": "仅价格 等阈值", "vol_base": "仅量能 等阈值",
      "or_base": "价格 OR 量能", "price_eq": "仅价格 等触发数", "vol_eq": "仅量能 等触发数",
      "or_eq": "OR 等触发数", "or_scale": "OR 等比例放大", "price_eqblk": "仅价格 等块数",
      "price_only": "价格中·量能未中", "vol_only": "量能中·价格未中"}


def col(rows, arm, key):
    out = []
    for r in rows:
        a = r["arms"].get(arm, {})
        if key in a and a[key] is not None:
            out.append((r["sym"], a[key]))
    return out


def paired(rows, a, b, key):
    o = []
    for r in rows:
        x, y = r["arms"].get(a, {}), r["arms"].get(b, {})
        if x.get(key) is not None and y.get(key) is not None:
            o.append((r["sym"], x[key], y[key]))
    return o


def boot_med_ci(x, nboot=20000):
    x = np.asarray(x, float)
    idx = RNG.integers(0, len(x), size=(nboot, len(x)))
    m = np.median(x[idx], axis=1)
    m.sort()
    return float(np.median(x)), float(m[int(.025 * nboot)]), float(m[int(.975 * nboot)])


def sign_test(diffs):
    d = np.asarray(diffs, float)
    d = d[d != 0]
    k = int((d > 0).sum()); n = len(d)
    p = stats.binomtest(k, n, 0.5).pvalue
    ci = stats.binomtest(k, n, 0.5).proportion_ci(0.95)
    return k, n, k / n, p, (ci.low, ci.high)


def hdr(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)


# ---------------------------------------------------------------- §1 分母
hdr("§1  三套分母下的跨标的中位倍数（113 只）")
print(f"{'对照组':<18}{'own 自身净化':>14}{'cb 共用净化':>14}{'np 不净化':>14}"
      f"{'own 基准池日数':>16}{'own 基准中位':>14}")
for a in ARMS:
    row = []
    for k in ("mult", "mult_cb", "mult_np"):
        v = [x for _, x in col(R, a, k)]
        row.append(np.median(v) if v else float("nan"))
    nb = [x for _, x in col(R, a, "nbase")]
    bm = [x for _, x in col(R, a, "base_med")]
    print(f"{CN[a]:<18}{row[0]:>14.3f}{row[1]:>14.3f}{row[2]:>14.3f}"
          f"{np.median(nb):>16.0f}{np.median(bm):>14.5f}")

hdr("§1b 净化抽薄的程度（own 口径下基准池剩余日数 / 全部有效日）")
for a in ["and_base", "price_eq", "price_base", "or_base"]:
    fr = []
    for r in R:
        x = r["arms"].get(a, {})
        if x.get("nbase") and x.get("nbase_np"):
            fr.append(x["nbase"] / x["nbase_np"])
    print(f"{CN[a]:<18}保留比例 中位 {np.median(fr):.3f}  P10 {np.quantile(fr,.1):.3f}  "
          f"P90 {np.quantile(fr,.9):.3f}")

hdr("§1c 划分自洽性检验：等阈值下 仅价格 = 双确认 ⊎ 价格中·量能未中\n"
    "    同一分母时，仅价格的中位必落在两个子集中位之间。own 口径下若违反，说明分母不可比")
for tag, key in (("own 自身净化", "mult"), ("cb 共用净化", "mult_cb"), ("np 不净化", "mult_np")):
    bad = 0; tot = 0
    for r in R:
        A = r["arms"].get("and_base", {}).get(key)
        P = r["arms"].get("price_base", {}).get(key)
        O = r["arms"].get("price_only", {}).get(key)
        if None in (A, P, O): continue
        tot += 1
        if not (min(A, O) - 1e-9 <= P <= max(A, O) + 1e-9): bad += 1
    print(f"  {tag:<12} 违反 {bad}/{tot}  ({bad/tot:.1%})")

# ---------------------------------------------------------------- §2 主对照
def compare(rows, base, other, key, label):
    p = paired(rows, base, other, key)
    if not p: return None
    d = np.array([x - y for _, x, y in p])
    med, lo, hi = boot_med_ci(d)
    k, n, frac, pv, ci = sign_test(d)
    try:
        w = stats.wilcoxon(d).pvalue
    except Exception:
        w = float("nan")
    mb = np.median([x for _, x, _ in p]); mo = np.median([y for _, _, y in p])
    print(f"  {label:<26}{mb:>7.3f}{mo:>8.3f}{med:>9.3f} [{lo:6.3f},{hi:6.3f}]"
          f"{frac:>8.1%} ({k}/{n}) p={pv:.3f}  W p={w:.4f}")
    return dict(diff_med=med, lo=lo, hi=hi, win=frac, n=n, p_sign=pv, p_w=w, sd=float(d.std(ddof=1)))


for tag, key in (("own 自身净化（R34 口径）", "mult"), ("cb 共用净化", "mult_cb"), ("np 不净化", "mult_np")):
    hdr(f"§2  双确认 vs 各对照组 · {tag}")
    print(f"  {'对照':<26}{'AND':>7}{'对照':>8}{'配对差中位':>9} {'95% 自助区间':>16}"
          f"{'AND 赢':>10}   符号检验 / Wilcoxon")
    store = {}
    for o in ["price_base", "or_base", "vol_base", "price_eq", "vol_eq", "or_eq",
              "or_scale", "price_eqblk"]:
        store[o] = compare(R, "and_base", o, key, CN[o])
    if key == "mult_cb":
        CB_STORE = store

# ---------------------------------------------------------------- §3 功效
hdr("§3  功效分析（配对差 · 共用净化分母 · n = 113）")
for o in ["price_eq", "or_eq", "price_base", "or_base"]:
    p = paired(R, "and_base", o, "mult_cb")
    d = np.array([x - y for _, x, y in p])
    n = len(d); sd = d.std(ddof=1)
    # 配对 t 的最小可检出差（80% 功效，双侧 5%）
    mde_t = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * sd / np.sqrt(n)
    # 中位数的自助标准误
    idx = RNG.integers(0, n, size=(20000, n))
    se_med = float(np.median(d[idx], axis=1).std(ddof=1))
    mde_med = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * se_med
    # 符号检验能检出的最小胜率
    lo_p = 0.5
    for pp in np.arange(0.50, 0.85, 0.005):
        # 正态近似功效
        se0 = 0.5 / np.sqrt(n); se1 = np.sqrt(pp * (1 - pp) / n)
        pw = 1 - stats.norm.cdf((stats.norm.ppf(0.975) * se0 - (pp - 0.5)) / se1)
        if pw >= 0.80: lo_p = pp; break
    print(f"  AND − {CN[o]:<20} sd(配对差) {sd:.3f}  "
          f"均值口径 MDE {mde_t:+.3f}  中位口径 MDE {mde_med:+.3f}  "
          f"符号检验 80% 功效需胜率 ≥ {lo_p:.1%}")
base_lvl = np.median([x for _, x in col(R, "and_base", "mult_cb")])
print(f"  参考基数：双确认倍数中位 {base_lvl:.3f}（共用净化口径）")

# ---------------------------------------------------------------- §4 经验零
hdr("§4  经验零（触发集环形平移 · 保 n 保块结构 · 破时间对齐）")
print(f"{'对照组':<18}{'零倍数中位 cb':>16}{'零 95 分位 cb':>16}"
      f"{'零倍数中位 own':>17}{'判据假阳性率 own':>18}{'实测通过比例':>14}")
NULLTAB = {}
for a in ["and_base", "price_eq", "vol_eq", "or_eq", "price_base", "vol_base", "or_base"]:
    mc = [r["null"][a]["med_cb"] for r in R if a in r.get("null", {}) and "med_cb" in r["null"][a]]
    mo = [r["null"][a]["med_own"] for r in R if a in r.get("null", {}) and "med_own" in r["null"][a]]
    q95 = [r["null"][a]["q95_cb"] for r in R if a in r.get("null", {}) and "q95_cb" in r["null"][a]]
    pr = [r["null"][a]["pass_rate"] for r in R if a in r.get("null", {}) and r["null"][a].get("pass_rate") is not None]
    obs = [x for _, x in col(R, a, "passed")]
    NULLTAB[a] = dict(null_med_cb=np.median(mc), null_med_own=np.median(mo),
                      fp=np.mean(pr), obs=np.mean(obs))
    print(f"{CN[a]:<18}{np.median(mc):>16.3f}{np.median(q95):>16.3f}"
          f"{np.median(mo):>17.3f}{np.mean(pr):>18.1%}{np.mean(obs):>14.1%}")

hdr("§4b 扣掉经验零之后的超额（逐标的：实测倍数 − 该标的该对照组的零中位）")
print(f"{'对照组':<18}{'超额中位 cb':>14}{'95% 自助区间':>20}")
EXC = {}
for a in ["and_base", "price_eq", "vol_eq", "or_eq", "price_base", "vol_base", "or_base"]:
    v = []
    for r in R:
        m = r["arms"].get(a, {}).get("mult_cb"); nz = r.get("null", {}).get(a, {}).get("med_cb")
        if m is not None and nz is not None: v.append((r["sym"], m - nz))
    EXC[a] = {s: x for s, x in v}
    med, lo, hi = boot_med_ci([x for _, x in v])
    print(f"{CN[a]:<18}{med:>14.3f}   [{lo:.3f}, {hi:.3f}]")

hdr("§4c 超额的配对比较（AND − 对照）")
for o in ["price_eq", "or_eq", "price_base", "or_base"]:
    common = [s for s in EXC["and_base"] if s in EXC[o]]
    d = np.array([EXC["and_base"][s] - EXC[o][s] for s in common])
    med, lo, hi = boot_med_ci(d)
    k, n, frac, pv, _ = sign_test(d)
    print(f"  AND − {CN[o]:<20} 配对差中位 {med:+.3f} [{lo:+.3f},{hi:+.3f}]  "
          f"AND 赢 {frac:.1%} ({k}/{n}) p={pv:.3f}")

# ---------------------------------------------------------------- §5 安慰剂
hdr("§5  安慰剂平移（共用净化分母 cb · 跨标的中位）")
KS = ["-40", "-30", "-20", "-15", "-10", "-8", "-6", "0", "6", "8", "10", "15", "20", "30", "40"]
print(f"{'对照组':<18}" + "".join(f"{k:>7}" for k in KS))
PL = {}
for a in ["and_base", "price_eq", "or_eq", "price_base", "vol_base", "or_base"]:
    line, vals = [], {}
    for k in KS:
        v = [r["placebo"][a][k]["cb"] for r in R
             if a in r.get("placebo", {}) and k in r["placebo"][a] and "cb" in r["placebo"][a][k]]
        vals[k] = np.median(v) if v else float("nan")
        line.append(f"{vals[k]:>7.3f}" if v else f"{'—':>7}")
    PL[a] = vals
    print(f"{CN[a]:<18}" + "".join(line))

hdr("§5b 特异性 = 倍数(k=0) − 该对照组远端安慰剂中位(|k| ≥ 15)，逐标的算")
print(f"{'对照组':<18}{'特异性中位':>12}{'95% 自助区间':>20}{'>0 比例':>10}")
SPEC = {}
for a in ["and_base", "price_eq", "or_eq", "price_base", "vol_base", "or_base"]:
    v = []
    for r in R:
        p = r.get("placebo", {}).get(a, {})
        if "0" not in p or "cb" not in p["0"]: continue
        far = [p[k]["cb"] for k in ("-40", "-30", "-20", "-15", "15", "20", "30", "40")
               if k in p and "cb" in p[k]]
        if len(far) < 4: continue
        v.append((r["sym"], p["0"]["cb"] - float(np.median(far))))
    SPEC[a] = {s: x for s, x in v}
    med, lo, hi = boot_med_ci([x for _, x in v])
    print(f"{CN[a]:<18}{med:>12.3f}   [{lo:.3f}, {hi:.3f}]{np.mean([x>0 for _,x in v]):>10.1%}")

hdr("§5c 特异性的配对比较（AND − 对照）")
for o in ["price_eq", "or_eq", "price_base", "or_base"]:
    common = [s for s in SPEC["and_base"] if s in SPEC[o]]
    d = np.array([SPEC["and_base"][s] - SPEC[o][s] for s in common])
    med, lo, hi = boot_med_ci(d)
    k, n, frac, pv, _ = sign_test(d)
    print(f"  AND − {CN[o]:<20} 配对差中位 {med:+.3f} [{lo:+.3f},{hi:+.3f}]  "
          f"AND 赢 {frac:.1%} ({k}/{n}) p={pv:.3f}")

# ---------------------------------------------------------------- §6 差集
hdr("§6  差集验证（等阈值 · 共用净化分母）")
for tag, key in (("own 自身净化", "mult"), ("cb 共用净化", "mult_cb"), ("np 不净化", "mult_np")):
    a = np.median([x for _, x in col(R, "and_base", key)])
    po = np.median([x for _, x in col(R, "price_only", key)])
    pb = np.median([x for _, x in col(R, "price_base", key)])
    vo = np.median([x for _, x in col(R, "vol_only", key)])
    print(f"  {tag:<12} 双确认 {a:.3f} | 价格中·量能未中 {po:.3f} | 仅价格全集 {pb:.3f} "
          f"| 量能中·价格未中 {vo:.3f}")
p = paired(R, "and_base", "price_only", "mult_cb")
d = np.array([x - y for _, x, y in p])
med, lo, hi = boot_med_ci(d)
k, n, frac, pv, _ = sign_test(d)
print(f"\n  配对：双确认 − 价格中·量能未中 = {med:+.3f} [{lo:+.3f},{hi:+.3f}] "
      f"AND 赢 {frac:.1%} ({k}/{n}) p={pv:.4f}")
nn = [(r["arms"]["and_base"]["n"], r["arms"]["price_only"]["n"]) for r in R]
print(f"  样本占比：双确认在仅价格全集中占 中位 "
      f"{np.median([a/(a+b) for a,b in nn]):.1%}")

# ---------------------------------------------------------------- §7 分层
hdr("§7  分层（共用净化分母 · AND vs 仅价格等触发数 / vs OR 等触发数）")


def strat(rows, name):
    out = []
    for o in ["price_eq", "or_eq"]:
        p = paired(rows, "and_base", o, "mult_cb")
        if len(p) < 4: continue
        d = np.array([x - y for _, x, y in p])
        k, n, frac, pv, ci = sign_test(d)
        out.append(f"{CN[o]}: 差 {np.median(d):+.3f} 赢 {frac:.0%} ({k}/{n}) p={pv:.3f}")
    print(f"  {name:<26} " + "  |  ".join(out))


strat(R, f"全部 ({len(R)})")
strat(EQ, f"美股 ({len(EQ)})")
strat(CR, f"加密 ({len(CR)})")
for key, vals in (("vol_tier", ["低波 <25%", "中波 25-50%", "高波 >50%"]),
                  ("size_tier", ["large", "mid", "small"])):
    for v in vals:
        sub = [r for r in R if r[key] == v]
        if len(sub) >= 4: strat(sub, f"{key}={v} ({len(sub)})")
secs = sorted({r["sector"] for r in EQ})
for s in secs:
    sub = [r for r in EQ if r["sector"] == s]
    if len(sub) >= 4: strat(sub, f"行业 {s} ({len(sub)})")
for lab, f in (("历史 <5 年", lambda r: r["years"] < 5),
               ("历史 5-8 年", lambda r: 5 <= r["years"] < 8),
               ("历史 ≥8 年", lambda r: r["years"] >= 8)):
    sub = [r for r in R if f(r)]
    if len(sub) >= 4: strat(sub, f"{lab} ({len(sub)})")

hdr("§7b 加密 25 只逐只（AND − 仅价格等触发数，共用净化分母）")
p = paired(CR, "and_base", "price_eq", "mult_cb")
for s, x, y in sorted(p, key=lambda t: t[1] - t[2]):
    print(f"  {s:<8} AND {x:6.3f}  仅价格 {y:6.3f}  差 {x-y:+.3f}")
d = np.array([x - y for _, x, y in p])
k, n, frac, pv, ci = sign_test(d)
print(f"  加密合计 赢 {frac:.1%} ({k}/{n}) p={pv:.3f} 95%胜率区间 [{ci[0]:.2f},{ci[1]:.2f}]")
# 美股 vs 加密 的分化是否显著
de = np.array([x - y for _, x, y in paired(EQ, "and_base", "price_eq", "mult_cb")])
print(f"  美股配对差中位 {np.median(de):+.3f} (n={len(de)}) vs 加密 {np.median(d):+.3f} (n={len(d)}) "
      f"Mann-Whitney p={stats.mannwhitneyu(de,d).pvalue:.3f}")

# ---------------------------------------------------------------- §8 告警量
hdr("§8  告警量代价（等阈值口径）")
rat_or, rat_p, rat_orb, rat_pb = [], [], [], []
for r in R:
    A, P, O = r["arms"]["and_base"], r["arms"]["price_base"], r["arms"]["or_base"]
    rat_or.append(O["n"] / A["n"]); rat_p.append(P["n"] / A["n"])
    rat_orb.append(O["blocks"] / A["blocks"]); rat_pb.append(P["blocks"] / A["blocks"])
for nm, v in (("OR / AND 触发日数", rat_or), ("仅价格 / AND 触发日数", rat_p),
              ("OR / AND 告警场次(块)", rat_orb), ("仅价格 / AND 告警场次(块)", rat_pb)):
    print(f"  {nm:<24} 中位 {np.median(v):.2f}×  P10 {np.quantile(v,.1):.2f}×  "
          f"P90 {np.quantile(v,.9):.2f}×  最大 {max(v):.2f}×")
fr_and = [r["arms"]["and_base"]["freq"] for r in R]
fr_or = [r["arms"]["or_base"]["freq"] for r in R]
fr_p = [r["arms"]["price_base"]["freq"] for r in R]
print(f"\n  年触发次数中位   AND {np.median(fr_and):.1f}  仅价格 {np.median(fr_p):.1f}  "
      f"OR {np.median(fr_or):.1f}")
print(f"  假设 5 只组合    AND {np.median(fr_and)*5/52:.1f} 次/周  "
      f"仅价格 {np.median(fr_p)*5/52:.1f} 次/周  OR {np.median(fr_or)*5/52:.1f} 次/周")

# ---------------------------------------------------------------- §9 样本外校准
hdr("§9  等触发数校准是否引入了前视（前半段定阈值 → 后半段比）")
rows = []
for r in R:
    o = r.get("oos", {})
    if all(k in o for k in ("and_h2", "price_oos_h2", "price_is_h2")):
        rows.append((r["sym"], o["and_h2"]["mult_cb"], o["price_oos_h2"]["mult_cb"],
                     o["price_is_h2"]["mult_cb"], o["thr_oos"], o["thr_is"]))
d_oos = np.array([a - b for _, a, b, c, _, _ in rows])
d_is = np.array([a - c for _, a, b, c, _, _ in rows])
for nm, d in (("后半段 · 阈值来自前半段（样本外）", d_oos),
              ("后半段 · 阈值来自后半段（样本内）", d_is)):
    med, lo, hi = boot_med_ci(d)
    k, n, frac, pv, _ = sign_test(d)
    print(f"  {nm:<34} AND−仅价格 {med:+.3f} [{lo:+.3f},{hi:+.3f}] "
          f"AND 赢 {frac:.1%} ({k}/{n}) p={pv:.3f}")
thr = np.array([(a, b) for *_, a, b in [(x[4], x[5]) for x in rows]])
print(f"  阈值稳定性：前半段定的 θz' 中位 {np.median(thr[:,0]):.3f}，"
      f"后半段自定 {np.median(thr[:,1]):.3f}，"
      f"逐标的绝对差中位 {np.median(np.abs(thr[:,0]-thr[:,1])):.3f}")

# ---------------------------------------------------------------- §10 判据通过比例
hdr("§10 判据通过比例（下界 > 1.0 且块数 ≥ 5）")
print(f"{'对照组':<18}{'own 口径':>12}{'cb 口径':>12}{'np 口径':>12}{'own 假阳性':>12}"
      f"{'零调整后':>12}")
for a in ["and_base", "price_eq", "vol_eq", "or_eq", "price_base", "vol_base", "or_base"]:
    pw = {k: np.mean([x for _, x in col(R, a, k)]) for k in ("passed", "passed_cb", "passed_np")}
    fp = NULLTAB[a]["fp"]
    adj = (pw["passed"] - fp) / (1 - fp)
    print(f"{CN[a]:<18}{pw['passed']:>12.1%}{pw['passed_cb']:>12.1%}{pw['passed_np']:>12.1%}"
          f"{fp:>12.1%}{adj:>12.1%}")

json.dump({"null": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in NULLTAB.items()}},
          open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1)
