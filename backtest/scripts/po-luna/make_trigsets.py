"""构造不依赖 M18 的触发集（判据机器的先行验证 + PO3 主体）。"""
import os, sys, json, gzip
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")
recs = json.load(gzip.open(f"{DERIV}/candidates.json.gz", "rt", encoding="utf-8"))
conf = {r["cid"]: r for r in json.load(gzip.open(f"{DERIV}/confirm.json.gz", "rt", encoding="utf-8"))}

A = [r for r in recs if r["layer"] in ("main18", "cb4")]
ts = {}
ts["M17_tierA"] = [M.to_epoch(r["ts"]) for r in A if r["h17"]]
ts["M24only_tierA"] = [M.to_epoch(r["ts"]) for r in A if r["h24"] and not r["h17"]]
ts["M24any_tierA"] = [M.to_epoch(r["ts"]) for r in A if r["h24"]]
ts["M17_media"] = [M.to_epoch(r["ts"]) for r in recs if r["layer"] == "media7" and r["h17"]]
# 已确认子集（PO2/PO3 的触发定义里含市场确认）
def cf(r, key):
    c = conf.get(r["cid"], {}).get(key)
    return bool(c and c["c"])
ts["M24only_tierA_conf_semi"] = [M.to_epoch(r["ts"]) for r in A if r["h24"] and not r["h17"] and cf(r, "P_semi")]
ts["M24only_tierA_conf_crypto"] = [M.to_epoch(r["ts"]) for r in A if r["h24"] and not r["h17"] and cf(r, "P_crypto")]
ts["M17_tierA_conf_semi"] = [M.to_epoch(r["ts"]) for r in A if r["h17"] and cf(r, "P_semi")]
for k, v in ts.items():
    print(f"{k:32} {len(v)}")
json.dump(ts, open(f"{DERIV}/trigsets_nollm.json", "w"))
