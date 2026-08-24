"""对每一条「通过」做四项核实：留一法 · 安慰剂平移(|k|≥6) · 当日 |z| 配对 · 种子敏感性"""
import sys, os, json, random, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
FNS = {"EV1": lambda s: insider_triggers(load_insider(s), "P", False, 2, "kth"),
       "EV2": lambda s: insider_triggers(load_insider(s), "S", True, 2, "kth"),
       "EV3": lambda s: analyst_triggers(load_analyst(s))[:2],
       "EV5": lambda s: congress_triggers(load_congress(s))[:2]}


def zmatched(trig_idx, S, M=40, seed=SEED, B=1000):
    """基准按触发当日 |z| 最接近的 M 个净化非触发日配对"""
    V, sig, z, n = S["V"], S["sig"], S["z"], S["n"]
    usable = [i for i in range(n) if V[i] is not None and sig[i] is not None and z[i] is not None]
    T = sorted(i for i in trig_idx if i in set(usable))
    if len(T) < 3:
        return None
    near = set()
    for i in T:
        near.update(range(i - PURGE, i + PURGE + 1))
    pool = [i for i in usable if i not in near]
    az = {i: abs(z[i]) for i in usable}
    pool_sorted = sorted(pool, key=lambda i: az[i])
    pz = [az[i] for i in pool_sorted]
    import bisect
    grp = {}
    for i in T:
        k = bisect.bisect_left(pz, az[i])
        lo, hi = max(0, k - M // 2), min(len(pool_sorted), max(0, k - M // 2) + M)
        grp[i] = [V[j] for j in pool_sorted[lo:hi]]
    ratios = [V[i] / med(grp[i]) for i in T]
    blks = blocks_of(T)
    rng = random.Random(seed)
    boots = []
    for _ in range(B):
        samp = []
        for _ in range(len(blks)):
            samp.extend(blks[rng.randrange(len(blks))])
        boots.append(med([V[i] / med(rng.choices(grp[i], k=len(grp[i]))) for i in samp]))
    boots.sort()
    return dict(n=len(T), nb=len(blks), r=med(ratios), lo=boots[int(.025 * B)],
                hi=boots[int(.975 * B) - 1], medz=med([az[i] for i in T]),
                basez=med([az[i] for i in pool]))


def report(sid, sym):
    S = build(sym)
    days, _ = FNS[sid](sym)
    ti = align(days, S["ds"])
    base = evaluate(ti, S)
    print(f"\n{'='*80}\n{sid} · {sym}   基线 {base['r']:.2f} [{base['lo']:.2f}, {base['hi']:.2f}] "
          f"n={base['n']} 块={base['nb']}\n{'='*80}")

    # ① 留一法（逐块剔除）
    blks = blocks_of([i for i in ti if S["V"][i] is not None and S["sig"][i] is not None])
    flips = 0
    print("① 留一法（逐块剔除）")
    for j in range(len(blks)):
        keep = [i for k, b in enumerate(blks) if k != j for i in b]
        r = evaluate(keep, S)
        if r.get("err") or r["lo"] <= 1.0:
            flips += 1
    print(f"   {len(blks)} 块里剔除任意一块 → 翻转为未通过 {flips} 次 "
          f"({flips/len(blks)*100:.0f}%)")

    # ② 安慰剂平移 |k| ≥ 6
    print("② 安慰剂平移（只跑 |k| ≥ 6，k∈[-5,-1] 的窗口含触发日本身，算术上必然变强）")
    line = []
    for k in (-14, -12, -10, -8, -6, 6, 8, 10, 12, 14):
        sh = [i + k for i in ti if 0 <= i + k < S["n"]]
        r = evaluate(sh, S)
        line.append((k, r.get("r"), r.get("lo")))
    print("   " + "  ".join(f"k={k}:{(('%.2f' % v) if v else '—')}"
                            f"{'✓' if (lo and lo>1.0) else ''}" for k, v, lo in line))
    print(f"   实际 k=0 : {base['r']:.2f}✓   平移中位 "
          f"{med([v for _, v, _ in line if v]):.2f}   平移里通过的 "
          f"{sum(1 for _,_,lo in line if lo and lo>1.0)}/{len(line)}")

    # ③ 当日 |z| 配对
    zm = zmatched(ti, S)
    print("③ 当日 |z| 配对基准（控制「触发当天本来就是大波动日」）")
    if zm:
        print(f"   触发日 |z| 中位 {zm['medz']:.2f} vs 非触发 {zm['basez']:.2f} → "
              f"配对后倍数 {zm['r']:.2f} [{zm['lo']:.2f}, {zm['hi']:.2f}] "
              f"{'仍通过' if zm['lo']>1.0 else '不通过'}")

    # ④ 种子敏感性
    outs = [evaluate(ti, S, seed=SEED + 977 * q) for q in range(12)]
    los = [o["lo"] for o in outs]
    print(f"④ 12 个随机种子：下界 {min(los):.3f}–{max(los):.3f} · "
          f"通过 {sum(1 for l in los if l>1.0)}/12")

    # ⑤ 触发间隔（是不是季度节奏）
    tt = sorted(days)
    gaps = [(tt[i + 1] - tt[i]).days for i in range(len(tt) - 1)]
    if gaps:
        q = sum(1 for g in gaps if 80 <= g <= 100) / len(gaps)
        print(f"⑤ 相邻触发间隔 中位 {med(gaps):.0f} 日 · 落在 80–100 日（季度节奏）的 "
              f"{q*100:.0f}%  {sorted(gaps)}")
    return dict(sid=sid, sym=sym, base=base, loo_flip=flips, loo_n=len(blks),
                placebo=line, zmatch=zm, seeds=los)


if __name__ == "__main__":
    out = []
    for sid, blk in R.items():
        for x in blk["rows"]:
            if x["bucket"] == "通过":
                out.append(report(sid, x["sym"]))
    json.dump(out, open(f"{ROOT}/out/scrutiny.json", "w"), indent=1, ensure_ascii=False, default=str)
