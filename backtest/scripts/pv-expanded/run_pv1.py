"""PV1 主跑：92 美股 + 25 加密（不含基准 SPY），R28 定稿口径。
输出 pv1_per_ticker.json"""
import json, numpy as np, time
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci

t0=time.time(); out=[]
for r in roster():
    ind=prep(r)
    T=pv1_trigger(ind,1.5,ind["thv"])
    T=[t for t in T if not np.isnan(ind["V"][t])]
    res=ratio_ci(ind,T)
    rec=dict(sym=ind["sym"], asset=ind["asset"], sector=ind["sector"],
             size_tier=ind["size_tier"], vol_tier=ind["vol_tier"], vol_tier_csv=ind["vol_tier_csv"],
             stratum=ind["stratum"], bars=int(ind["n"]), years=round(ind["years"],2),
             sigma_ann=round(ind["sigma_ann"],4), sigma_csv=ind["sigma_csv"],
             rho=round(ind["rho"],4), rho2y=round(ind["rho2y"],4), kurt=round(ind["kurt"],2),
             n_trig=len(T), freq=round(len(T)/ind["years"],2) if ind["years"]>0 else None)
    if res:
        rec.update(blocks=res["blocks"], mult=round(res["mult"],3), lo=round(res["lo"],3),
                   hi=round(res["hi"],3), passed=bool(res["pass_"]), nbase=res["nbase"])
    else:
        rec.update(blocks=None, mult=None, lo=None, hi=None, passed=False, nbase=None, note="样本不足")
    out.append(rec)
    print(f"{rec['sym']:<7}{rec['asset']:<10}{str(rec['vol_tier']):<12}{rec['n_trig']:>5}"
          f"{str(rec['blocks']):>5}{(rec['mult'] if rec['mult'] else float('nan')):>7.2f}"
          f"  [{rec['lo']}, {rec['hi']}] {'🟢' if rec['passed'] else '❌'}", flush=True)
json.dump(out, open("pv1_per_ticker.json","w"), indent=1, ensure_ascii=False)
print(f"\n完成 {len(out)} 只  用时 {time.time()-t0:.0f}s  通过 {sum(1 for x in out if x['passed'])}")
