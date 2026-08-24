"""M16 持仓敏感度映射 · 扩池重做。

分组：利率敏感（金融 · 房地产 · 公用事业，26 只）vs 其余（65 只）
     另按 beta 中位二分 / 三分位

两个检验：
  ① 逐日配对（主）：每个发布日算「A 组归一化 V 均值 − B 组归一化 V 均值」，
                    对发布日整块自助 → 组间差值的 95% 区间。跨标的相关性由日内截面平均吸收
  ② 标的层（次）：组间「相对基准倍数」均值差 + 置换检验。忽略截面相关，区间偏窄，只作参照
"""
import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
UNI = "/Users/ming/project/alva/backtest/universe/universe.csv"
SEED = 20260819
NB = 4000
NPERM = 20000

RATE_SENS = {"金融", "房地产", "公用事业"}
EVENTS = ["CPI_T0", "CPI_T-1", "CORE_CPI_T0", "NFP_T0", "NFP_T-1", "GDP_T0", "FEDFUNDS_T0"]
LABEL = {"CPI_T0": "物价 发布当日", "CPI_T-1": "物价 发布前1日", "CORE_CPI_T0": "核心物价 发布当日",
         "NFP_T0": "就业 发布当日", "NFP_T-1": "就业 发布前1日",
         "GDP_T0": "产出 发布当日", "FEDFUNDS_T0": "有效联邦基金利率 发布当日"}

per = json.load(open(f"{OUT}/core.json"))
norms = json.load(open(f"{OUT}/norms.json"))
U = {r["symbol"]: r for r in csv.DictReader(open(UNI))}
STOCKS = [s for s, r in U.items() if r["asset_class"] == "us_equity" and s != "SPY"]
STOCKS = [s for s in STOCKS if s in per and "_err" not in per[s]]
CRYPTO = [s for s, r in U.items() if r["asset_class"] == "crypto" and s in per and "_err" not in per[s]]


def beta(s):
    b = U[s]["beta"]
    return float(b) if b else None


def mult(sym, ev):
    r = per.get(sym, {}).get(ev)
    return r["mult"] if r else None


def day_paired(A, B, ev, seed=SEED, nb=NB):
    """逐日配对：每个事件日 mean(A 归一化 V) − mean(B 归一化 V)，整块自助（事件日间隔 ≥ 20 天，各自成块）"""
    days = sorted(set().union(*[set(norms.get(s, {}).get(ev, {})) for s in A + B]) )
    diffs, na, nb_ = [], [], []
    for d in days:
        a = [norms[s][ev][d] for s in A if d in norms.get(s, {}).get(ev, {})]
        b = [norms[s][ev][d] for s in B if d in norms.get(s, {}).get(ev, {})]
        if len(a) >= 3 and len(b) >= 3:
            diffs.append(np.mean(a) - np.mean(b)); na.append(len(a)); nb_.append(len(b))
    if len(diffs) < 5:
        return None
    diffs = np.array(diffs)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diffs), (nb, len(diffs)))
    rep_mean = np.sort(diffs[idx].mean(axis=1))
    rep_med = np.sort(np.median(diffs[idx], axis=1))
    t = stats.wilcoxon(diffs) if len(diffs) >= 10 else None
    return dict(ndays=len(diffs), mean=float(diffs.mean()),
                mean_lo=float(rep_mean[int(.025 * nb)]), mean_hi=float(rep_mean[int(.975 * nb)]),
                med=float(np.median(diffs)),
                med_lo=float(rep_med[int(.025 * nb)]), med_hi=float(rep_med[int(.975 * nb)]),
                p_wilcoxon=float(t.pvalue) if t is not None else None,
                nA=float(np.mean(na)), nB=float(np.mean(nb_)))


def stock_level(A, B, ev, seed=SEED):
    a = np.array([mult(s, ev) for s in A if mult(s, ev) is not None])
    b = np.array([mult(s, ev) for s in B if mult(s, ev) is not None])
    if len(a) < 3 or len(b) < 3:
        return None
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(NPERM):
        rng.shuffle(pool)
        if abs(pool[:len(a)].mean() - pool[len(a):].mean()) >= abs(obs):
            cnt += 1
    # 组间差的自助区间（标的层重抽，忽略截面相关 → 偏窄）
    ia = rng.integers(0, len(a), (NB, len(a))); ib = rng.integers(0, len(b), (NB, len(b)))
    rep = np.sort(a[ia].mean(axis=1) - b[ib].mean(axis=1))
    return dict(nA=len(a), nB=len(b), mA=float(a.mean()), mB=float(b.mean()),
                medA=float(np.median(a)), medB=float(np.median(b)),
                diff=float(obs), lo=float(rep[int(.025 * NB)]), hi=float(rep[int(.975 * NB)]),
                p_perm=cnt / NPERM,
                passA=int(sum(1 for s in A if (per[s].get(ev) or {}).get("pass_"))),
                passB=int(sum(1 for s in B if (per[s].get(ev) or {}).get("pass_"))))


