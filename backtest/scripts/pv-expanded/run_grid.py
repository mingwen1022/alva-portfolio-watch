"""阈值网格：θz × θv 逐标的重跑，用于检验决策 #2（θz 不分档）与 #3（θv 只按资产类别）。
判据仍是 95% 下界 > 1.0 ∧ 块数 ≥ 5；触发频率只作描述量（决策 #9：频率不能当判据）。"""
import json, numpy as np, time
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci

ZS=[1.0,1.25,1.5,1.75,2.0,2.5]
VS=[1.0,1.5,2.0,2.5,3.0,3.5]
t0=time.time(); out=[]
for r in roster():
    ind=prep(r)
    rec=dict(sym=ind["sym"],asset=ind["asset"],vol_tier=ind["vol_tier"],size_tier=ind["size_tier"],
             sector=ind["sector"],sigma_ann=round(ind["sigma_ann"],4),rho=round(ind["rho"],4),
             years=round(ind["years"],2),g={})
    for z in ZS:
        for v in VS:
            T=[t for t in pv1_trigger(ind,z,v) if not np.isnan(ind["V"][t])]
            if len(T)<3: continue
            res=ratio_ci(ind,T,nboot=800)
            if res: rec["g"][f"{z}|{v}"]=dict(n=res["n"],blocks=res["blocks"],
                        mult=round(res["mult"],3),lo=round(res["lo"],3),passed=bool(res["pass_"]),
                        freq=round(len(T)/ind["years"],2))
    out.append(rec); print(rec["sym"],len(rec["g"]),f"{time.time()-t0:.0f}s",flush=True)
json.dump(out,open("grid.json","w"),indent=1,ensure_ascii=False)
print("done",time.time()-t0)
