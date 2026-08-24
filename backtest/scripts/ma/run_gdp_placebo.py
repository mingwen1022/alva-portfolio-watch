"""GDP 发布日附近的倍数剖面。
GDP 预估值固定在 1/4/7/10 月末发布 —— 与美股财报季高度重合。
若「GDP 效应」实为财报季日历效应，则把发布日整体平移若干交易日后效应仍在，
且只出现在有财报的股票、不出现在加密标的。
"""
import statistics as st
from ma_engine import *
from macro_calendar import first_release
from run_ma import universe, window, trig_from_dates

LO,HI="2020-01-14","2026-08-12"
U=universe()
gdp=[r[0] for r in first_release("GDP")]
syms=["AAPL","MSFT","AMD","XOM","SOFI","KO","NVDA","SPY","BTC","ETH"]
print("发布日相对平移（交易日）下的相对基准倍数（点估计）")
print("shift " + "".join(f"{s:>7s}" for s in syms))
for shift in range(-20,21,4):
    line=f"{shift:+5d} "
    for sym in syms:
        s=U[sym]; lo,hi=window(s,LO,HI)
        T=[i for i in trig_from_dates(s,gdp,shift) if lo<=i<=hi]
        r=ratio_ci(s,T,lo,hi)
        line += f"{r['mult']:7.2f}" if r else "      -"
    print(line)
print()
print("窄网格 shift -6..+6")
print("shift " + "".join(f"{s:>7s}" for s in syms))
for shift in range(-6,7):
    line=f"{shift:+5d} "
    for sym in syms:
        s=U[sym]; lo,hi=window(s,LO,HI)
        T=[i for i in trig_from_dates(s,gdp,shift) if lo<=i<=hi]
        r=ratio_ci(s,T,lo,hi)
        line += f"{r['mult']:7.2f}" if r else "      -"
    print(line)
