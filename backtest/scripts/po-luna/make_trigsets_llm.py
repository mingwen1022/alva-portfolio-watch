"""用全量 M18 标签构造 PO1/PO2/PO3 的触发集。

PO1 = M17 ∧ factual ∧ M19新              不等确认 → offset 0
PO2 = M17 ∧ rhetorical ∧ M19新 ∧ 确认     等 Δ 窗口 → offset 2（剔除与确认窗重叠）
PO3 = M24only ∧ M16高敏感 ∧ M19新 ∧ 确认  同上

对照组：
  PO1_rhet   M17 ∧ rhetorical（不等确认）—— 与 PO1 唯一差别就是 M18，直接看判据分不分得开
  PO_all17   M17 全体（删掉 M18 后 PO1/PO2 合并的触发面）
"""
import os, sys, json, gzip
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market as M

S = os.environ["S"]; ROOT = f"{S}/porun2"
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"

recs = json.load(gzip.open(f"{DERIV}/candidates.json.gz","rt",encoding="utf-8"))
conf = {r["cid"]: r for r in json.load(gzip.open(f"{DERIV}/confirm.json.gz","rt",encoding="utf-8"))}
lab  = {o["id"]: o for o in json.load(gzip.open(f"{ROOT}/out/m18_luna_full.json.gz","rt",encoding="utf-8"))}
raw  = json.load(open(f"{ROOT}/out/rawlabels.json"))

A = [r for r in recs if r["layer"] in ("main18","cb4")]
def fact_raw(r): 
    v = raw.get(r["cid"]);  return v is not None and v["spec_raw"]=="factual"
def fact_pipe(r):
    v = lab.get(r["cid"]);  return v is not None and v["specificity"]=="factual"
def cf(r,key):
    c = conf.get(r["cid"],{}).get(key);  return bool(c and c["c"])
E = M.to_epoch

ts = {}
# —— 不等确认（offset 0）
ts["PO1_raw"]        = [E(r["ts"]) for r in A if r["h17"] and fact_raw(r)]
ts["PO1_pipe"]       = [E(r["ts"]) for r in A if r["h17"] and fact_pipe(r)]
ts["PO1rhet_raw"]    = [E(r["ts"]) for r in A if r["h17"] and not fact_raw(r)]
ts["PO1rhet_pipe"]   = [E(r["ts"]) for r in A if r["h17"] and not fact_pipe(r)]
ts["PO_all17"]       = [E(r["ts"]) for r in A if r["h17"]]
json.dump(ts, open(f"{ROOT}/out/trigsets_llm_off0.json","w"))

# —— 等确认（offset 2）
ts2 = {}
ts2["PO2_rhet_confsemi"]   = [E(r["ts"]) for r in A if r["h17"] and not fact_pipe(r) and cf(r,"P_semi")]
ts2["PO2_rhet_confcrypto"] = [E(r["ts"]) for r in A if r["h17"] and not fact_pipe(r) and cf(r,"P_crypto")]
ts2["PO1_fact_confsemi"]   = [E(r["ts"]) for r in A if r["h17"] and fact_pipe(r) and cf(r,"P_semi")]
ts2["PO1_fact_confcrypto"] = [E(r["ts"]) for r in A if r["h17"] and fact_pipe(r) and cf(r,"P_crypto")]
ts2["PO3_confsemi"]        = [E(r["ts"]) for r in A if r["h24"] and not r["h17"] and cf(r,"P_semi")]
ts2["PO3_confcrypto"]      = [E(r["ts"]) for r in A if r["h24"] and not r["h17"] and cf(r,"P_crypto")]
json.dump(ts2, open(f"{ROOT}/out/trigsets_llm_off2.json","w"))

for k,v in list(ts.items())+list(ts2.items()):
    print(f"{k:26} {len(v)}")
