"""全样本安慰剂平移（只跑 |k| ≥ 6）+ |z| 配对下的符号检验

平移的意义：若「24/28 只倍数 >1」来自触发日本身，平移后应当塌回 1；
若来自那段时期本来就动荡，平移后仍在 1 以上。
"""
import sys, os, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from scrutiny import zmatched
from collections import defaultdict

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
FNS = {"EV1": lambda s: insider_triggers(load_insider(s), "P", False, 2, "kth"),
       "EV2": lambda s: insider_triggers(load_insider(s), "S", True, 2, "kth"),
       "EV3": lambda s: analyst_triggers(load_analyst(s))[:2],
       "EV5": lambda s: congress_triggers(load_congress(s))[:2]}
KS = [-14, -12, -10, -8, -6, 0, 6, 8, 10, 12, 14]


def point(T, S, bm, dec):
    return med([S["V"][i] / bm[dec(S["sig"][i])] for i in T])


OUT = {}
for sid, blk in R.items():
    ev = [x for x in blk["rows"] if x["bucket"] in ("通过", "未通过", "反向")]
    tab = defaultdict(list)
    zsign = []
    for x in ev:
        s = x["sym"]
        S = build(s)
        ti = align(FNS[sid](s)[0], S["ds"])
        usable = [i for i in range(S["n"]) if S["V"][i] is not None and S["sig"][i] is not None]
        us = set(usable)
        T0 = sorted(i for i in ti if i in us)
        near = set()
        for i in T0:
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
        for k in KS:
            T = [i + k for i in T0 if (i + k) in us]
            if len(T) >= 3:
                tab[k].append(point(T, S, bm, dec))
        zm = zmatched(ti, S, B=200)
        if zm:
            zsign.append(zm["r"])
    print(f"\n### {sid}  可判定 {len(ev)} 只")
    print(f"{'平移 k':<8}{'倍数中位':>10}{'>1 的只数':>11}{'占比':>8}")
    for k in KS:
        v = tab[k]
        if not v:
            continue
        g = sum(1 for a in v if a > 1)
        print(f"{('实际 0' if k==0 else k):<8}{st.median(v):>10.3f}{f'{g}/{len(v)}':>11}"
              f"{g/len(v)*100:>7.0f}%")
    if zsign:
        g = sum(1 for a in zsign if a > 1)
        print(f"{'|z| 配对':<8}{st.median(zsign):>10.3f}{f'{g}/{len(zsign)}':>11}{g/len(zsign)*100:>7.0f}%")
    OUT[sid] = dict(shift={str(k): tab[k] for k in tab}, zsign=zsign)

json.dump(OUT, open(f"{ROOT}/out/shift_all.json", "w"), indent=1, ensure_ascii=False)
