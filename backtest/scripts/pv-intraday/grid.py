"""阈值网格扫描（窗 A）。报分布，不用触发频率当筛选判据。"""
import sys, json, time, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import grid_subset
from prep import prep
from analysis import run_window, trig_mask, valid_mask

THZ = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
THV = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
NBOOT = 400

def scan(rows, gridkind, tag, window="A"):
    cache = {}
    out = []
    for r in rows:
        s = r["symbol"]
        try: cache[s] = prep(s, gridkind)
        except Exception as e: print("ERR", s, e)
    for thz in THZ:
        for thv in THV:
            recs = []
            for s, P in cache.items():
                vm = valid_mask(P, window)
                tm = trig_mask(P, thz, thv) & vm
                nd = int(tm.any(axis=1).sum()); nv = int(vm.any(axis=1).sum())
                res = run_window(P, thz, thv, window=window, nboot=NBOOT)
                recs.append(dict(sym=s, n=int(tm.sum()), days=nd, vdays=nv,
                                 blocks=res["blocks"] if res else 0,
                                 mult=res["mult"] if res else None,
                                 lo=res["lo"] if res else None,
                                 passed=bool(res["pass_"]) if res else False))
            ms = [x["mult"] for x in recs if x["mult"] is not None]
            out.append(dict(tag=tag, thz=thz, thv=thv, nsym=len(recs),
                            passed=sum(x["passed"] for x in recs),
                            mult_med=float(np.median(ms)) if ms else None,
                            mult_p25=float(np.percentile(ms, 25)) if ms else None,
                            mult_p75=float(np.percentile(ms, 75)) if ms else None,
                            trig_per_day=float(np.median([x["n"]/max(x["vdays"],1) for x in recs])),
                            day_rate=float(np.median([x["days"]/max(x["vdays"],1) for x in recs])),
                            blocks_med=float(np.median([x["blocks"] for x in recs])),
                            per_sym=recs))
            o = out[-1]
            print(f"{tag} z{thz:<4} v{thv:<5} 通过 {o['passed']}/{o['nsym']:<3} "
                  f"倍数中位 {o['mult_med'] if o['mult_med'] else float('nan'):.3f} "
                  f"触发/日 {o['trig_per_day']:.2f} 有触发日占比 {o['day_rate']:.3f} 块中位 {o['blocks_med']:.0f}", flush=True)
    return out

if __name__ == "__main__":
    t0 = time.time()
    gu, gc = grid_subset()
    res = scan(gu, "RTH", "美股RTH") + scan(gc, "UTC", "加密")
    json.dump(res, open(f"{BASE}/derived/grid_A.json", "w"), indent=1, ensure_ascii=False)
    print("用时", round(time.time() - t0))
