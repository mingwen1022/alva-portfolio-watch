"""对一组触发时刻跑判据 + 经验零 + 安慰剂平移（多进程）。

用法  python3 scripts/run_crit.py <trigsets.json> <out.json> [reps] [nboot_null] [offset]

⚠️ PO 的触发日**跨标的共用**（同一条政策言论打到所有持仓），
   判据的假阳性率因此不是逐标的独立的 4%。经验零用**共用伪日历**：
   一次抽一份日历同时套到全部标的，量出「通过比例」这个统计量本身的零分布。
   位置匹配版另外把替换日限制在同月内三分位 + 同周几 —— MA 族踩过日历位置的坑。
"""
import os, sys, json, time
import numpy as np
import multiprocessing as mp
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crit

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NBOOT_MAIN = 2000
SEED_NULL = 424242
SEMI = ["NVDA", "AMD", "MSFT", "ARM", "ALAB"]
_P = {}


def _load_all():
    k = crit.kinds()
    for s, v in sorted(k.items()):
        try:
            _P[s] = (crit.load(s, v == "crypto"), v == "crypto")
        except Exception:
            pass
    return _P


def _job(a):
    """a = (sym, kind, 'obs'|'null'|'placebo', payload, nboot, seed)"""
    sym, mode, payload, nboot, seed = a
    P, isc = _P[sym]
    if mode == "obs":
        eps, off = payload
        tm, hit = crit.trig_mask_from_posts(P, eps, isc, offset=off)
    elif mode == "cal":
        tm = crit.mask_from_calendar(P, {int(k): set(v) for k, v in payload.items()})
        hit = int(tm.sum())
    else:  # shift
        eps, off, k = payload
        tm0, _ = crit.trig_mask_from_posts(P, eps, isc, offset=off)
        tm = np.zeros_like(tm0)
        if k < 0: tm[:k] = tm0[-k:]
        else: tm[k:] = tm0[:-k]
        hit = int(tm.sum())
    r = crit.run_sym(P, tm, nboot=nboot, seed=seed)
    if r is None:
        return None
    r.update(sym=sym, asset="crypto" if isc else "us_equity", hit=hit)
    return r


def summarize(rows, asset):
    o = [x for x in rows if x["asset"] == asset]
    if not o:
        return None
    return dict(n=len(o), passrate=float(np.mean([x["pass_"] for x in o])),
                mult_med=float(np.median([x["mult"] for x in o])),
                trig_med=float(np.median([x["n"] for x in o])),
                blocks_med=float(np.median([x["blocks"] for x in o])))


def main(trigfile, out, reps=10, nboot_null=250, offset=0):
    trigsets = json.load(open(trigfile))
    _load_all()
    syms = sorted(_P.keys())
    print(f"载入 {len(syms)} 个标的（美股 {sum(1 for s in syms if not _P[s][1])} · 加密 {sum(1 for s in syms if _P[s][1])}）", flush=True)
    pool = Pool(9)
    res = {}
    for name, eps in trigsets.items():
        t0 = time.time()
        obs = [r for r in pool.map(_job, [(s, "obs", (eps, offset), NBOOT_MAIN, 20260819) for s in syms]) if r]
        # 参照标的（每个资产类别一个）用来生成共用伪日历
        nulls = {}
        for asset, isc in (("us_equity", False), ("crypto", True)):
            ref = next((s for s in syms if _P[s][1] == isc), None)
            if ref is None:
                continue
            P, _ = _P[ref]
            tmref, _h = crit.trig_mask_from_posts(P, eps, isc, offset=offset)
            if not tmref.any():
                continue
            sub = [s for s in syms if _P[s][1] == isc]
            for mode, gen in (("day", crit.shared_null_calendars),
                              ("pos", crit.position_matched_calendars)):
                cals = (gen(P, tmref, reps, SEED_NULL, mode="day") if mode == "day"
                        else gen(P, tmref, reps, SEED_NULL + 1))
                agg = []
                for rep, cal in enumerate(cals):
                    pay = {str(k): sorted(v) for k, v in cal.items()}
                    rr = [r for r in pool.map(_job, [(s, "cal", pay, nboot_null, 20260819 + rep) for s in sub]) if r]
                    if rr:
                        agg.append(dict(rep=rep, n=len(rr),
                                        passrate=float(np.mean([x["pass_"] for x in rr])),
                                        mult_med=float(np.median([x["mult"] for x in rr]))))
                nulls[f"{asset}|{mode}"] = agg
        placebo = []
        for k in (-10, -5, 5, 10):
            rr = [r for r in pool.map(_job, [(s, "shift", (eps, offset, k), nboot_null, 20260819) for s in syms]) if r]
            for asset in ("us_equity", "crypto"):
                sm = summarize(rr, asset)
                if sm:
                    sm.update(k=k, asset=asset)
                    placebo.append(sm)
        res[name] = dict(obs=obs, null=nulls, placebo=placebo, ntrig=len(eps), offset=offset)
        for asset in ("us_equity", "crypto"):
            sm = summarize(obs, asset)
            if not sm:
                continue
            nd = nulls.get(f"{asset}|day", []); npo = nulls.get(f"{asset}|pos", [])
            f = lambda a: (float(np.mean([x["passrate"] for x in a])) if a else float("nan"))
            g = lambda a: (float(np.percentile([x["passrate"] for x in a], 95)) if a else float("nan"))
            print(f"{name:28} {asset:10} n={sm['n']:>3} 通过 {sm['passrate']:>6.1%} 倍数 {sm['mult_med']:.3f} "
                  f"触发中位 {sm['trig_med']:.0f} | 零-日 {f(nd):>6.1%}(P95 {g(nd):.1%}) 零-位置 {f(npo):>6.1%}(P95 {g(npo):.1%})", flush=True)
        semi = [(x["sym"], round(x["mult"], 3), round(x["lo"], 3), x["pass_"]) for x in obs if x["sym"] in SEMI]
        print(f"{'':28} 半导体 {semi}   用时 {time.time()-t0:.0f}s", flush=True)
    pool.close()
    json.dump(res, open(out, "w"), indent=1)
    print("→", out, flush=True)


if __name__ == "__main__":
    mp.set_start_method("fork", force=True)   # macOS 默认 spawn，子进程读不到已载入的网格
    main(sys.argv[1], sys.argv[2],
         reps=int(sys.argv[3]) if len(sys.argv) > 3 else 10,
         nboot_null=int(sys.argv[4]) if len(sys.argv) > 4 else 250,
         offset=int(sys.argv[5]) if len(sys.argv) > 5 else 0)
