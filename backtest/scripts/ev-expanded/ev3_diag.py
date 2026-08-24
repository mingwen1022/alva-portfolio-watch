"""EV3 诊断：覆盖窗口 · 同向要件是否 binding · 触发日是不是财报日"""
import sys, os, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import *

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
ev = [x for x in R["EV3"]["rows"] if x["bucket"] in ("通过", "未通过", "反向")]

print("### 分析师数据覆盖\n")
spans = []
for x in ev:
    rows = load_analyst(x["sym"])
    if rows:
        spans.append((x["sym"], rows[0][0], rows[-1][0], len(rows), len(set(r[1] for r in rows))))
print(f"最早发布日 中位 {st.median([s[1].toordinal() for s in spans]) and min(s[1] for s in spans)} → "
      f"{max(s[2] for s in spans)}；每只条目数 中位 {st.median([s[3] for s in spans]):.0f} "
      f"（{min(s[3] for s in spans)}–{max(s[3] for s in spans)}）· 机构数中位 "
      f"{st.median([s[4] for s in spans]):.0f}")
print(f"最早发布日晚于 2021-06 的标的 {sum(1 for s in spans if s[1].year*100+s[1].month>202106)}/{len(spans)}")

print("\n### 同向要件是否 binding（K=3 同向 vs 不分方向）\n")
same = diff = 0
tot_d = tot_n = 0
for x in ev:
    rows = load_analyst(x["sym"])
    a, _, _ = analyst_triggers(rows, 3, True)
    b, _, _ = analyst_triggers(rows, 3, False)
    tot_d += len(a); tot_n += len(b)
    if set(a) == set(b):
        same += 1
    else:
        diff += 1
print(f"{same}/{len(ev)} 只标的两种口径给出逐位相同的触发集；触发合计 同向 {tot_d} vs 不分方向 {tot_n}")

print("\n### 触发日本身是不是大波动日（财报解释的代理）\n")
print(f"{'标的':<7}{'触发':>5}{'触发日|z|中位':>13}{'基线|z|中位':>12}{'倍':>6}{'间隔 80–100 日占比':>18}{'倍数':>7}")
q_all = []
for x in sorted(ev, key=lambda x: -x["r"])[:12]:
    S = build(x["sym"])
    ti = align(analyst_triggers(load_analyst(x["sym"]))[0], S["ds"])
    az = [abs(S["z"][i]) for i in ti if S["z"][i] is not None]
    base = [abs(v) for v in S["z"] if v is not None]
    days = sorted(analyst_triggers(load_analyst(x["sym"]))[0])
    gaps = [(days[i + 1] - days[i]).days for i in range(len(days) - 1)]
    q = sum(1 for g in gaps if 80 <= g <= 100) / len(gaps) if gaps else 0
    print(f"{x['sym']:<7}{x['n']:>5}{st.median(az):>13.2f}{st.median(base):>12.2f}"
          f"{st.median(az)/st.median(base):>6.2f}{q*100:>17.0f}%{x['r']:>7.2f}")
for x in ev:
    days = sorted(analyst_triggers(load_analyst(x["sym"]))[0])
    gaps = [(days[i + 1] - days[i]).days for i in range(len(days) - 1)]
    if gaps:
        q_all.append(sum(1 for g in gaps if 80 <= g <= 100) / len(gaps))
print(f"\n全部 {len(q_all)} 只：间隔落在 80–100 日的比例 中位 {st.median(q_all)*100:.0f}%，"
      f"≥50% 的标的 {sum(1 for v in q_all if v>=0.5)} 只")
