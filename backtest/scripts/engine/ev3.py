import json, math, statistics as st
from datetime import date
D=json.load(open("signals.json")); med=st.median
STOCKS=["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
WIN=30; HOR=[5,20,60,120]
spy={}
for ln in open("data/SPY.csv"):
    p=ln.strip().split(","); spy[p[0]]=float(p[1])
spyd=sorted(spy); spyi={t:i for i,t in enumerate(spyd)}
def ordn(s):
    y,m,d=map(int,s.split("-")); return date(y,m,d).toordinal()
def load(sym):
    out=[]
    for ln in open(f"ev/{sym}.csv"):
        p=ln.strip().split("|")
        if len(p)<6: continue
        out.append(dict(td=ordn(p[0]),fd=p[1],fdo=ordn(p[1]),code=p[2],plan=p[3]=="1",owner=p[5]))
    return out
def clusters(txs,K):
    txs=sorted(txs,key=lambda x:x["fdo"]); fired=[];used=-1;known=[]
    for cur in txs:
        known.append(cur)
        near=[x for x in known if abs(x["td"]-cur["td"])<WIN]
        best=None
        for a in near:
            if a["td"]>cur["td"]: continue
            win=[x for x in near if a["td"]<=x["td"]<a["td"]+WIN]
            if len(set(x["owner"] for x in win))>=K:
                e=max(x["td"] for x in win)
                if best is None or e>best: best=e
        if best is not None and best>used:
            fired.append(cur["fd"]); used=best
    return fired
def fwd_excess(sym, dstr, h):
    """从可知日之后首个交易日起，h 日 beta 调整超额收益（有符号）"""
    d=D[sym]; idx=None
    for i,t in enumerate(d["d"]):
        if t>=dstr: idx=i; break
    if idx is None or idx+h>=len(d["d"]): return None
    c0,c1=d["c"][idx],d["c"][idx+h]
    if not c0 or not c1: return None
    r=math.log(c1/c0)
    t0,t1=d["d"][idx],d["d"][idx+h]
    if t0 not in spyi or t1 not in spyi: return None
    m=math.log(spy[t1]/spy[t0])
    # 简化：用全样本 beta 近似（该标的对 SPY）
    return (r - BETA[sym]*m)*100
# 全样本 beta
BETA={}
for s in STOCKS:
    d=D[s]; xs=[];ys=[]
    for i in range(1,len(d["d"])):
        t,tp=d["d"][i],d["d"][i-1]
        if t in spyi and tp in spyi and d["c"][i] and d["c"][i-1]:
            xs.append(math.log(spy[t]/spy[tp])); ys.append(math.log(d["c"][i]/d["c"][i-1]))
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    num=sum((xs[k]-mx)*(ys[k]-my) for k in range(len(xs))); den=sum((x-mx)**2 for x in xs)
    BETA[s]=num/den if den else 1.0

def run(code,plan_f,K,label):
    print(f"\n### {label}\n")
    print(f"{'窗口':>6}{'触发数':>7}{'中位超额':>10}{'均值超额':>10}{'基准中位':>10}{'正收益占比':>11}{'基准正占比':>11}")
    fired={}
    for s in STOCKS:
        txs=[x for x in load(s) if x["code"]==code and (not plan_f or not x["plan"])]
        if len(txs)<3: continue
        fired[s]=clusters(txs,K)
    for h in HOR:
        hits=[];base=[]
        for s,fl in fired.items():
            for f in fl:
                v=fwd_excess(s,f,h)
                if v is not None: hits.append(v)
            d=D[s]
            for i in range(0,len(d["d"])-h,7):     # 每 7 日抽样作基准，减少重叠
                c0,c1=d["c"][i],d["c"][i+h]
                t0,t1=d["d"][i],d["d"][i+h]
                if c0 and c1 and t0 in spyi and t1 in spyi:
                    base.append((math.log(c1/c0)-BETA[s]*math.log(spy[t1]/spy[t0]))*100)
        if len(hits)<5: continue
        pos=sum(1 for x in hits if x>0)/len(hits); bpos=sum(1 for x in base if x>0)/len(base)
        print(f"{h:5d}日{len(hits):7d}{med(hits):9.2f}%{sum(hits)/len(hits):9.2f}%{med(base):9.2f}%{pos*100:10.1f}%{bpos*100:10.1f}%")

print("# EV 族 · 多窗口有方向超额收益（beta 调整 vs SPY）")
print("\n研究声称：内部人簇买预示 6–12 个月 4–8% 超额。5 日窗口可能是口径错配，故加测 20/60/120 日。")
print("与 PV 族不同：EV 簇买有方向性，故测**有符号**超额，不是绝对值。")
run("P",False,2,"EV1 内部人簇买 K=2")
run("S",True,2,"EV2 内部人簇卖 K=2（剔 10b5-1）")
run("S",True,3,"EV2 内部人簇卖 K=3（剔 10b5-1）")
