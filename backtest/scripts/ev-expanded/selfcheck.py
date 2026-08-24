"""自检：用旧口径 + 旧数据复现 results-phase2-ev.md 的逐标的数字"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *

OLD_EV2 = {"RIVN": (6, 1.32), "MSFT": (25, 1.20), "SOFI": (16, 1.12), "XOM": (8, 1.03),
           "NVDA": (33, 1.01), "TSLA": (38, 1.00), "PLTR": (25, 1.00), "AMD": (35, 0.98),
           "KO": (33, 0.84), "AAPL": (24, 0.71), "MSTR": (5, 0.72)}
OLD_EV3 = {"PLTR": (10, 1.79), "RIVN": (9, 1.31), "AMD": (20, 1.15), "XOM": (12, 1.08),
           "MSFT": (19, 1.07), "KO": (5, 1.04), "TSLA": (23, 0.99), "AAPL": (22, 0.98),
           "NVDA": (22, 0.95), "SOFI": (5, 0.92), "MSTR": (2, None)}
OLD_EV5 = {"PLTR": (11, 1.32), "NVDA": (53, 1.18), "KO": (48, 1.16), "MSFT": (59, 1.10),
           "SOFI": (3, 1.07), "TSLA": (49, 1.02), "AAPL": (59, 1.01), "AMD": (40, 0.95),
           "XOM": (47, 0.92), "MSTR": (6, 0.83), "RIVN": (3, None)}
OLD_EV1 = {"SOFI": 6, "MSTR": 5, "RIVN": 4, "XOM": 3, "TSLA": 2}


def run(tag, trigfn, expect, mode_note=""):
    print(f"\n=== {tag} {mode_note}")
    print(f"{'标的':<6}{'触发n':>6}{'期望':>6}{'块':>4}{'倍数':>7}{'期望':>7}{'95%区间':>16}")
    tot = 0
    for s in LEGACY11:
        S = build(s, src="old", raw_v=False)          # 旧口径 V = RV5/σ_rob
        days, nraw = trigfn(s)
        ti = align(days, S["ds"])
        r = evaluate(ti, S, strat=False, purge=0)     # 旧口径：全体非触发中位，无净化
        e = expect.get(s, (None, None))
        en, er = (e if isinstance(e, tuple) else (e, None))
        tot += r.get("n", 0)
        if r.get("err"):
            print(f"{s:<6}{r['n']:>6}{str(en):>6}{'—':>4}{r['err']:>7}")
        else:
            ci = "[%.2f, %.2f]" % (r["lo"], r["hi"])
            print(f"{s:<6}{r['n']:>6}{str(en):>6}{r['nb']:>4}{r['r']:>7.2f}"
                  f"{(('%.2f' % er) if er else '—'):>7}{ci:>16}")
    print(f"  合计触发 {tot}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "kth"
    run("EV2 内部人簇卖（剔 10b5-1）",
        lambda s: insider_triggers(load_insider(s, "old"), "S", True, 2, mode),
        OLD_EV2, f"trigger mode={mode}")
    run("EV1 内部人簇买",
        lambda s: insider_triggers(load_insider(s, "old"), "P", False, 2, mode),
        OLD_EV1, f"trigger mode={mode}")
    run("EV3 分析师簇 M9≥3 同向",
        lambda s: analyst_triggers(load_analyst(s, "old"))[:2], OLD_EV3)
    run("EV5 议员交易 M11≥1",
        lambda s: congress_triggers(load_congress(s, "old"))[:2], OLD_EV5)
