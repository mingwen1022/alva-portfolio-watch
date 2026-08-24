import json, statistics as st
from ma_engine import *
from macro_calendar import first_release
from m15 import series as m15_series

ANN={"股票":252,"加密":365}

def universe():
    spy=build("SPY",252)
    U={}
    for s_ in STOCKS:
        s=build(s_,252); s["cls"]="股票"; s["beta"]=beta_of(s,spy); U[s_]=s
    for s_ in CRYPTO:
        s=build(s_,365); s["cls"]="加密"; s["beta"]=None; U[s_]=s
    U["SPY"]=dict(build("SPY",252), cls="股票", beta=1.0)
    return U

def window(s, lo_date, hi_date):
    ds=s["dates"]
    lo=next((i for i,d in enumerate(ds) if d>=lo_date), None)
    hi=None
    for i in range(len(ds)-1,-1,-1):
        if ds[i]<=hi_date: hi=i; break
    # 需要 V 有定义
    while lo is not None and lo<len(ds) and s["V"][lo] is None: lo+=1
    while hi is not None and hi>0 and s["V"][hi] is None: hi-=1
    return lo,hi

def trig_from_dates(s, rds, shift):
    out=[]
    for rd in rds:
        i=to_trading(s, rd, shift)
        if i is not None: out.append(i)
    return sorted(set(out))

def report(U, name, rds, shift, lo_date, hi_date):
    rows=[]
    for sym,s in U.items():
        lo,hi=window(s, lo_date, hi_date)
        if lo is None or hi is None or hi-lo<200: continue
        T=[i for i in trig_from_dates(s,rds,shift) if lo<=i<=hi]
        r=ratio_ci(s,T,lo,hi)
        if r is None:
            rows.append((sym,s["cls"],s["beta"],len(T),None,None,None,None)); continue
        yrs=years_of(s,lo,hi,ANN[s["cls"]])
        rows.append((sym,s["cls"],s["beta"],r["n"],r["blocks"],r["mult"],(r["lo"],r["hi"]), r["n"]/yrs))
    return dict(name=name, rows=rows)

def show(rep):
    print(f"\n### {rep['name']}")
    print(f"{'标的':6s} {'类':4s} {'β':>6s} {'触发':>5s} {'块':>4s} {'倍数':>7s} {'95%区间':>18s} {'次/年':>6s}  判")
    for sym,cls,b,n,bl,m,ci,f in rep["rows"]:
        if m is None: print(f"{sym:6s} {cls:4s} {'-' if b is None else f'{b:6.2f}'} {n:5d}   样本不足"); continue
        ok="PASS" if ci[0]>1.0 else "fail"
        print(f"{sym:6s} {cls:4s} {'-' if b is None else f'{b:6.2f}'} {n:5d} {bl:4d} {m:7.2f} [{ci[0]:6.2f},{ci[1]:6.2f}] {f:6.1f}  {ok}")

if __name__=="__main__":
    U=universe()
    print("β 中位:", {k:(round(v['beta'],2) if v['beta'] is not None else None) for k,v in U.items()})
    cpi=[rd for rd,_,_ in first_release("CPI")]
    nfp=[rd for rd,_,_ in first_release("TOTAL_NONFARM_PAYROLL")]
    gdp=[rd for rd,_,_ in first_release("GDP")]
    LO,HI="2020-01-14","2026-08-12"
    print(f"\n窗口 {LO} → {HI}  ·  CPI {len(cpi)} 次 · NFP {len(nfp)} 次 · GDP {len(gdp)} 次")

    show(report(U,"参照 · CPI 发布当日（无 M15 过滤，无 M16 过滤）", cpi, 0, LO,HI))
    show(report(U,"MA1 · CPI 发布前 1 交易日", cpi, -1, LO,HI))
    show(report(U,"参照 · NFP 发布当日", nfp, 0, LO,HI))
    show(report(U,"MA1 · NFP 发布前 1 交易日", nfp, -1, LO,HI))
    show(report(U,"参照 · GDP 发布当日", gdp, 0, LO,HI))
    show(report(U,"MA1 · GDP 发布前 1 交易日", gdp, -1, LO,HI))
