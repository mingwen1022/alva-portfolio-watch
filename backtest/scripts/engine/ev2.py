import json, statistics as st
from datetime import date
D=json.load(open("signals.json")); med=st.median
STOCKS=["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
FWD=5; WIN=30
def ordn(s):
    y,m,d=map(int,s.split("-")); return date(y,m,d).toordinal()
def load(sym):
    out=[]
    for ln in open(f"ev/{sym}.csv"):
        p=ln.strip().split("|")
        if len(p)<6: continue
        out.append(dict(td=ordn(p[0]), fd=p[1], fdo=ordn(p[1]), code=p[2],
                        plan=p[3]=="1", officer=p[4]=="1", owner=p[5]))
    return out
def clusters(txs,K):
    """新簇只可能在新申报到达时形成，且必须包含该笔 → 只检查含它的窗口"""
    txs=sorted(txs,key=lambda x:x["fdo"])
    fired=[]; used_until=-1
    known=[]
    for cur in txs:
        known.append(cur)
        near=[x for x in known if abs(x["td"]-cur["td"])<WIN]
        best=None
        for a in near:
            if a["td"]>cur["td"]: continue
            win=[x for x in near if a["td"]<=x["td"]<a["td"]+WIN]
            if len(set(x["owner"] for x in win))>=K:
                end=max(x["td"] for x in win)
                if best is None or end>best[0]: best=(end,len(set(x["owner"] for x in win)))
        if best and best[0]>used_until:
            fired.append(dict(knownAt=cur["fd"], td_end=best[0],
                              lag=cur["fdo"]-best[0], n_owner=best[1]))
            used_until=best[0]
    return fired
def fwd(sym,dstr):
    d=D[sym]
    for i,t in enumerate(d["d"]):
        if t>=dstr:
            if i+FWD>=len(d["d"]) or d["fv"][i] is None: return None
            return dict(V=d["fv"][i], fr=d["fr"][i], date=d["d"][i])
    return None
def run(code,plan_f,K,label):
    print(f"\n### {label}  (code={code} · K={K}" + (" · 剔 10b5-1" if plan_f else "") + ")\n")
    print(f"{'标的':6}{'笔数':>6}{'簇次':>6}{'次/年':>7}{'滞后中位':>9}{'V':>7}{'V基准':>7}{'V倍数':>7}{'|后5日|':>8}{'基准':>7}{'倍数':>7}")
    aV=[];aR=[];tot=0;lags=[]
    for s in STOCKS:
        txs=[x for x in load(s) if x["code"]==code and (not plan_f or not x["plan"])]
        if len(txs)<3: continue
        cl=clusters(txs,K)
        stt=[x for x in (fwd(s,c["knownAt"]) for c in cl) if x]
        if len(stt)<3: continue
        d=D[s]; ex=set(x["date"] for x in stt)
        bV=med([d["fv"][i] for i in range(len(d["d"])) if d["fv"][i] is not None and d["d"][i] not in ex])
        bR=med([abs(d["fr"][i]) for i in range(len(d["d"])) if d["fr"][i] is not None and d["d"][i] not in ex])
        V=med([x["V"] for x in stt]); R=med([abs(x["fr"]) for x in stt])
        yrs=len(d["d"])/252; lag=med([c["lag"] for c in cl]); lags+= [c["lag"] for c in cl]
        aV+=[x["V"] for x in stt]; aR+=[abs(x["fr"]) for x in stt]; tot+=len(stt)
        print(f"{s:6}{len(txs):6d}{len(cl):6d}{len(cl)/yrs:7.1f}{lag:8.0f}日{V:7.2f}{bV:7.2f}{V/bV:7.2f}{R:8.1f}%{bR:6.1f}%{R/bR:7.2f}")
    if tot:
        gb=[];gr=[]
        for s in STOCKS:
            gb+=[x for x in D[s]["fv"] if x is not None]; gr+=[abs(x) for x in D[s]["fr"] if x is not None]
        print(f"\n  合计 {tot} 次 · 滞后中位 {med(lags):.0f} 日   V {med(aV):.2f} vs 基准 {med(gb):.2f} → **倍数 {med(aV)/med(gb):.2f}**"
              f"   |后5日| {med(aR):.1f}% vs {med(gr):.1f}% → 倍数 {med(aR)/med(gr):.2f}")
print("# EV 族回测（修正版：触发时点 = 最早凑够 K 人的申报日）")
for K in [2,3]: run("P",False,K,"EV1 内部人簇买")
for K in [2,3]: run("S",True,K,"EV2 内部人簇卖")
run("S",False,2,"对照：不剔 10b5-1")
