"""决策 #2 的原始依据在新池上的复算：
「实测波动差 4.7 倍、触发频率只差 1.5 倍；MAD 已消掉波动差异」
只看价格腿 |z_rob| ≥ θz，不带量能腿。"""
import numpy as np, statistics as st, json
from universe_load import roster, prep
rows=[]
for r in roster():
    ind=prep(r)
    z=ind["z"][~np.isnan(ind["z"])]
    rows.append(dict(sym=ind["sym"],asset=ind["asset"],vt=ind["vol_tier"],st_=ind["size_tier"],
                     sec=ind["sector"],sig=ind["sigma_ann"],years=ind["years"],
                     f15=float(np.mean(np.abs(z)>=1.5))*ind["ann"], f20=float(np.mean(np.abs(z)>=2.0))*ind["ann"],
                     rho=float(np.mean(np.abs(z)>=1.5))))
json.dump(rows,open("dec2.json","w"),indent=1,ensure_ascii=False)
for lab,sel in [("全部 116",lambda x:True),("美股 92",lambda x:x["asset"]=="us_equity"),
                ("美股 ≥5 年",lambda x:x["asset"]=="us_equity" and x["years"]>=5)]:
    g=[x for x in rows if sel(x)]
    sg=[x["sig"] for x in g]; f=[x["f15"] for x in g]
    print(f"{lab:<12} σ_ann 中位 {st.median(sg):.2f}  范围 [{min(sg):.2f}, {max(sg):.2f}]  极差 {max(sg)/min(sg):.1f}×"
          f"   |z|≥1.5 次/年 中位 {st.median(f):.0f} 范围 [{min(f):.0f}, {max(f):.0f}] 极差 {max(f)/min(f):.1f}×")
print("\n### 价格腿触发频率（次/年）按波动档 —— MAD 是否消掉了波动差异")
print(f"{'波动档':<14}{'标的':>5}{'σ_ann 中位':>11}{'|z|≥1.5 次/年':>15}{'|z|≥2.0 次/年':>15}")
for v in ["低波 <25%","中波 25-50%","高波 >50%"]:
    g=[x for x in rows if x["vt"]==v and x["asset"]=="us_equity"]
    if g: print(f"{v:<14}{len(g):>5}{st.median(x['sig'] for x in g):>11.2f}"
                f"{st.median(x['f15'] for x in g):>15.0f}{st.median(x['f20'] for x in g):>15.0f}")
g=[x for x in rows if x["asset"]=="crypto"]
print(f"{'加密':<14}{len(g):>5}{st.median(x['sig'] for x in g):>11.2f}"
      f"{st.median(x['f15'] for x in g):>15.0f}{st.median(x['f20'] for x in g):>15.0f}")
from scipy import stats as sp
us=[x for x in rows if x["asset"]=="us_equity"]
print(f"\nσ_ann 与 |z|≥1.5 频率 的 Spearman（美股 92）：{sp.spearmanr([x['sig'] for x in us],[x['f15'] for x in us])}")
