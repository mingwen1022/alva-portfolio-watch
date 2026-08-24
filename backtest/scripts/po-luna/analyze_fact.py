"""核心问题：P_fact vs P_rhet —— 事实性与表态性言论的市场确认率是否分化。

分化 → PO1 的「事实性直推」成立，保留 M18
不分化 → 删掉 M18，PO 族退化为纯规则 + 市场确认

读法三件套（缺一不可）：
  ① 与「随机时刻的确认率」这个底数比 —— 判据 |AR_z|≥2 OR RVOL≥2 本身就有 12–27% 的无条件触发率
  ② 差值的区间用**按 session 日分块**的自助 —— 同一天的帖子共用市场结果，不能当独立样本
  ③ 分层报 —— 官方+当事人 18 账号 / 央行 4 / 媒体 7；媒体是二手转述，t0 不可靠
"""
import os, sys, json, gzip
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")
SEED = 20260819
NBOOT = 4000


def load():
    lab = json.load(gzip.open(f"{DERIV}/m18_labels.json.gz", "rt", encoding="utf-8"))
    meta = json.load(gzip.open(f"{DERIV}/llm_meta.json.gz", "rt", encoding="utf-8"))
    conf = {r["cid"]: r for r in json.load(gzip.open(f"{DERIV}/confirm.json.gz", "rt", encoding="utf-8"))}
    out = []
    for o in lab:
        cid = o["id"]
        if cid not in meta or cid not in conf:
            continue
        r = dict(o)
        r.update(meta[cid])
        r["conf"] = conf[cid]
        out.append(r)
    return out


def boot_diff(rows, key, seed=SEED, nboot=NBOOT):
    """按 session 日分块自助：返回 (p_fact, p_rhet, diff, diff_lo, diff_hi, n_f, n_r, 块数)"""
    dat = []
    for r in rows:
        c = r["conf"].get(key)
        if not c:
            continue
        dat.append((c["day"], 1 if r["specificity"] == "factual" else 0, 1 if c["c"] else 0))
    if not dat:
        return None
    days = sorted({d for d, _, _ in dat})
    byday = {d: [] for d in days}
    for d, f, c in dat:
        byday[d].append((f, c))
    nf = sum(f for _, f, _ in dat); nr = len(dat) - nf
    pf = np.mean([c for _, f, c in dat if f]) if nf else np.nan
    pr = np.mean([c for _, f, c in dat if not f]) if nr else np.nan
    rng = np.random.default_rng(seed)
    D = len(days)
    diffs = []
    for _ in range(nboot):
        pick = rng.integers(0, D, D)
        F, R = [], []
        for i in pick:
            for f, c in byday[days[i]]:
                (F if f else R).append(c)
        if len(F) >= 5 and len(R) >= 5:
            diffs.append(np.mean(F) - np.mean(R))
    diffs = np.sort(np.array(diffs))
    if len(diffs) < 100:
        return dict(p_fact=pf, p_rhet=pr, diff=pf - pr, lo=np.nan, hi=np.nan,
                    n_f=nf, n_r=nr, blocks=D, nboot_ok=len(diffs))
    return dict(p_fact=float(pf), p_rhet=float(pr), diff=float(pf - pr),
                lo=float(diffs[int(0.025 * len(diffs))]), hi=float(diffs[int(0.975 * len(diffs))]),
                n_f=int(nf), n_r=int(nr), blocks=D, nboot_ok=len(diffs))


def rate(rows, key, sel=None):
    dat = [r["conf"][key] for r in rows if r["conf"].get(key) and (sel is None or sel(r))]
    if not dat:
        return None
    return dict(n=len(dat), p=float(np.mean([1 if c["c"] else 0 for c in dat])),
                p_ar=float(np.mean([abs(c["z"]) >= 2 for c in dat])),
                p_rv=float(np.mean([(c["rv"] is not None and c["rv"] >= 2) for c in dat])),
                med_absz=float(np.median([abs(c["z"]) for c in dat])))


def main():
    rows = load()
    print(f"带 M18 标签的候选 {len(rows)}")
    from collections import Counter
    print("分层：", dict(Counter(r["stratum"] for r in rows)))
    print("specificity：", dict(Counter(r["specificity"] for r in rows)))
    print("降级（六层校验两轮都没过）：", sum(1 for r in rows if r.get("downgraded")))
    print()

    GROUPS = [
        ("A1 官方+央行 · M17 路", lambda r: r["stratum"] == "A1_tierA_m17"),
        ("  └ 仅官方+当事人 18", lambda r: r["stratum"] == "A1_tierA_m17" and r["layer"] == "main18"),
        ("  └ 仅央行 4", lambda r: r["stratum"] == "A1_tierA_m17" and r["layer"] == "cb4"),
        ("B1 媒体 7 · M17 路", lambda r: r["stratum"] == "B1_media_m17"),
        ("A2 官方+央行 · 仅 M24 路", lambda r: r["stratum"] == "A2_tierA_m24only"),
        ("全部", lambda r: True),
    ]
    KEYS = [("NVDA", "NVDA"), ("P_semi", "半导体组合"), ("P_crypto", "加密组合")]

    for gname, gsel in GROUPS:
        sub = [r for r in rows if gsel(r)]
        if not sub:
            continue
        nf = sum(1 for r in sub if r["specificity"] == "factual")
        print(f"### {gname}   n={len(sub)}  factual {nf} ({nf/len(sub):.1%})")
        for key, label in KEYS:
            d = boot_diff(sub, key)
            if not d:
                continue
            print(f"  {label:12} P_fact {d['p_fact']:>6.1%} (n={d['n_f']:>4})  "
                  f"P_rhet {d['p_rhet']:>6.1%} (n={d['n_r']:>4})  "
                  f"差 {d['diff']:+.1%}  95% [{d['lo']:+.1%}, {d['hi']:+.1%}]  块 {d['blocks']}")
        print()


if __name__ == "__main__":
    main()
