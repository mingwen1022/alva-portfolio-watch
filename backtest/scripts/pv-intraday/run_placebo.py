"""安慰剂平移。|k| 必须 > 前瞻窗长度。
窗 A：5 bar → 平移 -8/-12/-24/-52 bar（RTH 一天 26 bar，-52 = 两天）
窗 B：最长到收盘 → 只能按 session 平移 -1/-2/-3/-5
窗 C：5 日 → 平移 -8/-10 日
用法 run_placebo.py <thz> <tve> <tvc>"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import run_window, run_window_C, daily_pack, trig_mask, valid_mask

# 平移量按每日 bar 数 K 定：|k| 必须 > 前瞻窗长（5 bar），且要跨到别的 session 才算真安慰剂
def shifts_A(K): return [0, -8, -12, -K, -2 * K, -5 * K, -10 * K]
SHIFT_B = [0, -1, -2, -3, -5]
SHIFT_C = [0, -8, -10]

def main(tze, tve, tzc, tvc, gk_eq="RTH", nboot=800):
    us, cr = full()
    rows = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        thv = tvc if crypto else tve
        thz = tzc if crypto else tze
        try: P = prep(s, "UTC" if crypto else gk_eq)
        except Exception: continue
        rec = dict(sym=s, asset="crypto" if crypto else "us_equity", A={}, B={}, C={})
        K = int(P["nslots"])
        for k in shifts_A(K):
            x = run_window(P, thz, thv, "A", nboot=nboot, shift=k, shift_unit="bar")
            rec["A"][f"{k}({k/K:+.0f}日)" if abs(k) >= K else str(k)] = round(x["mult"], 3) if x else None
        for k in SHIFT_B:
            x = run_window(P, thz, thv, "B", nboot=nboot, shift=k, shift_unit="session")
            rec["B"][str(k)] = round(x["mult"], 3) if x else None
        try:
            dp = daily_pack(s, crypto)
            vmA = valid_mask(P, "A"); tmA = trig_mask(P, thz, thv) & vmA
            tdays = [int(d) for d in P["days"][tmA.any(axis=1)]]
            for k in SHIFT_C:
                x = run_window_C(dp, tdays, nboot=nboot, shift=k)
                rec["C"][str(k)] = round(x["mult"], 3) if x else None
        except Exception: pass
        rows.append(rec)
        print(f"{s:<7} A {rec['A']}  B {rec['B']}  C {rec['C']}", flush=True)
    json.dump(rows, open(f"{BASE}/derived/placebo.json", "w"), indent=1, ensure_ascii=False)
    return rows

if __name__ == "__main__":
    main(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))
