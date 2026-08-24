"""网格分析：决策 #2（θz 不分档）与决策 #3（θv 只按资产类别）在 92+25 上是否仍成立。
读法按扩池后新规：看通过比例，不看某只是否通过。触发频率只报不判（决策 #9）。"""
import json, numpy as np, statistics as st
G=json.load(open("grid.json"))
ZS=[1.0,1.25,1.5,1.75,2.0,2.5]; VS=[1.0,1.5,2.0,2.5,3.0,3.5]
LONG=[x for x in G if x["years"]>=5]      # 短历史标的会把网格弄成噪声，主表用 ≥5 年

def cell(rows,z,v,field="passed"):
    k=f"{z}|{v}"; g=[x["g"][k] for x in rows if k in x["g"]]
    if not g: return None
    if field=="passed": return sum(1 for e in g if e["passed"])/len(g), len(g)
    return st.median(e[field] for e in g), len(g)

def table(title,rows,field="passed",fmt="{:.0%}"):
    print(f"\n{title}（n={len(rows)}）")
    print(f"{'θz \\ θv':<9}"+"".join(f"{v:>9}" for v in VS))
    for z in ZS:
        line=f"{z:<9}"
        for v in VS:
            c=cell(rows,z,v,field)
            line+=f"{(fmt.format(c[0]) if c else '—'):>9}"
        print(line)

US=[x for x in LONG if x["asset"]=="us_equity"]; CR=[x for x in LONG if x["asset"]=="crypto"]
table("### 通过比例 · 美股 ≥5 年",US)
table("### 通过比例 · 加密 ≥5 年",CR)
table("### 倍数中位 · 美股 ≥5 年",US,"mult","{:.2f}")
table("### 倍数中位 · 加密 ≥5 年",CR,"mult","{:.2f}")
table("### 触发频率中位 次/年 · 美股 ≥5 年（描述量，不作判据）",US,"freq","{:.0f}")
table("### 触发频率中位 次/年 · 加密 ≥5 年",CR,"freq","{:.0f}")

print("\n### 美股按波动档分：θz 是否该分档（θv 固定 2.0）")
print(f"{'波动档':<14}"+"".join(f"{'θz='+str(z):>12}" for z in ZS))
for lab in ["低波 <25%","中波 25-50%","高波 >50%"]:
    rows=[x for x in US if x["vol_tier"]==lab]; line=f"{lab:<14}"
    for z in ZS:
        c=cell(rows,z,2.0); m=cell(rows,z,2.0,"mult")
        line+=f"{(f'{c[0]:.0%}/{m[0]:.2f}' if c else '—'):>12}"
    print(line+f"   n={len(rows)}")
print("<sub>每格 = 通过比例 / 倍数中位</sub>")

print("\n### 美股按波动档分：θv 是否该分档（θz 固定 1.5）")
print(f"{'波动档':<14}"+"".join(f"{'θv='+str(v):>12}" for v in VS))
for lab in ["低波 <25%","中波 25-50%","高波 >50%"]:
    rows=[x for x in US if x["vol_tier"]==lab]; line=f"{lab:<14}"
    for v in VS:
        c=cell(rows,1.5,v); m=cell(rows,1.5,v,"mult")
        line+=f"{(f'{c[0]:.0%}/{m[0]:.2f}' if c else '—'):>12}"
    print(line+f"   n={len(rows)}")

print("\n### 美股按市值档分：θv（θz 固定 1.5）")
for lab in ["大盘","中盘","小盘"]:
    rows=[x for x in US if x["size_tier"]==lab]; line=f"{lab:<14}"
    for v in VS:
        c=cell(rows,1.5,v); m=cell(rows,1.5,v,"mult")
        line+=f"{(f'{c[0]:.0%}/{m[0]:.2f}' if c else '—'):>12}"
    print(line+f"   n={len(rows)}")

print("\n### 部门（θz1.5 · θv2.0 与 θv3.0 对照）")
print(f"{'部门':<10}{'n':>4}{'θv=2.0 通过/倍数':>20}{'θv=3.0 通过/倍数':>20}")
for s in sorted({x["sector"] for x in US}):
    rows=[x for x in US if x["sector"]==s]
    a=cell(rows,1.5,2.0); am=cell(rows,1.5,2.0,"mult")
    b=cell(rows,1.5,3.0); bm=cell(rows,1.5,3.0,"mult")
    print(f"{s:<10}{len(rows):>4}{(f'{a[0]:.0%} / {am[0]:.2f}' if a else '—'):>20}{(f'{b[0]:.0%} / {bm[0]:.2f}' if b else '—'):>20}")
