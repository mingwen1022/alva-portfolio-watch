"""M16 的补充检验：把 beta>1.2 换成中位数二分，去掉 13 vs 2 的分组退化。"""
import statistics as st, random
from ma_engine import *
from macro_calendar import first_release
from run_ma import universe, window, trig_from_dates

LO,HI="2020-01-14","2026-08-12"

def mults(U, rds, shift):
    per={}
    for sym,s in U.items():
        if sym=="SPY": continue
        lo,hi=window(s,LO,HI)
        T=[i for i in trig_from_dates(s,rds,shift) if lo<=i<=hi]
        Tset=set(T)
        N=[s["V"][i] for i in range(lo,hi+1) if i not in Tset and s["V"][i] is not None]
        vs=[s["V"][i] for i in T if s["V"][i] is not None]
        if len(vs)<8 or len(N)<30: continue
        per[sym]=st.median(vs)/st.median(N)
    return per

U=universe()
for name, rds, shift in [("CPI 当日",[r[0] for r in first_release("CPI")],0),
                         ("CPI T-1",[r[0] for r in first_release("CPI")],-1),
                         ("NFP 当日",[r[0] for r in first_release("TOTAL_NONFARM_PAYROLL")],0)]:
    per=mults(U,rds,shift)
    stk=[(U[k]["beta"],k,per[k]) for k in per if U[k]["cls"]=="股票"]
    stk.sort()
    half=len(stk)//2
    lowb=stk[:half]; highb=stk[-half:]
    ml=st.mean([x[2] for x in lowb]); mh=st.mean([x[2] for x in highb])
    allm=[x[2] for x in stk]; rng=random.Random(20260819); obs=mh-ml; c=0
    for _ in range(20000):
        rng.shuffle(allm)
        if abs(st.mean(allm[:half])-st.mean(allm[half:half*2]))>=abs(obs): c+=1
    print(f"{name}: 低β组({','.join(x[1] for x in lowb)}) {ml:.3f}  "
          f"高β组({','.join(x[1] for x in highb)}) {mh:.3f}  差 {mh-ml:+.3f} ({(mh/ml-1)*100:+.1f}%)  置换 p={c/20000:.3f}")
    cry=[per[k] for k in per if U[k]["cls"]=="加密"]
    print(f"        加密组均值 {st.mean(cry):.3f}（M16 判高敏感） vs 全股票均值 {st.mean(allm):.3f}")
