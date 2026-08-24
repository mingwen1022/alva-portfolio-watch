"""点估计的零分布：块结构不变、位置随机重放，只算点估计（不做自助）。

回答两件事
  ① 相对基准倍数这个估计量在零信号下是不是中位为 1（决定符号检验能不能用）
  ② 每只标的的安慰剂 p 值 = 零分布中 ≥ 实测倍数的比例
"""
import sys, os, json, random, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from collections import defaultdict

REP = 500
U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
FNS = {"EV1": lambda s: insider_triggers(load_insider(s), "P", False, 2, "kth"),
       "EV2": lambda s: insider_triggers(load_insider(s), "S", True, 2, "kth"),
       "EV3": lambda s: analyst_triggers(load_analyst(s))[:2],
       "EV5": lambda s: congress_triggers(load_congress(s))[:2]}


def point_ratio(T, S, pool, cuts, bypool_med):
    def dec(x):
        lo, hi = 0, len(cuts)
        while lo < hi:
            m = (lo + hi) // 2
            if x >= cuts[m]:
                lo = m + 1
            else:
                hi = m
        return lo
    return med([S["V"][i] / bypool_med[dec(S["sig"][i])] for i in T])


OUT = {}
for sid, blk in R.items():
    ev = [x for x in blk["rows"] if x["bucket"] in ("通过", "未通过", "反向")]
    rows = []
    for x in ev:
        s = x["sym"]
        S = build(s)
        ti = align(FNS[sid](s)[0], S["ds"])
        usable = [i for i in range(S["n"]) if S["V"][i] is not None and S["sig"][i] is not None]
        us = set(usable)
        T = sorted(i for i in ti if i in us)
        blks = blocks_of(T)
        near = set()
        for i in T:
            near.update(range(i - PURGE, i + PURGE + 1))
        pool = [i for i in usable if i not in near]
        ss = sorted(S["sig"][i] for i in pool)
        cuts = [ss[int(k * len(ss) / NDEC)] for k in range(1, NDEC)]

        def dec(v):
            lo, hi = 0, len(cuts)
            while lo < hi:
                m = (lo + hi) // 2
                if v >= cuts[m]:
                    lo = m + 1
                else:
                    hi = m
            return lo
        bp = defaultdict(list)
        for i in pool:
            bp[dec(S["sig"][i])].append(S["V"][i])
        bm = {k: med(v) for k, v in bp.items()}
        obs = med([S["V"][i] / bm[dec(S["sig"][i])] for i in T])

        rng = random.Random(1234567 + hash(s) % 99991)
        lo_u, hi_u = usable[0], usable[-1]
        null = []
        for _ in range(REP):
            fake = set()
            for b in blks:
                st0 = rng.randint(lo_u, max(lo_u, hi_u - len(b)))
                for k in range(len(b)):
                    fake.add(st0 + k)
            fk = [i for i in fake if i in us]
            if len(fk) < 3:
                continue
            null.append(med([S["V"][i] / bm[dec(S["sig"][i])] for i in fk]))
        null.sort()
        p = sum(1 for v in null if v >= obs) / len(null)
        rows.append(dict(sym=s, obs=round(obs, 4), null_med=round(med(null), 4),
                         null_gt1=round(sum(1 for v in null if v > 1) / len(null), 4),
                         p=round(p, 4), nb=len(blks), n=len(T)))
        print(f"  {sid} {s:6} 实测 {obs:.3f} · 零分布中位 {med(null):.3f} · "
              f"零分布 >1 的比例 {sum(1 for v in null if v>1)/len(null)*100:.0f}% · p={p:.3f}", flush=True)
    OUT[sid] = rows
    exp1 = sum(x["null_gt1"] for x in rows)
    got1 = sum(1 for x in rows if x["obs"] > 1)
    sig = sum(1 for x in rows if x["p"] < 0.05)
    print(f"== {sid}  实测 >1 的只数 {got1}/{len(rows)}  零期望 {exp1:.1f}  "
          f"零分布中位的中位 {st.median([x['null_med'] for x in rows]):.3f}  "
          f"安慰剂 p<0.05 的只数 {sig}（期望 {0.05*len(rows):.1f}）", flush=True)
    json.dump(OUT, open(f"{ROOT}/out/placebo_null.json", "w"), indent=1, ensure_ascii=False)
