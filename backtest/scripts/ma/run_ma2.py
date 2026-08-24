import statistics as st
from ma_engine import *
from macro_calendar import first_release
from m15 import series as m15_series
from run_ma import universe, window, trig_from_dates, report, show, ANN

LO,HI="2020-01-14","2026-08-12"

def ma2_dates(ind, mode, th=1.5):
    return [rd for rd,od,a,z in m15_series(ind,mode) if z is not None and abs(z)>=th]

if __name__=="__main__":
    U=universe()
    for ind in ["CPI","TOTAL_NONFARM_PAYROLL"]:
        for mode in ["literal","delta"]:
            ds=ma2_dates(ind,mode)
            show(report(U, f"MA2 · {ind} · M15 口径={mode} · |z|>=1.5 · {len(ds)} 个发布日", ds, 0, LO,HI))
    # 极端档：只看 |z| 最大的那批（delta 口径）
    for ind in ["CPI","TOTAL_NONFARM_PAYROLL"]:
        for th in [2.0, 2.5]:
            ds=ma2_dates(ind,"delta",th)
            if len(ds)<6: print(f"\n### MA2 {ind} delta |z|>={th}: 仅 {len(ds)} 个发布日，样本不足"); continue
            show(report(U, f"MA2 · {ind} · delta · |z|>={th} · {len(ds)} 个发布日", ds, 0, LO,HI))
