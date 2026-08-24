"""PLTR 在 EV3 下单独通过 —— 核实是不是靠少数几次触发 / 时段 / 随机种子撑着"""
import random, statistics as st
from datetime import date, timedelta
from ev35_rerun import build, align, blocks, evaluate, analyst_triggers, SYMS, B, SEED, COOL

S="PLTR"
V,ds=build(S)
raw,nrow,nev=analyst_triggers(S,3,True,True)
trig=align(raw,ds)
tv=[d for d in trig if d in V]
N=[v for d,v in V.items() if d not in set(trig)]
base=st.median(N)
print(f"原始行 {nrow} · 有方向的修订事件 {nev} · 冷却前触发 {len(raw)} · 对齐后 {len(trig)} · 落在 V 上 {len(tv)}")
print(f"非触发日基准中位 V = {base:.3f}   (n={len(N)})")
print(f"\n{'触发日':<13}{'V':>7}{'V/基准':>9}   位置")
srt=sorted(V.values())
for d in tv:
    pct=sum(1 for x in srt if x<=V[d])/len(srt)
    print(f"{str(d):<13}{V[d]:>7.2f}{V[d]/base:>9.2f}   P{pct*100:.0f}")
print(f"\n触发日 V 中位 {st.median([V[d] for d in tv]):.3f} → 倍数 {st.median([V[d] for d in tv])/base:.2f}")

def boot(tvv,seed,b=B):
    bs=blocks(tvv); random.seed(seed); rs=[]
    for _ in range(b):
        fl=[V[x] for _ in range(len(bs)) for x in random.choice(bs)]
        rs.append(st.median(fl)/base)
    rs.sort(); return rs[int(.025*b)],rs[b//2],rs[int(.975*b)]

print("\n── 留一法（去掉某一次触发后重算） ──")
for d in tv:
    lo,m,hi=boot([x for x in tv if x!=d],SEED)
    print(f"  去掉 {d}   倍数 {m:.2f}  区间 [{lo:.2f}, {hi:.2f}]  {'仍通过' if lo>1 else '❌ 翻转为未通过'}")

print("\n── 随机种子敏感性（同一批触发，换 12 个种子） ──")
res=[boot(tv,sd) for sd in range(1,13)]
print("  下界 " + " ".join(f"{r[0]:.2f}" for r in res))
print(f"  下界>1.0 的比例 {sum(1 for r in res if r[0]>1)}/12")

print("\n── 触发日按年分布 ──")
from collections import Counter
c=Counter(d.year for d in tv); print("  "+"  ".join(f"{y}:{n}" for y,n in sorted(c.items())))
# 同期 PLTR 整体 V 水平
for y in sorted(c):
    ys=[v for d,v in V.items() if d.year==y]
    print(f"  {y} 全年非触发日 V 中位 {st.median([v for d,v in V.items() if d.year==y and d not in set(trig)]):.2f}  (全样本基准 {base:.2f})")

print("\n── 安慰剂：把触发日整体平移 ──")
di={d:i for i,d in enumerate(ds)}
for sh in [-40,-20,-10,-5,5,10,20,40]:
    sh_tv=[]
    for d in tv:
        i=di.get(d)
        if i is None: continue
        j=i+sh
        if 0<=j<len(ds) and ds[j] in V: sh_tv.append(ds[j])
    if len(sh_tv)<3: continue
    m=st.median([V[x] for x in sh_tv])/base
    lo,_,hi=boot(sh_tv,SEED)
    print(f"  平移 {sh:>+4} 交易日   倍数 {m:.2f}  区间 [{lo:.2f}, {hi:.2f}]  {'⚠️ 也通过' if lo>1 else ''}")

print("\n── 与年份配平的基准（只用触发所在年份的非触发日作基准） ──")
yrs={d.year for d in tv}
Ny=[v for d,v in V.items() if d.year in yrs and d not in set(trig)]
by=st.median(Ny)
bs=blocks(tv); random.seed(SEED); rs=[]
for _ in range(B):
    fl=[V[x] for _ in range(len(bs)) for x in random.choice(bs)]
    rs.append(st.median(fl)/by)
rs.sort()
print(f"  年份配平基准 {by:.3f} (n={len(Ny)})   倍数 {rs[B//2]:.2f}  区间 [{rs[int(.025*B)]:.2f}, {rs[int(.975*B)]:.2f}]")

print("\n── 定义敏感性 ──")
for lbl,kw in [("不做串标的守卫",dict(guard=False)),("不分方向 ≥3",dict(directional=False)),
               ("K=4 同向",dict(K=4)),("K=2 同向",dict(K=2))]:
    r2,_,_=analyst_triggers(S,**{**dict(K=3,directional=True,guard=True),**kw})
    t2=align(r2,ds); e=evaluate(t2,V)
    if not e: print(f"  {lbl:<16} 样本不足 (n={len(t2)})"); continue
    print(f"  {lbl:<16} 触发 {e['n']:>3}  倍数 {e['r']:.2f}  区间 [{e['lo']:.2f}, {e['hi']:.2f}]  {'通过' if e['lo']>1 else '未通过'}")
