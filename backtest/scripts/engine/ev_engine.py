import json, math, statistics as st, os
D=json.load(open("signals.json")); med=st.median
STOCKS=["AAPL","MSFT","NVDA","TSLA","AMD","PLTR","RIVN","SOFI","KO","XOM","MSTR"]
FWD=5; WIN=30   # 簇窗口 30 日历日

def load(sym):
    out=[]
    for ln in open(f"ev/{sym}.csv"):
        p=ln.strip().split("|")
        if len(p)<6: continue
        out.append(dict(td=p[0], fd=p[1], code=p[2], plan=p[3]=="1", officer=p[4]=="1", owner=p[5]))
    return out

def days(a,b):
    from datetime import date
    ya,ma,da=map(int,a.split("-")); yb,mb,db=map(int,b.split("-"))
    return (date(yb,mb,db)-date(ya,ma,da)).days

def clusters(txs, K):
    """簇用 transaction_date 定义；触发时点 = 该簇内最晚的 filing_date"""
    txs=sorted(txs, key=lambda x:x["td"])
    fired=[]; last_end=""
    for i,a in enumerate(txs):
        win=[x for x in txs if 0 <= days(a["td"], x["td"]) < WIN]
        if len(set(x["owner"] for x in win))>=K:
            end_td=max(x["td"] for x in win)
            if end_td<=last_end: continue
            knownAt=max(x["fd"] for x in win)          # ⭐ 可知时点
            fired.append(dict(td_end=end_td, knownAt=knownAt, n_owner=len(set(x["owner"] for x in win)),
                              n_tx=len(win), officer=sum(1 for x in win if x["officer"])))
            last_end=end_td
    return fired

def fwd_stats(sym, dstr):
    """从可知日之后第一个交易日算起的前瞻表现"""
    d=D[sym]; idx=None
    for i,t in enumerate(d["d"]):
        if t>=dstr: idx=i; break
    if idx is None or idx+FWD>=len(d["d"]): return None
    if d["fv"][idx] is None: return None
    return dict(V=d["fv"][idx], fr=d["fr"][idx], z=d["z"][idx], rv=d["rv"][idx], date=d["d"][idx])

def baseline(sym, exclude):
    d=D[sym]; ex=set(exclude)
    vs=[d["fv"][i] for i in range(len(d["d"])) if d["fv"][i] is not None and d["d"][i] not in ex]
    frs=[abs(d["fr"][i]) for i in range(len(d["d"])) if d["fr"][i] is not None and d["d"][i] not in ex]
    return med(vs), med(frs)

def run(code, plan_filter, K, label):
    print(f"\n### {label}  (code={code} · K={K}"
          + (" · 剔除 is_10b51" if plan_filter else "") + ")\n")
    print(f"{'标的':6}{'笔数':>6}{'簇次':>6}{'次/年':>7}{'滞后中位':>9}{'V':>7}{'V基准':>7}{'V倍数':>7}{'|后5日|':>8}{'基准':>7}{'倍数':>7}")
    allV=[];allB=[];allR=[];allRB=[];tot=0
    for s in STOCKS:
        txs=[x for x in load(s) if x["code"]==code and (not plan_filter or not x["plan"])]
        if len(txs)<3: continue
        cl=clusters(txs,K)
        if not cl: continue
        st_=[fwd_stats(s,c["knownAt"]) for c in cl]
        st_=[x for x in st_ if x]
        if len(st_)<3: continue
        lag=med([days(c["td_end"],c["knownAt"]) for c in cl])
        bV,bR=baseline(s,[x["date"] for x in st_])
        V=med([x["V"] for x in st_]); R=med([abs(x["fr"]) for x in st_])
        yrs=len([t for t in D[s]["d"]])/252
        allV+= [x["V"] for x in st_]; allR+=[abs(x["fr"]) for x in st_]; tot+=len(st_)
        print(f"{s:6}{len(txs):6d}{len(cl):6d}{len(cl)/yrs:7.1f}{lag:8.0f}日{V:7.2f}{bV:7.2f}{V/bV:7.2f}{R:8.1f}%{bR:6.1f}%{R/bR:7.2f}")
    if tot:
        gb=[];gr=[]
        for s in STOCKS:
            d=D[s]
            gb+=[x for x in d["fv"] if x is not None]; gr+=[abs(x) for x in d["fr"] if x is not None]
        print(f"\n  合计 {tot} 次触发   V {med(allV):.2f} vs 全样本基准 {med(gb):.2f} → 倍数 {med(allV)/med(gb):.2f}"
              f"   |后5日收益| {med(allR):.1f}% vs {med(gr):.1f}% → 倍数 {med(allR)/med(gr):.2f}")
    return tot

print("# EV 族回测 · 内部人交易")
print("\n触发时点用 filing_date（可知日），簇定义用 transaction_date —— 防前视")
for K in [2,3]:
    run("P", False, K, f"EV1 内部人簇买")
for K in [2,3]:
    run("S", True, K, f"EV2 内部人簇卖（剔 10b5-1）")
run("S", False, 2, "对照组：内部人簇卖（不剔 10b5-1）")
