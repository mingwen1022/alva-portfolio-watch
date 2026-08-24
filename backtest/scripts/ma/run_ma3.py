"""MA3 · FOMC 决议：确认端点缺口，并检验 FEDERAL_FUNDS 能否代理。"""
import collections, datetime, statistics as st
from macro_calendar import first_release
from ma_engine import *
from run_ma import universe, window, trig_from_dates, report, show

cal=first_release("FEDERAL_FUNDS")
dom=collections.Counter(int(rd[8:10]) for rd,_,_ in cal)
wd =collections.Counter(datetime.date.fromisoformat(rd).weekday() for rd,_,_ in cal)
print("FEDERAL_FUNDS 首发日 · 日历位置")
print("  发布日在当月第几天:", dict(sorted(dom.items())))
print("  星期分布(0=一):", dict(sorted(wd.items())))
print(f"  共 {len(cal)} 次 / {len(cal)/6.6:.1f} 次每年   （FOMC 每年 8 次，日期不规则）")

vals=[(rd,od,v) for rd,od,v in cal]
chg=[abs(vals[i][2]-vals[i-1][2]) for i in range(1,len(vals))]
moved=sum(1 for c in chg if c>0.05)
print(f"  月均有效利率相邻变动 >0.05pp 的月份: {moved}/{len(chg)}  "
      f"（利率决议 2020-2026 实际约 {8*6.6:.0f} 次会议，其中多数为不变）")
print(f"  变动幅度中位 {st.median(chg):.3f}pp · max {max(chg):.3f}pp")

U=universe()
LO,HI="2020-01-14","2026-08-12"
show(report(U,"参照 · FEDERAL_FUNDS 发布当日（月均有效利率，非决议日）",
            [rd for rd,_,_ in cal], 0, LO,HI))
