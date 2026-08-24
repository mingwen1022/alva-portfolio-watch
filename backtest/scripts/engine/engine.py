import math, json, statistics as st, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

W      = 90                      # 基线窗口（不含当日）
FWD    = 5                       # 前瞻窗口
ZS     = [1.5, 2.0, 2.5]
VS     = [1.5, 2.0, 3.0]
ABS_FLOOR = 0.05                 # R2 绝对值兜底

STOCKS = ["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
CRYPTO = ["BTC","ETH","SOL","DOGE"]

def load(sym):
    rows=[]
    for ln in open(f"{D}/{sym}.csv"):
        d,c,v = ln.strip().split(",")
        rows.append((d, float(c), float(v)))
    return rows

def med(xs): return st.median(xs)

def series(sym):
    """returns dict of aligned arrays with derived stats; index 0 is oldest"""
    rows = load(sym)
    dates = [r[0] for r in rows]; close=[r[1] for r in rows]; vol=[r[2] for r in rows]
    n=len(rows)
    r=[None]*n
    for i in range(1,n):
        if close[i-1]>0 and close[i]>0: r[i]=math.log(close[i]/close[i-1])
    return dict(sym=sym, dates=dates, close=close, vol=vol, r=r, n=n)

def enrich(s, ann):
    """rolling MAD baseline, z_rob, RVOL, trailing annualized vol"""
    n=s["n"]; r=s["r"]; vol=s["vol"]
    z=[None]*n; rv=[None]*n; sig=[None]*n; avol=[None]*n
    for t in range(n):
        w = [r[i] for i in range(max(1,t-W), t) if r[i] is not None]
        if len(w) < 60 or r[t] is None:
            continue
        m  = med(w)
        mad= med([abs(x-m) for x in w])
        sr = 1.4826*mad
        if sr <= 0: continue
        z[t]   = (r[t]-m)/sr
        sig[t] = sr
        avol[t]= sr*math.sqrt(ann)                     # 用同一稳健口径年化
        vw = [vol[i] for i in range(max(0,t-W), t) if vol[i] and vol[i]>0]
        if len(vw) >= 60:
            mv = med(vw)
            if mv>0: rv[t] = vol[t]/mv
    s.update(z=z, rvol=rv, sigma=sig, avol=avol)
    return s

def beta_series(s, bench):
    """rolling 90d beta vs benchmark, aligned by date"""
    n=s["n"]; bi={d:i for i,d in enumerate(bench["dates"])}
    b=[None]*n
    for t in range(n):
        xs=[];ys=[]
        for i in range(max(1,t-W), t):
            j = bi.get(s["dates"][i])
            if j is None or j==0: continue
            if s["r"][i] is None or bench["r"][j] is None: continue
            xs.append(bench["r"][j]); ys.append(s["r"][i])
        if len(xs)<60: continue
        mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
        num=sum((xs[k]-mx)*(ys[k]-my) for k in range(len(xs)))
        den=sum((xs[k]-mx)**2 for k in range(len(xs)))
        if den>0: b[t]=num/den
    s["beta"]=b
    return s

def fwd_stats(s, bench, t):
    """post-event realized vol ratio (V) and beta-adjusted |excess| (A)"""
    n=s["n"]
    if t+FWD >= n: return None, None
    rr=[s["r"][t+k] for k in range(1,FWD+1)]
    if any(x is None for x in rr): return None,None
    pv = math.sqrt(sum(x*x for x in rr)/FWD)
    V  = pv/s["sigma"][t] if s["sigma"][t] else None
    A=None
    if bench is not None and s["beta"][t] is not None:
        bi={d:i for i,d in enumerate(bench["dates"])}
        cum=sum(rr); cm=0.0; ok=True
        for k in range(1,FWD+1):
            j=bi.get(s["dates"][t+k])
            if j is None or bench["r"][j] is None: ok=False;break
            cm+=bench["r"][j]
        if ok: A=abs(cum - s["beta"][t]*cm)
    return V,A

def tier(av):
    if av is None: return None
    if av < 0.25: return "低波 <25%"
    if av < 0.50: return "中波 25-50%"
    return "高波 >50%"

RULES = {}
for zt in ZS: RULES[f"A·价格 z≥{zt}"]      = ("A", zt, None)
for vt in VS: RULES[f"B·量能 RVOL≥{vt}"]   = ("B", None, vt)
for zt in ZS:
    for vt in VS: RULES[f"C·双确认 z≥{zt}+v≥{vt}"] = ("C", zt, vt)
RULES["R2·绝对值兜底 |r|>5%&|z|<1"] = ("R2", None, None)

def fires(s, t, kind, zt, vt):
    z=s["z"][t]; rv=s["rvol"][t]; r=s["r"][t]
    if kind=="A":  return z is not None and abs(z)>=zt
    if kind=="B":  return rv is not None and rv>=vt
    if kind=="C":  return z is not None and rv is not None and abs(z)>=zt and rv>=vt
    if kind=="R2": return (r is not None and z is not None and abs(r)>ABS_FLOOR and abs(z)<1.0)
    return False

def run():
    spy = enrich(series("SPY"), 252)
    btc_b = enrich(series("BTC"), 365)
    universe=[]
    for sym in STOCKS:
        s=enrich(series(sym),252); s=beta_series(s,spy); s["cls"]="股票"; universe.append(s)
    for sym in CRYPTO:
        s=enrich(series(sym),365)
        s=beta_series(s,btc_b) if sym!="BTC" else dict(s, beta=[None]*s["n"])
        s["cls"]="加密"; universe.append(s)

    per_ticker={}; tier_acc={}; overlap={}
    for s in universe:
        n=s["n"]; sym=s["sym"]
        years = sum(1 for t in range(n) if s["z"][t] is not None)/(252 if s["cls"]=="股票" else 365)
        bench = spy if s["cls"]=="股票" else (btc_b if sym!="BTC" else None)
        avs=[s["avol"][t] for t in range(n) if s["avol"][t] is not None]
        per_ticker[sym]=dict(cls=s["cls"], years=round(years,2),
                             avol=round(st.median(avs),3) if avs else None, F={})
        # overlap between price(z>=2) and volume(rvol>=2)
        pa=set(); pb=set()
        for t in range(n):
            if fires(s,t,"A",2.0,None): pa.add(t)
            if fires(s,t,"B",None,2.0): pb.add(t)
        overlap[sym]=dict(nA=len(pa), nB=len(pb), both=len(pa&pb),
                          jac=round(len(pa&pb)/max(1,len(pa|pb)),3))
        for name,(kind,zt,vt) in RULES.items():
            trig=[t for t in range(n) if fires(s,t,kind,zt,vt)]
            per_ticker[sym]["F"][name]=round(len(trig)/years,1) if years>0 else None
            for t in range(n):
                tr = tier(s["avol"][t])
                if tr is None: continue
                key=(s["cls"],tr,name)
                a=tier_acc.setdefault(key, dict(days=0,trig=0,V=[],A=[],P=0,bV=[],bA=[]))
                a["days"]+=1
                hit = t in set(trig) if False else fires(s,t,kind,zt,vt)
                V,A = fwd_stats(s,bench,t)
                if hit:
                    a["trig"]+=1
                    if V is not None: a["V"].append(V)
                    if A is not None: a["A"].append(A)
                    if t+1<n and fires(s,t+1,kind,zt,vt): a["P"]+=1
                else:
                    if V is not None: a["bV"].append(V)
                    if A is not None: a["bA"].append(A)
    return per_ticker, tier_acc, overlap

if __name__=="__main__":
    pt, ta, ov = run()
    out={"per_ticker":pt,
         "tier":{ "|".join(k): dict(days=v["days"], trig=v["trig"],
                    F=round(v["trig"]/(v["days"]/(252 if k[0]=="股票" else 365)),1) if v["days"] else None,
                    V=round(st.median(v["V"]),2) if v["V"] else None,
                    bV=round(st.median(v["bV"]),2) if v["bV"] else None,
                    A=round(st.median(v["A"])*100,2) if v["A"] else None,
                    bA=round(st.median(v["bA"])*100,2) if v["bA"] else None,
                    P=round(v["P"]/v["trig"],2) if v["trig"] else None)
                 for k,v in ta.items()},
         "overlap":ov}
    print(json.dumps(out, ensure_ascii=False))
