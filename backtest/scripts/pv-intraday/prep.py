"""逐标的算 M 层网格并缓存到 derived/cache/<sym>_<grid>.npz"""
import sys, os, numpy as np
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"
sys.path.insert(0, f"{BASE}/scripts")
from load_intraday import symbols, to_grid
from engine import build_grid, indicators, fwd_vol

CACHE = f"{BASE}/derived/cache"
os.makedirs(CACHE, exist_ok=True)

def prep(sym, grid_kind, force=False):
    f = f"{CACHE}/{sym}_{grid_kind}.npz"
    if os.path.exists(f) and not force:
        return dict(np.load(f, allow_pickle=True))
    g = to_grid(sym, grid_kind)
    C, Vv, present, filled = build_grid(g["sess"], g["slot"], g["close"], g["vol"], g["nslots"])
    ind = indicators(C, Vv, g["nslots"], cum_rvol=True)
    # bar 局部 RVOL（变体）
    ind2 = indicators(C, Vv, g["nslots"], cum_rvol=False)
    VA, LA = fwd_vol(ind["r"], 5, session_bound=True, mode="fixed")
    VAX, _ = fwd_vol(ind["r"], 5, session_bound=False, mode="fixed")
    VB, LB = fwd_vol(ind["r"], 0, session_bound=True, mode="toclose")
    out = dict(r=ind["r"], sigma=ind["sigma"], z=ind["z"], rvol=ind["rvol"],
               rvol_bar=ind2["rvol"], VA=VA, VAX=VAX, LA=LA, VB=VB, LB=LB,
               present=present, filled=filled, days=g["days"], nslots=np.array(g["nslots"]),
               kind=np.array(g["kind"]))
    np.savez_compressed(f, **out)
    return out

if __name__ == "__main__":
    import time
    t0 = time.time()
    import sys as _s
    from load_intraday import _index
    only = _s.argv[1] if len(_s.argv) > 1 else "RTH"      # RTH | ETH | ALL
    idx = _index()
    syms = sorted(idx.keys())
    if only == "ETH":
        # ETH 只跑扫描子集（覆盖率已证明不可用，仅留证据）
        from roster import grid_subset
        keep = {r["symbol"] for r in grid_subset()[0]}
        syms = [x for x in syms if x in keep]
    for i, s in enumerate(syms):
        kind = idx[s][0]
        grids = ["UTC"] if kind == "crypto" else (["RTH", "ETH"] if only == "ALL" else [only])
        if kind == "crypto" and only == "ETH": continue
        for gk in grids:
            try: prep(s, gk)
            except Exception as e: print("ERR", s, gk, e)
        if i % 10 == 0: print(f"{i}/{len(syms)} {s} {time.time()-t0:.0f}s", flush=True)
    print("done", time.time() - t0)
