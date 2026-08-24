"""对每个组合、每条候选帖，算市场确认。复用 backtest/scripts/po-luna/market.py，口径不变。

组合分两类：
  basis   12 个部门组合（11 GICS + 加密），用于拟合 M16 的部门敏感度矩阵
  holdout 12 个跨部门混合股票组合（种子固定，事前抽），只用于检验，不参与拟合
输出 conf_ports.json.gz： {cid: {port: 0/1 或 None}}，另存 z / rv / day / k
"""
import os, sys, json, gzip, random
sys.path.insert(0, "/Users/ming/project/alva/backtest/scripts/po-luna")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M
import port_defs as PD

OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 20260820


def holdout_portfolios():
    """混合部门股票组合：每个从 5 个不同部门各抽 1 只，等权。规则先写定。"""
    rows = PD.load_universe()
    bysec = {}
    for r in rows:
        if r["sector"] == "加密":
            continue
        bysec.setdefault(r["sector"], []).append(r["symbol"])
    for k in bysec:
        bysec[k].sort()
    secs = sorted(bysec)
    rng = random.Random(SEED)
    out = {}
    for i in range(12):
        pick = rng.sample(secs, 5)
        out[f"H{i+1}"] = sorted(rng.choice(bysec[s]) for s in pick)
    # 加密混合组合（加密内部无部门，随机抽 4 个）
    cry = sorted(r["symbol"] for r in rows if r["sector"] == "加密")
    for i in range(4):
        out[f"HC{i+1}"] = sorted(rng.sample(cry, 4))
    return out


def main():
    cand = json.load(gzip.open("/Users/ming/project/alva/backtest/data/po-derived/candidates.json.gz", "rt"))
    basis = PD.basis_portfolios()
    hold = holdout_portfolios()
    ports = {("B:" + k): v for k, v in basis.items()}
    ports.update({("H:" + k): v for k, v in hold.items()})
    print(json.dumps(ports, ensure_ascii=False, indent=1))
    eps = [M.to_epoch(r["ts"]) for r in cand]
    res = {}
    for name, mem in ports.items():
        pp = M.portfolio_prep(mem)
        col = []
        for ep in eps:
            c = M.confirm_portfolio(pp, ep)
            col.append(None if c is None else [int(c["confirmed"]), round(c["ar_z"], 3),
                                               (None if c["rvol"] is None else round(c["rvol"], 3)),
                                               c["day"], c["k"]])
        got = [x for x in col if x]
        print(f"{name:16} n={len(got):>6} ({len(got)/len(col):5.1%})  确认率 {sum(x[0] for x in got)/max(len(got),1):6.2%}")
        res[name] = col
    with gzip.open(os.path.join(OUT, "conf_ports.json.gz"), "wt") as f:
        json.dump(dict(cids=[r["cid"] for r in cand], ts=[r["ts"] for r in cand],
                       ports=ports, conf=res), f)
    print("saved")


if __name__ == "__main__":
    main()
