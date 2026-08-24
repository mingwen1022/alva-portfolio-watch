"""AND vs OR 等触发数对照 · 日线 · 逐标的

复用 backtest/scripts/pv-expanded/pv_engine.py（逐位复制，md5 一致）的
indicators / blocks_of / ratio_ci，不改一行。本文件只负责：
  ① 造对照组的触发集（等触发数校准）
  ② 逐标的调用 ratio_ci
  ③ 落盘诊断量

对照组
  and_base   |z|>=1.5 AND rvol>=thv          现行 PV1
  price_eq   |z|>=qz                          触发数校准到 = and_base
  vol_eq     rvol>=qv                         同上
  or_eq      |z|>=qz2 OR rvol>=qv2            两腿等尾质量，并集触发数校准到 = and_base
  or_scale   |z|>=a*1.5 OR rvol>=a*thv        两腿等比例放大，稳健性对照
  price_base |z|>=1.5                         等阈值（PV1 的价格腿）
  vol_base   rvol>=thv                        等阈值（PV1 的量能腿）
  or_base    price_base OR vol_base           官方口径原样
"""
import sys, os, json, math, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from pv_engine import indicators, blocks_of, ratio_ci, load_universe
from universe_load import roster, vol_tier

OUT = os.path.join(os.path.dirname(HERE), "derived")
NBOOT_MAIN, NBOOT_AUX = 4000, 1500
D_EQ = "/Users/ming/project/alva/backtest/universe/data/daily"
D_CR = "/Users/ming/project/alva/backtest/universe/data/crypto"


# ---------- 额外读 open，用于跳空 / 盘中拆分（引擎不读 open） ----------
def load_open(sym, asset):
    import csv
    d = D_CR if asset == "crypto" else D_EQ
    ds, op, cl = [], [], []
    with open(f"{d}/{sym}.csv") as f:
        for row in csv.DictReader(f):
            try:
                o = float(row["open"]); c = float(row["close"])
            except (TypeError, ValueError):
                continue
            ds.append(row["date"]); op.append(o); cl.append(c)
    o = np.argsort(ds)
    return np.array(op)[o], np.array(cl)[o]


def prep2(r):
    sym = r["symbol"]
    asset = "crypto" if r["asset_class"] == "crypto" else "us_equity"
    ann = 365 if asset == "crypto" else 252
    ds, c, v = load_universe(sym, asset)
    ind = indicators(c, v, ann)
    ind.update(sym=sym, asset=asset, ann=ann, dates=ds, close=c, vol=v,
               thv=3.0 if asset == "crypto" else 2.0,
               sector=r["sector"], size_tier=r["size_tier"], stratum=r["stratum"],
               vol_tier_csv={"low": "低波 <25%", "mid": "中波 25-50%",
                             "high": "高波 >50%"}.get(r["vol_tier"]),
               advol=float(r["avg_dollar_vol_usd"]) if r["avg_dollar_vol_usd"] else float("nan"))
    op, cl = load_open(sym, asset)
    if len(op) == len(c):
        gap = np.full(len(c), np.nan); itd = np.full(len(c), np.nan)
        ok = (op[1:] > 0) & (cl[:-1] > 0)
        gap[1:][ok] = np.log(op[1:][ok] / cl[:-1][ok])
        ok2 = (op > 0) & (cl > 0)
        itd[ok2] = np.log(cl[ok2] / op[ok2])
        ind["gap"] = gap; ind["itd"] = itd
    else:
        ind["gap"] = np.full(len(c), np.nan); ind["itd"] = np.full(len(c), np.nan)
    av = ind["avol"][~np.isnan(ind["avol"])]
    ind["sigma_ann"] = float(np.median(av)) if len(av) else float("nan")
    ind["vol_tier"] = vol_tier(ind["sigma_ann"])
    # 全部对照组共用的候选池 E：V/sigma/z/rvol 四者皆有效
    E = (~np.isnan(ind["V"])) & (~np.isnan(ind["sigma"])) & \
        (~np.isnan(ind["z"])) & (~np.isnan(ind["rvol"]))
    ind["E"] = E
    ind["Eidx"] = np.flatnonzero(E)
    ind["years"] = len(ind["Eidx"]) / ann
    return ind


# ---------- 等触发数校准 ----------
def topn_thr(x, n):
    """返回使 |{x >= thr}| >= n 且尽量等于 n 的阈值"""
    if n <= 0: return np.inf
    xs = np.sort(x)[::-1]
    if n >= len(xs): return -np.inf
    return float(xs[n - 1])


