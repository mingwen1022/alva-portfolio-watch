"""基础组合定义 —— 只用 universe.csv 的 sector 与 avg_dollar_vol，事前可定，不看任何回测结果。

规则先写定再执行：
  每个 GICS 部门取该部门内 avg_dollar_vol_usd 最大的 4 只（不足 4 只则全取），等权
  加密取 avg_dollar_vol_usd 最大的 4 个，等权
  SPY 不进任何组合（它是基准）
"""
import csv, sys, os
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run/scripts")
import load_intraday as L

UNIV = "/Users/ming/project/alva/backtest/universe/universe.csv"
NPER = 4

def load_universe():
    rows = list(csv.DictReader(open(UNIV)))
    have = set(L.symbols())
    out = []
    for r in rows:
        if r["symbol"] == "SPY" or r["symbol"] not in have:
            continue
        if not r["sector"]:
            continue
        try:
            r["adv"] = float(r["avg_dollar_vol_usd"] or 0)
        except ValueError:
            r["adv"] = 0.0
        out.append(r)
    return out

def basis_portfolios():
    rows = load_universe()
    bysec = {}
    for r in rows:
        bysec.setdefault(r["sector"], []).append(r)
    ports = {}
    for sec, rs in bysec.items():
        rs.sort(key=lambda x: -x["adv"])
        ports[sec] = [r["symbol"] for r in rs[:NPER]]
    return ports

if __name__ == "__main__":
    rows = load_universe()
    print("universe with intraday:", len(rows))
    for sec, mem in sorted(basis_portfolios().items()):
        print(f"  {sec:8} {mem}")
