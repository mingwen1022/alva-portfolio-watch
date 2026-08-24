"""M23 分布可用性：ρ = P(|z_rob| ≥ 1.5)。registry 的界是 ρ<2% 停用 / ρ>40% 降级。
除全样本与近 2 年外，再扫每只标的所有 504 日滚动窗的最小 / 最大 ρ ——
守卫在历史上任何时点是否触发过。"""
import numpy as np, statistics as st, json
from universe_load import roster, prep
rows=[]
for r in roster():
    ind=prep(r); z=ind["z"]; z=z[~np.isnan(z)]
    hit=(np.abs(z)>=1.5).astype(float)
    rec=dict(sym=ind["sym"],asset=ind["asset"],vt=ind["vol_tier"],n=len(z),
             rho=float(hit.mean()),rho2y=float(hit[-min(len(hit),504):].mean()))
    if len(hit)>=504:
        c=np.cumsum(np.insert(hit,0,0)); roll=(c[504:]-c[:-504])/504
        rec.update(roll_min=float(roll.min()),roll_max=float(roll.max()))
    rows.append(rec)
json.dump(rows,open("m23.json","w"),indent=1,ensure_ascii=False)
al=[x["rho"] for x in rows]
print(f"全样本 ρ（{len(rows)} 只）：中位 {st.median(al):.3f}  范围 [{min(al):.3f}, {max(al):.3f}]")
rr=[x for x in rows if "roll_min" in x]
mn=[x["roll_min"] for x in rr]; mx=[x["roll_max"] for x in rr]
print(f"504 日滚动窗（{len(rr)} 只有足够长度）：窗内最小 ρ 的下确界 {min(mn):.3f}（{min(rr,key=lambda x:x['roll_min'])['sym']}）"
      f"  窗内最大 ρ 的上确界 {max(mx):.3f}（{max(rr,key=lambda x:x['roll_max'])['sym']}）")
print(f"任何时点 ρ < 2% 的标的：{sum(1 for x in rr if x['roll_min']<0.02)}   ρ > 40% 的标的：{sum(1 for x in rr if x['roll_max']>0.40)}")
print(f"正态理论值 13.36%；实测低于理论的标的 {sum(1 for x in al if x<0.1336)}/{len(al)}")
print("ρ 最低六只（全样本）：" + " · ".join(f"{x['sym']} {x['rho']:.3f}" for x in sorted(rows,key=lambda x:x['rho'])[:6]))
print("ρ 最高六只（全样本）：" + " · ".join(f"{x['sym']} {x['rho']:.3f}" for x in sorted(rows,key=lambda x:-x['rho'])[:6]))
