"""三项对照：① 双确认 vs 仅价格 vs 仅量能（等触发数）② 阈值分半可复现性 ③ bar 局部 RVOL 变体"""
import sys, json, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from roster import full
from prep import prep
from analysis import trig_mask, valid_mask, daily_pack
from engine import ratio_ci, sigma_decile, purge_fixed, trigger as dtrig

TZE, TVE, TZC, TVC = 4.5, 2.0, 10.0, 3.0
NB = 800


def _run(P, tm, nboot=NB):
    vm = valid_mask(P, "A")
    tm = tm & vm
    cell = sigma_decile(P["sigma"], vm)
    pm = purge_fixed(tm, 5)
    return ratio_ci(P["VA"], cell, tm, pm, nboot=nboot, block_gap=1)


def controls(P, thz, thv):
    vm = valid_mask(P, "A")
    z = np.abs(P["z"]); rv = P["rvol"]
    both = (~np.isnan(z)) & (~np.isnan(rv)) & vm
    tm_and = both & (z >= thz) & (rv >= thv)
    n = int(tm_and.sum())
    if n < 10: return None
    zz = z[both]; vv = rv[both]
    qz = float(np.quantile(zz, 1 - n / len(zz)))
    qv = float(np.quantile(vv, 1 - n / len(vv)))
    tm_p = both & (z >= qz)
    tm_v = both & (rv >= qv)
    out = {}
    for k, tm in (("and", tm_and), ("price", tm_p), ("vol", tm_v)):
        r = _run(P, tm)
        out[k] = dict(n=r["n"], blocks=r["blocks"], mult=round(r["mult"], 3),
                      lo=round(r["lo"], 3), passed=bool(r["pass_"])) if r else None
    out["p_vol_given_price"] = float((both & (z >= thz) & (rv >= thv)).sum() /
                                     max((both & (z >= thz)).sum(), 1))
    out["thz_eq"] = round(qz, 3); out["thv_eq"] = round(qv, 3)
    return out


def splithalf(P, sym, crypto, thv):
    """在前后两半各自求「与日线 PV1 告警量对齐」的 thz，看是否一致"""
    days = P["days"]; vm = valid_mask(P, "A")
    vd = np.flatnonzero(vm.any(axis=1))
    if len(vd) < 200: return None
    mid = vd[len(vd) // 2]
    dp = daily_pack(sym, crypto)
    dtm = dtrig(dp["ind"], 1.5, 3.0 if crypto else 2.0).reshape(-1)
    dkeys = np.array([int(d.replace("-", "")) for d in dp["dates"]])
    dvm = dp["vm"].reshape(-1)
    GRID = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0]
    res = {}
    for tag, sel in (("前半", vd[vd <= mid]), ("后半", vd[vd > mid])):
        lo, hi = int(days[sel].min()), int(days[sel].max())
        m = (dkeys >= lo) & (dkeys <= hi) & dvm
        if m.sum() < 30: return None
        target = float(dtm[m].sum() / m.sum())
        best, bd = None, 9e9
        for t in GRID:
            tm = trig_mask(P, t, thv) & vm
            rate = float(tm[sel].any(axis=1).mean())
            d = abs(rate - target)
            if d < bd: bd, best = d, (t, rate)
        res[tag] = dict(target=round(target, 4), thz=best[0], rate=round(best[1], 4))
    return res


if __name__ == "__main__":
    us, cr = full()
    out = []
    for r in us + cr:
        s = r["symbol"]; crypto = r["asset_class"] == "crypto"
        try: P = prep(s, "UTC" if crypto else "RTH")
        except Exception: continue
        thz, thv = (TZC, TVC) if crypto else (TZE, TVE)
        rec = dict(sym=s, asset="crypto" if crypto else "us_equity")
        rec["ctrl"] = controls(P, thz, thv)
        rec["split"] = splithalf(P, s, crypto, thv)
        # bar 局部 RVOL
        vm = valid_mask(P, "A")
        tmb = trig_mask(P, thz, thv, rvol_key="rvol_bar") & vm
        rb = _run(P, tmb)
        rec["rvol_bar"] = dict(n=rb["n"], mult=round(rb["mult"], 3), lo=round(rb["lo"], 3),
                               blocks=rb["blocks"], passed=bool(rb["pass_"])) if rb else None
        out.append(rec)
        print(s, rec["ctrl"]["and"]["mult"] if rec["ctrl"] else None,
              rec["ctrl"]["price"]["mult"] if rec["ctrl"] else None,
              rec["ctrl"]["vol"]["mult"] if rec["ctrl"] else None,
              rec["split"], flush=True)
    json.dump(out, open(f"{BASE}/derived/controls.json", "w"), indent=1, ensure_ascii=False)
