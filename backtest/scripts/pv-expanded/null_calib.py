"""零假设校准：把触发日换成同数量、同块长分布的随机日，判据的假阳性率应接近 2.5%。
不做这一步，「106/116 通过」无法与随机期望比较。"""
import json, numpy as np
from universe_load import roster, prep
from pv_engine import pv1_trigger, ratio_ci, blocks_of

REP=5
rng0=np.random.default_rng(7)
res=[]
for r in roster():
    ind=prep(r)
    T=[t for t in pv1_trigger(ind,1.5,ind["thv"]) if not np.isnan(ind["V"][t])]
    if len(T)<3: continue
    bl=blocks_of(np.array(T)); sizes=[len(b) for b in bl]
    valid=ind["valid"]
    lo,hi=int(valid.min()),int(valid.max())
    for rep in range(REP):
        fake=[]
        for sz in sizes:
            st=int(rng0.integers(lo,hi-sz-1))
            fake.extend(range(st,st+sz))
        fake=sorted(set(i for i in fake if not np.isnan(ind["V"][i])))
        if len(fake)<3: continue
        out=ratio_ci(ind,fake,nboot=1000,seed=20260819+rep)
        if out: res.append(dict(sym=ind["sym"],rep=rep,mult=out["mult"],lo=out["lo"],
                                blocks=out["blocks"],passed=bool(out["pass_"])))
json.dump(res,open("null_calib.json","w"),indent=1,ensure_ascii=False)
p=[x for x in res if x["passed"]]
import statistics as st
print(f"随机日对照：{len(res)} 次  通过 {len(p)}  假阳性率 {len(p)/len(res)*100:.1f}%")
print(f"倍数中位 {st.median(x['mult'] for x in res):.3f}   下界中位 {st.median(x['lo'] for x in res):.3f}")
