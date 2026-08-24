"""MA 族回测引擎。

判据（现行，唯一）：相对基准倍数的 95% 区间下界 > 1.0
  V_t   = sqrt(mean(r_{t+1..t+5}^2)) / sigma_rob,t
  倍数  = median(V | 触发日) / median(V | 非触发日)
  区间  = 整块自助（块 = 相邻触发间隔 < 5 交易日归一块），固定种子

硬规则：逐标的算，不池化。
"""
import math, statistics as st, random, os, csv, datetime
from macro_calendar import first_release

D_PX = "/Users/ming/project/alva/backtest/data/stocks-daily"
W, FWD = 90, 5
SEED, NBOOT = 20260819, 4000

STOCKS = ["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
CRYPTO = ["BTC","ETH","SOL","DOGE"]

def med(xs): return st.median(xs)

def load_px(sym):
    rows=[]
    for ln in open(f"{D_PX}/{sym}.csv"):
        d,c,v = ln.strip().split(",")
        rows.append((d,float(c),float(v)))
    rows.sort()
    return rows

def build(sym, ann):
    rows=load_px(sym)
    dates=[r[0] for r in rows]; close=[r[1] for r in rows]
    n=len(rows); r=[None]*n
    for i in range(1,n):
        if close[i-1]>0 and close[i]>0: r[i]=math.log(close[i]/close[i-1])
    sigma=[None]*n; avol=[None]*n
    for t in range(n):
        w=[r[i] for i in range(max(1,t-W),t) if r[i] is not None]
        if len(w)<60 or r[t] is None: continue
        m=med(w); mad=med([abs(x-m) for x in w]); sr=1.4826*mad
        if sr<=0: continue
        sigma[t]=sr; avol[t]=sr*math.sqrt(ann)
    V=[None]*n
    for t in range(n):
        if sigma[t] is None or t+FWD>=n: continue
        rr=[r[t+k] for k in range(1,FWD+1)]
        if any(x is None for x in rr): continue
        V[t]=math.sqrt(sum(x*x for x in rr)/FWD)/sigma[t]
    return dict(sym=sym, dates=dates, idx={d:i for i,d in enumerate(dates)},
                r=r, sigma=sigma, V=V, avol=avol, n=n)

def beta_of(s, bench):
    """滚动 90 日 OLS beta vs 基准，返回中位 beta（用于 M16 分组）"""
    bi=bench["idx"]; bs=[]
    for t in range(s["n"]):
        xs=[];ys=[]
        for i in range(max(1,t-W),t):
            j=bi.get(s["dates"][i])
            if j is None or j==0: continue
            if s["r"][i] is None or bench["r"][j] is None: continue
            xs.append(bench["r"][j]); ys.append(s["r"][i])
        if len(xs)<60: continue
        mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
        num=sum((a-mx)*(b-my) for a,b in zip(xs,ys)); den=sum((a-mx)**2 for a in xs)
        if den>0: bs.append(num/den)
    return med(bs) if bs else None

# ---------- 交易日对齐 ----------
def to_trading(s, rd, shift=0):
    """把发布日映射到该标的的交易日下标；shift=-1 取前一个交易日"""
    ds=s["dates"]
    lo,hi=0,len(ds)
    while lo<hi:
        mid=(lo+hi)//2
        if ds[mid]<rd: lo=mid+1
        else: hi=mid
    if lo>=len(ds): return None
    i=lo+shift
    if i<0 or i>=len(ds): return None
    return i

# ---------- 整块自助 ----------
def blocks_of(idxs, gap=FWD):
    idxs=sorted(idxs); bl=[]; cur=[]
    for i in idxs:
        if cur and i-cur[-1]>=gap: bl.append(cur); cur=[]
        cur.append(i)
    if cur: bl.append(cur)
    return bl

def ratio_ci(s, trig_idx, win_lo, win_hi):
    """win_lo/win_hi 限定样本区间（下标）。返回 dict"""
    Vv=s["V"]
    T=[i for i in trig_idx if win_lo<=i<=win_hi and Vv[i] is not None]
    Tset=set(i for i in trig_idx)
    N=[Vv[i] for i in range(win_lo,win_hi+1) if i not in Tset and Vv[i] is not None]
    if len(T)<3 or len(N)<30: return None
    base=med(N)
    if base<=0: return None
    pt=med([Vv[i] for i in T])/base
    bl=blocks_of(T)
    rng=random.Random(SEED)
    reps=[]
    for _ in range(NBOOT):
        samp=[]
        for _ in range(len(bl)):
            samp.extend(bl[rng.randrange(len(bl))])
        reps.append(med([Vv[i] for i in samp])/base)
    reps.sort()
    lo=reps[int(0.025*NBOOT)]; hi=reps[int(0.975*NBOOT)]
    return dict(n=len(T), blocks=len(bl), mult=pt, lo=lo, hi=hi,
                base=base, nbase=len(N))

def years_of(s, win_lo, win_hi, ann):
    return sum(1 for i in range(win_lo,win_hi+1) if s["V"][i] is not None)/ann