def show(title, A, B, tagA, tagB):
    print(f"\n{'='*100}\n{title}   {tagA} n={len(A)} · {tagB} n={len(B)}\n{'='*100}")
    print(f"{'事件':22s} {tagA+' 中位':>10s} {tagB+' 中位':>10s} {'差(标的层)':>12s} {'95%区间':>18s} {'置换p':>7s} "
          f"| {'逐日配对差':>10s} {'95%区间':>18s} {'Wilcoxon p':>10s} {'日数':>5s}")
    rows = {}
    for ev in EVENTS:
        sl = stock_level(A, B, ev)
        dp = day_paired(A, B, ev)
        if sl is None:
            continue
        rows[ev] = dict(stock=sl, day=dp)
        d = (f"{dp['mean']:+10.4f} [{dp['mean_lo']:+.4f},{dp['mean_hi']:+.4f}] {dp['p_wilcoxon']:10.3f} {dp['ndays']:5d}"
             if dp else " " * 40)
        print(f"{LABEL[ev]:22s} {sl['medA']:10.3f} {sl['medB']:10.3f} {sl['diff']:+12.4f} "
              f"[{sl['lo']:+.3f},{sl['hi']:+.3f}] {sl['p_perm']:7.3f} | {d}")
    return rows


if __name__ == "__main__":
    A = [s for s in STOCKS if U[s]["sector"] in RATE_SENS]
    B = [s for s in STOCKS if U[s]["sector"] not in RATE_SENS]
    out = {}
    print(f"利率敏感组：{' '.join(sorted(A))}")
    out["sector"] = show("① 部门分组 · 利率敏感（金融/房地产/公用事业） vs 其余", A, B, "利率敏感", "其余")

    bs = sorted([s for s in STOCKS if beta(s) is not None], key=beta)
    md = np.median([beta(s) for s in bs])
    HB = [s for s in bs if beta(s) > md]; LB = [s for s in bs if beta(s) <= md]
    out["beta_median"] = show(f"② beta 中位二分（分界 {md:.3f}）", HB, LB, "高beta", "低beta")

    T3 = bs[int(len(bs) * 2 / 3):]; B3 = bs[:int(len(bs) / 3)]
    out["beta_tercile"] = show(f"③ beta 三分位极端组（高 {beta(T3[0]):.2f}+ vs 低 {beta(B3[-1]):.2f}−）",
                               T3, B3, "beta前1/3", "beta后1/3")

    RG = [s for s in STOCKS if beta(s) is not None and beta(s) > 1.2]
    RL = [s for s in STOCKS if beta(s) is not None and beta(s) <= 1.2]
    out["registry"] = show(f"④ registry 原判定（beta > 1.2 = 高敏感）", RG, RL, "高敏感", "低敏感")

    out["crypto"] = show("⑤ 加密 vs 美股（registry 把加密整体判为高敏感）", CRYPTO, STOCKS, "加密", "美股")

    # 逐部门
    print(f"\n{'='*100}\n逐部门中位相对基准倍数（n = 该部门标的数）\n{'='*100}")
    secs = sorted(set(U[s]["sector"] for s in STOCKS))
    print(f"{'部门':10s} {'n':>3s} " + " ".join(f"{LABEL[e][:8]:>10s}" for e in EVENTS))
    sec_tab = {}
    for sec in secs:
        ss = [s for s in STOCKS if U[s]["sector"] == sec]
        row = []
        for e in EVENTS:
            v = [mult(s, e) for s in ss if mult(s, e) is not None]
            row.append(float(np.median(v)) if v else None)
        sec_tab[sec] = row
        print(f"{sec:10s} {len(ss):3d} " + " ".join(f"{x:10.3f}" if x else " " * 10 for x in row))
    out["sector_table"] = sec_tab

    # beta 与倍数的秩相关
    print(f"\n{'='*100}\nbeta 与相对基准倍数的 Spearman 相关（n = 91 只美股）\n{'='*100}")
    corr = {}
    for e in EVENTS:
        x = [beta(s) for s in STOCKS if beta(s) is not None and mult(s, e) is not None]
        y = [mult(s, e) for s in STOCKS if beta(s) is not None and mult(s, e) is not None]
        r, p = stats.spearmanr(x, y)
        rp, pp = stats.pearsonr(x, y)
        corr[e] = dict(rho=float(r), p=float(p), n=len(x), pearson=float(rp), p_pearson=float(pp))
        print(f"{LABEL[e]:22s} n={len(x):3d}  Spearman {r:+.3f} (p={p:.3f})   Pearson {rp:+.3f} (p={pp:.3f})")
    out["corr"] = corr
    json.dump(out, open(f"{OUT}/m16.json", "w"), ensure_ascii=False, indent=1)
