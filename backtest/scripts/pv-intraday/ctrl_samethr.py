"""等阈值对照（registry 口径）：双确认 / 仅价格 / 仅量能 用同一组阈值"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import valid_mask
from engine import ratio_ci, sigma_decile, purge_fixed

def go(P, thz, thv):
    vm = valid_mask(P, "A"); z = np.abs(P["z"]); rv = P["rvol"]
    both = (~np.isnan(z)) & (~np.isnan(rv)) & vm
    cell = sigma_decile(P["sigma"], vm)
    out = {}
    for k, tm in (("and", both & (z >= thz) & (rv >= thv)),
                  ("price", both & (z >= thz)),
                  ("vol", both & (rv >= thv))):
        r = ratio_ci(P["VA"], cell, tm, purge_fixed(tm, 5), nboot=600, block_gap=1)
        out[k] = dict(n=r["n"], mult=round(r["mult"], 3), lo=round(r["lo"], 3),
                      blocks=r["blocks"], passed=bool(r["pass_"])) if r else None
    return out

if __name__ == "__main__":
    us, cr = full(); rows = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        try: P = prep(s, "UTC" if crypto else "RTH")
        except Exception: continue
        thz, thv = (10.0, 3.0) if crypto else (4.5, 2.0)
        rows.append(dict(sym=s, asset="crypto" if crypto else "us_equity", **{"r": go(P, thz, thv)}))
    json.dump(rows, open(f"{BASE}/derived/ctrl_samethr.json", "w"), indent=1, ensure_ascii=False)
    for a in ("us_equity", "crypto"):
        rr = [x for x in rows if x["asset"] == a and all(x["r"][k] for k in ("and", "price", "vol"))]
        print(f"\n{a} n={len(rr)}")
        for k, l in (("and", "双确认"), ("price", "仅价格"), ("vol", "仅量能")):
            print(f"   {l:<8} 触发中位 {np.median([x['r'][k]['n'] for x in rr]):>6.0f}"
                  f"  倍数中位 {np.median([x['r'][k]['mult'] for x in rr]):.3f}"
                  f"  通过 {sum(x['r'][k]['passed'] for x in rr)}/{len(rr)}")
        d1 = [x["r"]["and"]["mult"] - x["r"]["price"]["mult"] for x in rr]
        d2 = [x["r"]["and"]["mult"] - x["r"]["vol"]["mult"] for x in rr]
        print(f"   配对差 双确认−仅价格 {np.median(d1):+.3f}（{sum(1 for x in d1 if x>0)}/{len(d1)} 为正）"
              f"  双确认−仅量能 {np.median(d2):+.3f}（{sum(1 for x in d2 if x>0)}/{len(d2)}）")
