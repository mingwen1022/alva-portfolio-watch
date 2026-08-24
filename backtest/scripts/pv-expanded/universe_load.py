"""样本池装载 + 逐标的属性（波动档 / 市值档 / 行业 / ρ）"""
import csv, math, numpy as np
from pv_engine import load_universe, indicators

UNIV = "/Users/ming/project/alva/backtest/universe/universe.csv"

def roster(include_benchmark=False):
    out=[]
    for r in csv.DictReader(open(UNIV)):
        if r["stratum"]=="benchmark" and not include_benchmark: continue
        out.append(r)
    return out

def vol_tier(sig):
    if sig is None or np.isnan(sig): return None
    return "低波 <25%" if sig<0.25 else ("中波 25-50%" if sig<0.50 else "高波 >50%")

def prep(r):
    sym=r["symbol"]; asset="crypto" if r["asset_class"]=="crypto" else "us_equity"
    ann=365 if asset=="crypto" else 252
    ds,c,v=load_universe(sym,asset)
    ind=indicators(c,v,ann)
    ind["dates"]=ds; ind["sym"]=sym; ind["asset"]=asset; ind["ann"]=ann
    ind["thv"]=3.0 if asset=="crypto" else 2.0
    valid=np.flatnonzero(~np.isnan(ind["V"]))
    ind["valid"]=valid
    ind["years"]=len(valid)/ann
    av=ind["avol"][~np.isnan(ind["avol"])]
    ind["sigma_ann"]=float(np.median(av)) if len(av) else float("nan")
    z=ind["z"][~np.isnan(ind["z"])]
    ind["rho"]=float(np.mean(np.abs(z)>=1.5)) if len(z) else float("nan")
    z2=ind["z"][-min(len(ind["z"]),504):]; z2=z2[~np.isnan(z2)]
    ind["rho2y"]=float(np.mean(np.abs(z2)>=1.5)) if len(z2) else float("nan")
    ind["kurt"]=float(((z-z.mean())**4).mean()/ (z.var()**2) - 3) if len(z)>10 else float("nan")
    ind["vol_tier"]=vol_tier(ind["sigma_ann"])
    ind["vol_tier_csv"]={"low":"低波 <25%","mid":"中波 25-50%","high":"高波 >50%"}.get(r["vol_tier"])
    ind["size_tier"]={"large":"大盘","mid":"中盘","small":"小盘"}.get(r["size_tier"],"—")
    ind["sector"]=r["sector"]; ind["stratum"]=r["stratum"]
    ind["sigma_csv"]=float(r["sigma_ann"]) if r["sigma_ann"] else float("nan")
    return ind
