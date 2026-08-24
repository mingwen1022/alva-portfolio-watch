"""自检：用本引擎复现 plan.md §一 已审核的 PV1 逐标的数字（旧 11 只美股）。
目标：XOM 2.70 [1.53,4.87] · SOFI 1.15 [0.90,1.40] 未通过 · TSLA 1.21 · KO 1.30 擦边。
"""
import numpy as np, json
from pv_engine import load_legacy, indicators, pv1_trigger, ratio_ci

REF = {"XOM":2.70,"AAPL":1.97,"MSFT":1.86,"NVDA":1.68,"MSTR":1.48,"AMD":1.31,
       "KO":1.30,"PLTR":1.27,"RIVN":1.25,"TSLA":1.21,"SOFI":1.15}
REFN= {"XOM":47,"AAPL":61,"MSFT":66,"NVDA":65,"MSTR":148,"AMD":71,"KO":54,
       "PLTR":64,"RIVN":67,"TSLA":73,"SOFI":61}

rows=[]
print(f"{'标的':<6}{'触发':>5}{'参考':>5}{'块':>4}{'倍数':>7}{'参考':>7}{'差':>7}   {'95% 区间':<16}{'判定'}")
for s in REF:
    ds,c,v = load_legacy(s)
    ind = indicators(c,v,252)
    T = pv1_trigger(ind,1.5,2.0)
    r = ratio_ci(ind,T)
    d = r["mult"]-REF[s]
    print(f"{s:<6}{r['n']:>5}{REFN[s]:>5}{r['blocks']:>4}{r['mult']:>7.2f}{REF[s]:>7.2f}{d:>+7.2f}   "
          f"[{r['lo']:.2f}, {r['hi']:.2f}]{'':<3}{'🟢' if r['pass_'] else '❌'}")
    rows.append(dict(sym=s, ref=REF[s], refn=REFN[s], **r))
json.dump(rows, open("selfcheck.json","w"), indent=1, ensure_ascii=False)
