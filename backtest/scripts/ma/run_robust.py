import statistics as st
from ma_engine import *
from macro_calendar import first_release
from run_ma import universe, window, trig_from_dates, ANN

U=universe()
cpi=[r[0] for r in first_release("CPI")]
nfp=[r[0] for r in first_release("TOTAL_NONFARM_PAYROLL")]
syms=["AAPL","MSFT","NVDA","TSLA","AMD","KO","XOM","MSTR","SPY","BTC","ETH","DOGE"]

def prof(rds, lo_d, hi_d, label):
    print(f"\n{label}  (窗口 {lo_d} → {hi_d})")
    print("shift " + "".join(f"{s:>7s}" for s in syms))
    for shift in range(-3,4):
        line=f"{shift:+5d} "
        for sym in syms:
            s=U[sym]; lo,hi=window(s,lo_d,hi_d)
            T=[i for i in trig_from_dates(s,rds,shift) if lo<=i<=hi]
            r=ratio_ci(s,T,lo,hi)
            line += f"{r['mult']:7.2f}" if r else "      -"
        print(line)

prof(cpi,"2020-01-14","2026-08-12","CPI 发布日邻域剖面（shift 0 = 发布当日 · +1 = observed_at 对应日）")
prof(cpi,"2020-07-01","2026-08-12","CPI 剖面 · 剔除 2020 上半年疫情段")
prof(nfp,"2020-01-14","2026-08-12","NFP 发布日邻域剖面")

# 功效：CPI 当日各标的 95% 区间上界 —— 能排除多大的效应
print("\n功效参考 · CPI 发布当日 95% 区间上界（高于该值的效应本样本可以排除）")
ups=[]
for sym in U:
    s=U[sym]; lo,hi=window(s,"2020-01-14","2026-08-12")
    T=[i for i in trig_from_dates(s,cpi,0) if lo<=i<=hi]
    r=ratio_ci(s,T,lo,hi)
    if r: ups.append((sym,r["hi"])); 
ups.sort(key=lambda x:x[1])
print("  " + " ".join(f"{k}{v:.2f}" for k,v in ups))
print(f"  上界中位 {st.median([v for _,v in ups]):.2f} · 最宽 {max(v for _,v in ups):.2f}")
