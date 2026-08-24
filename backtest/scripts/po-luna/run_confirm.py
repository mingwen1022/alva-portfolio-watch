"""逐候选算市场确认（0 credits）。输出 derived/confirm.json.gz。

标的级（PO1/PO2 的 M17 路）  NVDA · AMD · MSFT
组合级（PO3 的 M24 路）      半导体组合 = NVDA+AMD+MSFT 等权（M16 高敏感：β_组合 1.72 > 1.2）
                             防御组合   = KO+JNJ+GIS+UL 等权（M16 低敏感：β_组合 < 1.2）← M16 的对照
                             加密组合   = BTC+ETH+SOL 等权（E_加密 100% > 20% → 高敏感）
"""
import os, sys, json, gzip
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")
SYMS = ["NVDA", "AMD", "MSFT"]
PORTS = {
    "semi": ["NVDA", "AMD", "MSFT"],
    "defensive": ["KO", "JNJ", "GIS", "UL"],
    "crypto": ["BTC", "ETH", "SOL"],
}


def main():
    recs = json.load(gzip.open(os.path.join(BASE, "derived/candidates.json.gz"), "rt", encoding="utf-8"))
    for s in SYMS:
        M.prep(s)
    pps = {k: M.portfolio_prep(v) for k, v in PORTS.items()}
    out = []
    for r in recs:
        ep = M.to_epoch(r["ts"])
        rec = dict(cid=r["cid"], ts=r["ts"], handle=r["handle"], layer=r["layer"],
                   ctype=r["ctype"], t0_trust=r["t0_trust"],
                   m17=bool(r["h17"]), m24=bool(r["h24"]), ep=ep)
        for s in SYMS:
            c = M.confirm(s, ep)
            rec[s] = None if c is None else dict(z=round(c["ar_z"], 3),
                                                 rv=(None if c["rvol"] is None else round(c["rvol"], 3)),
                                                 c=c["confirmed"], day=c["day"], k=c["k"])
        for k, pp in pps.items():
            c = M.confirm_portfolio(pp, ep)
            rec["P_" + k] = None if c is None else dict(z=round(c["ar_z"], 3),
                                                        rv=(None if c["rvol"] is None else round(c["rvol"], 3)),
                                                        c=c["confirmed"], day=c["day"], k=c["k"])
        out.append(rec)
    with gzip.open(os.path.join(BASE, "derived/confirm.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(out, f)

    # 覆盖与基线对照
    print(f"候选 {len(out)}")
    for s in SYMS + ["P_semi", "P_defensive", "P_crypto"]:
        got = [r for r in out if r[s]]
        cf = sum(1 for r in got if r[s]["c"])
        print(f"  {s:12} 有窗口 {len(got):>6} ({len(got)/len(out):>5.1%})   确认 {cf:>5} ({cf/max(len(got),1):>5.1%})")

    print("\n按通路（Tier A = 22 账号：main18 + cb4）")
    A = [r for r in out if r["layer"] in ("main18", "cb4")]
    for name, sel in (("M17 命中", lambda r: r["m17"]), ("仅 M24", lambda r: r["m24"] and not r["m17"])):
        sub = [r for r in A if sel(r)]
        for s in ("NVDA", "P_semi", "P_crypto"):
            got = [r for r in sub if r[s]]
            cf = sum(1 for r in got if r[s]["c"])
            print(f"  {name:8} {s:10} n={len(got):>5}  确认率 {cf/max(len(got),1):>6.1%}")


if __name__ == "__main__":
    main()
