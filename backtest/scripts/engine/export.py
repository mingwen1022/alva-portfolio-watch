import math, json, statistics as st, os
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),"ohlc")
W=90; FWD=5
STOCKS=["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
CRYPTO=["BTC","ETH","SOL","DOGE"]
med=st.median
def r2(x,n=2): return None if x is None else round(x,n)

out={}
for sym in STOCKS+CRYPTO:
    cls = "股票" if sym in STOCKS else "加密"
    ann = 252 if cls=="股票" else 365
    rows=[l.strip().split(",") for l in open(f"{D}/{sym}.csv") if l.strip()]
    d=[x[0] for x in rows]
    o=[float(x[1]) for x in rows]; h=[float(x[2]) for x in rows]
    lo=[float(x[3]) for x in rows]; c=[float(x[4]) for x in rows]; v=[float(x[5]) for x in rows]
    n=len(rows)
    r=[None]*n
    for i in range(1,n):
        if c[i-1]>0 and c[i]>0: r[i]=math.log(c[i]/c[i-1])
    z=[None]*n; rv=[None]*n; av=[None]*n; sig=[None]*n
    for t in range(n):
        w=[r[i] for i in range(max(1,t-W),t) if r[i] is not None]
        if len(w)>=60 and r[t] is not None:
            m=med(w); mad=med([abs(x-m) for x in w]); s=1.4826*mad
            if s>0:
                z[t]=(r[t]-m)/s; sig[t]=s; av[t]=s*math.sqrt(ann)
        vw=[v[i] for i in range(max(0,t-W),t) if v[i]>0]
        if len(vw)>=60 and med(vw)>0: rv[t]=v[t]/med(vw)
    fv=[None]*n; fr=[None]*n
    for t in range(n):
        if t+FWD>=n or sig[t] is None: continue
        rr=[r[t+k] for k in range(1,FWD+1)]
        if any(x is None for x in rr): continue
        fv[t]=math.sqrt(sum(x*x for x in rr)/FWD)/sig[t]
        fr[t]=(math.exp(sum(rr))-1)*100
    out[sym]=dict(cls=cls, d=d,
        o=[r2(x,4) for x in o], h=[r2(x,4) for x in h], l=[r2(x,4) for x in lo], c=[r2(x,4) for x in c],
        v=[round(x) for x in v],
        z=[r2(x) for x in z], rv=[r2(x) for x in rv],
        av=[r2(x,3) for x in av], fv=[r2(x) for x in fv], fr=[r2(x) for x in fr],
        ret=[r2(x*100,2) if x is not None else None for x in r])
json.dump(out, open("signals.json","w"), ensure_ascii=False, separators=(",",":"))
print("tickers", len(out), "bytes", os.path.getsize("signals.json"))
