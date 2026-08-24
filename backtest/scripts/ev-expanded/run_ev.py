"""EV 族在 92 只美股样本池上的重跑（SPY 为基准，不计入）"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *

U = universe()
SYMS = [s for s in U if s != "SPY"]
OUT = f"{ROOT}/out"


def trig_ev1(s):
    return insider_triggers(load_insider(s), "P", False, 2, "kth")


def trig_ev2(s):
    return insider_triggers(load_insider(s), "S", True, 2, "kth")


def trig_ev3(s):
    return analyst_triggers(load_analyst(s))[:2]


def trig_ev5(s):
    return congress_triggers(load_congress(s))[:2]


SIGS = {"EV1": ("内部人簇买 code=P · ≥2 owner · 30 日窗", trig_ev1),
        "EV2": ("内部人簇卖 code=S · 剔 10b5-1 · ≥2 owner · 30 日窗", trig_ev2),
        "EV3": ("分析师簇 M9≥3 同向 · 30 日窗 · 口径 B", trig_ev3),
        "EV5": ("议员交易 M11≥1 · 30 日窗 · 触发日=申报日", trig_ev5)}


def main():
    res = {}
    t0 = time.time()
    cache = {}
    for sid, (desc, fn) in SIGS.items():
        rows = []
        for s in SYMS:
            if s not in cache:
                cache[s] = build(s)
            S = cache[s]
            days, nraw = fn(s)
            ti = align(days, S["ds"])
            r = evaluate(ti, S, strat=True)
            yrs = U[s]["bars"] / 252
            rows.append(dict(sym=s, n_raw=nraw, n_trig_cal=len(days), n=r.get("n", 0),
                             nb=r.get("nb", 0), r=r.get("r"), lo=r.get("lo"), hi=r.get("hi"),
                             err=r.get("err"), per_yr=round(len(days) / yrs, 2) if yrs else None,
                             verdict=verdict(r), **{k: U[s][k] for k in
                             ("sector", "size", "vol", "stratum", "new", "bars", "n_insider", "n_analyst")}))
            print(f"  {sid} {s:6} n={r.get('n',0):4} nb={r.get('nb',0):4} "
                  f"r={r.get('r') and round(r['r'],3)} {verdict(r)}", flush=True)
        res[sid] = dict(desc=desc, rows=rows)
        print(f"== {sid} 完成 {time.time()-t0:.0f}s", flush=True)
    json.dump(res, open(f"{OUT}/ev_main.json", "w"), indent=1, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