def calibrate(ind, n_target):
    az = np.abs(ind["z"])[ind["E"]]
    rv = ind["rvol"][ind["E"]]
    out = {}
    out["qz"] = topn_thr(az, n_target)
    out["qv"] = topn_thr(rv, n_target)
    # OR · 两腿等尾质量：并集数随每腿 m 单调不减，m ∈ [ceil(n/2), n]
    best = None
    for m in range(max(1, (n_target + 1) // 2), n_target + 1):
        tz = topn_thr(az, m); tv = topn_thr(rv, m)
        u = int(((az >= tz) | (rv >= tv)).sum())
        d = abs(u - n_target)
        if best is None or d < best[0]:
            best = (d, m, tz, tv, u)
        if u >= n_target:  # 单调，越界即可停
            break
    out["or_m"], out["or_qz"], out["or_qv"], out["or_n"] = best[1], best[2], best[3], best[4]
    # OR · 两腿等比例放大
    thz, thv = 1.5, ind["thv"]
    best2 = None
    for a in np.arange(1.0, 8.001, 0.005):
        u = int(((az >= a * thz) | (rv >= a * thv)).sum())
        d = abs(u - n_target)
        if best2 is None or d < best2[0]:
            best2 = (d, float(a), u)
        if u < n_target:
            break
    out["or_a"], out["or_scale_n"] = best2[1], best2[2]
    return out


def masks(ind, cal, thz=1.5):
    z = np.abs(ind["z"]); rv = ind["rvol"]; E = ind["E"]
    thv = ind["thv"]
    m = {}
    m["and_base"] = E & (z >= thz) & (rv >= thv)
    m["price_base"] = E & (z >= thz)
    m["vol_base"] = E & (rv >= thv)
    m["or_base"] = E & ((z >= thz) | (rv >= thv))
    m["price_eq"] = E & (z >= cal["qz"])
    m["vol_eq"] = E & (rv >= cal["qv"])
    m["or_eq"] = E & ((z >= cal["or_qz"]) | (rv >= cal["or_qv"]))
    m["or_scale"] = E & ((z >= cal["or_a"] * thz) | (rv >= cal["or_a"] * thv))
    return m


# ---------- 诊断量 ----------
def diag(ind, T):
    T = np.asarray(T, int)
    r = ind["r"][T]; rv = ind["rvol"][T]; z = np.abs(ind["z"][T])
    g = ind["gap"][T]; it = ind["itd"][T]
    ok = (~np.isnan(g)) & (~np.isnan(it))
    d = dict(
        n=int(len(T)),
        med_abs_ret_pct=float(np.median(np.abs(r)) * 100),
        med_rvol=float(np.median(rv)),
        med_absz=float(np.median(z)),
        frac_rvol_lt1=float(np.mean(rv < 1.0)),
        frac_rvol_ge2=float(np.mean(rv >= 2.0)),
        frac_rvol_ge3=float(np.mean(rv >= 3.0)),
        frac_absz_ge15=float(np.mean(z >= 1.5)),
        frac_down=float(np.mean(r < 0)),
        persistence=float(np.mean(np.isin(T + 1, T))) if len(T) else float("nan"),
    )
    d["frac_gap_dom"] = float(np.mean(np.abs(g[ok]) > np.abs(it[ok]))) if ok.sum() else float("nan")
    return d


def run_ticker(r, verbose=True):
    ind = prep2(r)
    if len(ind["Eidx"]) < 300:
        return None
    m = masks(ind, {"qz": np.inf, "qv": np.inf, "or_qz": np.inf, "or_qv": np.inf,
                    "or_a": 1.0, "or_m": 0, "or_n": 0, "or_scale_n": 0})
    n_and = int(m["and_base"].sum())
    if n_and < 10:
        return None
    cal = calibrate(ind, n_and)
    M = masks(ind, cal)
    rec = dict(sym=ind["sym"], asset=ind["asset"], sector=ind["sector"],
               size_tier=ind["size_tier"], vol_tier=ind["vol_tier"],
               vol_tier_csv=ind["vol_tier_csv"], stratum=ind["stratum"],
               years=round(ind["years"], 2), sigma_ann=round(ind["sigma_ann"], 4),
               advol=ind["advol"], thv=ind["thv"], n_elig=int(len(ind["Eidx"])),
               cal={k: (round(v, 4) if isinstance(v, float) else v) for k, v in cal.items()},
               arms={}, trig={})
    for name, mask in M.items():
        T = np.flatnonzero(mask)
        nb = NBOOT_MAIN if name in ("and_base", "price_eq", "vol_eq", "or_eq") else NBOOT_AUX
        res = ratio_ci(ind, T, nboot=nb)
        a = dict(n=int(len(T)), freq=round(len(T) / ind["years"], 2))
        a.update(diag(ind, T))
        if res:
            a.update(blocks=res["blocks"], mult=round(res["mult"], 4),
                     lo=round(res["lo"], 4), hi=round(res["hi"], 4),
                     passed=bool(res["pass_"]))
        else:
            a.update(blocks=None, mult=None, lo=None, hi=None, passed=False)
        rec["arms"][name] = a
        rec["trig"][name] = T.tolist()
    if verbose:
        f = lambda k: rec["arms"][k]["mult"]
        print(f"{ind['sym']:<7}{ind['asset']:<10}n={n_and:<4} "
              f"AND {f('and_base')}  P {f('price_eq')}(θz'={cal['qz']:.2f})  "
              f"V {f('vol_eq')}(θv'={cal['qv']:.2f})  "
              f"OR {f('or_eq')}(n={rec['arms']['or_eq']['n']})", flush=True)
    return rec


if __name__ == "__main__":
    t0 = time.time(); out = []
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for r in roster():
        if only and r["symbol"] not in only:
            continue
        try:
            rec = run_ticker(r)
        except Exception as e:
            print("ERR", r["symbol"], e, flush=True); continue
        if rec: out.append(rec)
    os.makedirs(OUT, exist_ok=True)
    tag = "arms_subset.json" if only else "arms.json"
    json.dump(out, open(os.path.join(OUT, tag), "w"), indent=1, ensure_ascii=False)
    print(f"\n完成 {len(out)} 只  用时 {time.time()-t0:.0f}s")
