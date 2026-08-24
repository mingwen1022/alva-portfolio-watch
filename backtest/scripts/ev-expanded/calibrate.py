"""判据在零信号下的假阳性 / 假反向率标定

对每只「可判定」标的，保持块数与块内长度不变，把块的起点随机重放到可用交易日上，
用完全相同的口径重算。得到的通过率就是「92 只里若干只通过属于随机期望」的那个期望。
"""
import sys, os, json, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *
from collections import Counter

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
REP, BB = 30, 800
OUTF = f"{ROOT}/out/calib.json"
FNS = {"EV1": lambda s: insider_triggers(load_insider(s), "P", False, 2, "kth"),
       "EV2": lambda s: insider_triggers(load_insider(s), "S", True, 2, "kth"),
       "EV3": lambda s: analyst_triggers(load_analyst(s))[:2],
       "EV5": lambda s: congress_triggers(load_congress(s))[:2]}

out = {}
t0 = time.time()
for sid, blk in R.items():
    ev = [x for x in blk["rows"] if x["bucket"] in ("通过", "未通过", "反向")]
    cnt = Counter()
    per = []
    for x in ev:
        s = x["sym"]
        S = build(s)
        days, _ = FNS[sid](s)
        ti = align(days, S["ds"])
        blks = blocks_of([i for i in ti if S["V"][i] is not None and S["sig"][i] is not None])
        usable = [i for i in range(S["n"]) if S["V"][i] is not None and S["sig"][i] is not None]
        lo_u, hi_u = usable[0], usable[-1]
        rng = random.Random(hash(s) % 10**6 + 7)
        c = Counter()
        for rep in range(REP):
            fake = set()
            for b in blks:
                st0 = rng.randint(lo_u, max(lo_u, hi_u - len(b)))
                for k in range(len(b)):
                    fake.add(st0 + k)
            fk = sorted(i for i in fake if S["V"][i] is not None and S["sig"][i] is not None)
            r = evaluate(fk, S, strat=True, seed=SEED + rep, B=BB)
            if r.get("err") or r["nb"] < 5:
                c["skip"] += 1; continue
            c["n"] += 1
            if r["lo"] > 1.0: c["pass"] += 1
            if r["hi"] < 1.0: c["rev"] += 1
        cnt.update(c)
        per.append(dict(sym=s, **c))
        print(f"  {sid} {s:6} 假阳 {c['pass']}/{c['n']} 假反向 {c['rev']}/{c['n']}  "
              f"{time.time()-t0:.0f}s", flush=True)
    out[sid] = dict(n=cnt["n"], fp=cnt["pass"], frev=cnt["rev"],
                    fp_rate=cnt["pass"] / max(1, cnt["n"]), frev_rate=cnt["rev"] / max(1, cnt["n"]),
                    per=per)
    print(f"== {sid} 零信号假阳性率 {out[sid]['fp_rate']*100:.1f}% · "
          f"假反向率 {out[sid]['frev_rate']*100:.1f}%  (n={cnt['n']})", flush=True)
    json.dump(out, open(OUTF, "w"), indent=1, ensure_ascii=False)
