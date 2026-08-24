"""补充描述量（非判据）：发布当日自身的波动，检验「前瞻窗口 V 起点在 t+1、
可能漏掉宏观的当日脉冲」这一替代解释。"""
import math, statistics as st, random
from ma_engine import *
from macro_calendar import first_release
from run_ma import universe, window, trig_from_dates

U=universe()
LO,HI="2020-01-14","2026-08-12"
def zrob(s):
    n=s["n"]; r=s["r"]; z=[None]*n
    for t in range(n):
        w=[r[i] for i in range(max(1,t-W),t) if r[i] is not None]
        if len(w)<60 or r[t] is None: continue
        m=med(w); mad=med([abs(x-m) for x in w]); sr=1.4826*mad
        if sr>0: z[t]=(r[t]-m)/sr
    return z

for lab, rds in [("CPI",[r[0] for r in first_release("CPI")]),
                 ("NFP",[r[0] for r in first_release("TOTAL_NONFARM_PAYROLL")]),
                 ("GDP",[r[0] for r in first_release("GDP")])]:
    out=[]
    for sym,s in U.items():
        z=zrob(s); lo,hi=window(s,LO,HI)
        T=set(i for i in trig_from_dates(s,rds,0) if lo<=i<=hi)
        a=[abs(z[i]) for i in T if z[i] is not None]
        b=[abs(z[i]) for i in range(lo,hi+1) if i not in T and z[i] is not None]
        if len(a)<8: continue
        rng=random.Random(20260819); reps=[]
        base=st.median(b)
        for _ in range(4000):
            samp=[a[rng.randrange(len(a))] for _ in a]
            reps.append(st.median(samp)/base)
        reps.sort()
        out.append((sym, st.median(a)/base, reps[100], reps[3900]))
    print(f"\n{lab} 发布当日 |z_rob| 相对非发布日的倍数（描述量，不是判据）")
    for sym,m,l,h in sorted(out,key=lambda x:-x[1]):
        print(f"  {sym:6s} {m:5.2f} [{l:.2f}, {h:.2f}]{'  ↑' if l>1.0 else ''}")
