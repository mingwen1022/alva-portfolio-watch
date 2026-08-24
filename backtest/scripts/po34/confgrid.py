"""把「组合 × 任意时刻」的确认查询做成可重复调用的网格，用于安慰剂平移。

market.py 的 confirm_portfolio 每次都要 searchsorted，安慰剂要跑几百遍，
这里一次性把每个组合的 (day,k) → confirmed 布尔矩阵和 bar 起始 epoch 拿出来，
之后任意 epoch 查表即可。口径与 market.py 完全一致（同一函数算出来的）。
"""
import os, sys, json, gzip
import numpy as np
sys.path.insert(0, "/Users/ming/project/alva/backtest/scripts/po-luna")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M
import port_defs as PD
import compute_conf as CC

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "grid_cache.npz")


def build():
    basis = PD.basis_portfolios()
    hold = CC.holdout_portfolios()
    ports = {("B:" + k): v for k, v in basis.items()}
    ports.update({("H:" + k): v for k, v in hold.items()})
    out = {}
    meta = {}
    for name, mem in ports.items():
        pp = M.portfolio_prep(mem)
        AR, SIG, RV, BS = pp["AR"], pp["SIG"], pp["RV"], pp["BS"]
        with np.errstate(invalid="ignore", divide="ignore"):
            Z = AR / SIG
            conf = (np.abs(Z) >= M.AR_THR) | (RV >= M.RVOL_THR)
        valid = (~np.isnan(AR)) & (~np.isnan(SIG)) & (SIG > 0)
        span = pp["span"]; K = pp["K"]
        kok = np.zeros(K, bool); kok[1:K - span + 1] = True
        valid &= kok[None, :]
        out[name + "|conf"] = np.where(valid, conf, False)
        out[name + "|valid"] = valid
        out[name + "|bs"] = BS
        meta[name] = dict(members=mem, K=int(K), span=int(span))
    np.savez_compressed(CACHE, **out)
    json.dump(meta, open(os.path.join(HERE, "grid_meta.json"), "w"), ensure_ascii=False)
    return out, meta


class Grid:
    def __init__(self):
        if not os.path.exists(CACHE):
            build()
        z = np.load(CACHE)
        self.meta = json.load(open(os.path.join(HERE, "grid_meta.json")))
        self.g = {}
        for name in self.meta:
            bs = z[name + "|bs"]
            flat = bs.reshape(-1)
            ok = np.flatnonzero(~np.isnan(flat))
            self.g[name] = dict(conf=z[name + "|conf"].reshape(-1),
                                valid=z[name + "|valid"].reshape(-1),
                                flat=flat, ok=ok, sorted=flat[ok])

    def query(self, name, eps):
        """eps: int array of epochs → (valid bool array, confirmed bool array)"""
        g = self.g[name]
        pos = np.searchsorted(g["sorted"], eps, side="left")
        inr = pos < len(g["ok"])
        j = np.where(inr, g["ok"][np.clip(pos, 0, len(g["ok"]) - 1)], 0)
        v = g["valid"][j] & inr
        c = g["conf"][j] & v
        return v, c

    def names(self):
        return list(self.meta)


if __name__ == "__main__":
    build()
    G = Grid()
    # 自洽检验：网格查表结果必须与 compute_conf.py 逐条算的完全一致
    cp = json.load(gzip.open(os.path.join(HERE, "conf_ports.json.gz"), "rt"))
    from datetime import datetime, timezone
    eps = np.array([int(datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
                    for t in cp["ts"]])
    bad = 0
    for name in G.names():
        v, c = G.query(name, eps)
        ref = cp["conf"][name]
        rv = np.array([x is not None for x in ref])
        rc = np.array([bool(x[0]) if x else False for x in ref])
        d1 = int((v != rv).sum()); d2 = int((c != rc).sum())
        if d1 or d2:
            print(f"  ⚠️ {name}: valid 差 {d1}, conf 差 {d2}")
            bad += 1
    print("网格与逐条计算一致" if not bad else f"{bad} 个组合不一致")
