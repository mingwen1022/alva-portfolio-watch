"""ETH（扩展时段 64 槽）网格：覆盖率 · z 可算比例 · 窗 A 结果，与 RTH 对照"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import grid_subset
from prep import prep
from analysis import run_window, trig_mask, valid_mask

if __name__ == "__main__":
    gu, _ = grid_subset()
    out = []
    for r in gu:
        s = r["symbol"]
        rec = dict(sym=s)
        for gk in ("ETH", "RTH"):
            try: P = prep(s, gk)
            except Exception as e: continue
            K = int(P["nslots"])
            pres = P["present"]; fill = P["filled"]
            zdef = ~np.isnan(P["sigma"])
            # 逐 slot：该 slot 是否至少一半日子能算出 sigma
            slot_ok = (zdef.mean(axis=0) >= 0.5).sum()
            res = run_window(P, 4.5, 2.0, window="A", nboot=600)
            rec[gk] = dict(K=K, present=round(float(pres.mean()), 3), fill=round(float(fill.mean()), 3),
                           sigma_def=round(float(zdef.mean()), 3), slots_usable=int(slot_ok),
                           n=res["n"] if res else 0, mult=round(res["mult"], 3) if res else None,
                           lo=round(res["lo"], 3) if res else None,
                           passed=bool(res["pass_"]) if res else False)
        out.append(rec)
        print(s, rec.get("ETH"), rec.get("RTH"), flush=True)
    json.dump(out, open(f"{BASE}/derived/eth_vs_rth.json", "w"), indent=1, ensure_ascii=False)
    for gk in ("ETH", "RTH"):
        rr = [x[gk] for x in out if gk in x]
        print(f"\n{gk}: 网格存在率中位 {np.median([x['present'] for x in rr]):.3f}"
              f"  填充率 {np.median([x['fill'] for x in rr]):.3f}"
              f"  sigma 可算比例 {np.median([x['sigma_def'] for x in rr]):.3f}"
              f"  可用槽位中位 {np.median([x['slots_usable'] for x in rr]):.0f}/{rr[0]['K']}"
              f"  触发中位 {np.median([x['n'] for x in rr]):.0f}"
              f"  倍数中位 {np.median([x['mult'] for x in rr if x['mult']]):.3f}"
              f"  通过 {sum(x['passed'] for x in rr)}/{len(rr)}")
