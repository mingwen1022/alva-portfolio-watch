"""半样本可复现性：θ 的选择是否依赖样本窗口（F 判据当年就是栽在这一条）。"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L
TH=[0.05,0.075,0.10,0.15,0.20]
CUT="2023-06-01"
OUT={}
for sym in L.CRYPTO:
    S=L.build(sym); f00,fmax,meta=L.load_funding(sym); oi=L.load_oi(sym)
    dates=S["dates"]; fd=[d for d in dates if d in f00]; od=[d for d in dates if d in oi]
    rec={}
    for half,sel in (("H1",lambda d: d<CUT),("H2",lambda d: d>=CUT)):
        ev=set(L.to_idx(S,[d for d in fd if sel(d)]))
        ev3=set(L.to_idx(S,[d for d in od if sel(d)]))
        rec[half]={}
        for th in TH:
            T=[i for i in L.to_idx(S,L.dr1_days(f00,fd,th)) if i in ev]
            r=L.ratio_ci(S,T,"fwd",eval_idx=ev,B=1000) if T else None
            rec[half]["DR1@%g"%th]=None if r is None else dict(n=r['n'],blocks=r['blocks'],mult=r['mult'],lo=r['lo'],pass_=r['pass_'])
        T3=[i for i in L.to_idx(S,L.dr3_days(oi,od,0.10)) if i in ev3]
        r=L.ratio_ci(S,T3,"fwd",eval_idx=ev3,B=1000) if T3 else None
        rec[half]["DR3@0.1"]=None if r is None else dict(n=r['n'],blocks=r['blocks'],mult=r['mult'],lo=r['lo'],pass_=r['pass_'])
    OUT[sym]=rec
    print(sym,"ok",file=sys.stderr)
json.dump(OUT,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","out","split.json"),"w"),ensure_ascii=False,indent=1)
