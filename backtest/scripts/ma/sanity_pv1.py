"""引擎自检：用同一套 V / 整块自助复现 plan.md 里已审核过的 PV1 逐标的数字。
PV1 = |z_rob| >= 1.5 AND RVOL >= 2.0（股）/3.0（币），全样本 2018-01 起。
"""
import math, statistics as st
from ma_engine import build, ratio_ci, STOCKS, CRYPTO, W, med, D_PX

def rvol_series(sym):
    rows=[]
    for ln in open(f"{D_PX}/{sym}.csv"):
        d,c,v=ln.strip().split(","); rows.append((d,float(c),float(v)))
    rows.sort(); vol=[r[2] for r in rows]; n=len(rows)
    rv=[None]*n
    for t in range(n):
        w=[vol[i] for i in range(max(0,t-W),t) if vol[i] and vol[i]>0]
        if len(w)>=60:
            m=med(w)
            if m>0: rv[t]=vol[t]/m
    return rv

def zrob(s):
    n=s["n"]; r=s["r"]; z=[None]*n
    for t in range(n):
        w=[r[i] for i in range(max(1,t-W),t) if r[i] is not None]
        if len(w)<60 or r[t] is None: continue
        m=med(w); mad=med([abs(x-m) for x in w]); sr=1.4826*mad
        if sr>0: z[t]=(r[t]-m)/sr
    return z

for sym,ann,tv in [("XOM",252,2.0),("AAPL",252,2.0),("MSFT",252,2.0),("NVDA",252,2.0),
                   ("MSTR",252,2.0),("AMD",252,2.0),("KO",252,2.0),("PLTR",252,2.0),
                   ("RIVN",252,2.0),("TSLA",252,2.0),("SOFI",252,2.0)]:
    s=build(sym,ann); z=zrob(s); rv=rvol_series(sym)
    T=[t for t in range(s["n"]) if z[t] is not None and rv[t] is not None and abs(z[t])>=1.5 and rv[t]>=tv]
    lo=min(i for i in range(s["n"]) if s["V"][i] is not None)
    hi=max(i for i in range(s["n"]) if s["V"][i] is not None)
    r=ratio_ci(s,T,lo,hi)
    print(f"{sym:6s} 触发 {r['n']:4d} 块 {r['blocks']:4d}  倍数 {r['mult']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]")
