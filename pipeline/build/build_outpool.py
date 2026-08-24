# -*- coding: utf-8 -*-
"""第四个 demo 账本：池外标的 + 新股。真实回放到 2025-10-15。

为什么要有它：产品的核心要求是「对没见过的组合也能用」，而承载这句话的两条路径
——兜底阈值、基线不足——在主账本上一次都渲染不出来（8 只全是 validated / 502 根）。
2025-10-15 是一个真实的日子：ETF 基线充足走兜底反解，FIG 54 根 / KLAR 26 根真的不足。
"""
import json, os, statistics as st, math
ASOF="2025-10-15"; W=90; MIN_USABLE=60; THETA_Z=1.5
FB=json.load(open('pipeline/raw/fallback_solved.json'))          # ETF 反解结果
RAW=json.load(open('pipeline/raw/outpool.json'))
OUT='mock/data-outpool'; os.makedirs(OUT+'/symbols', exist_ok=True)

BOOK={"SPY":{"cls":"other","kind":"ETF","sh":40,"cost":430.0},
      "QQQ":{"cls":"other","kind":"ETF","sh":25,"cost":390.0},
      "GLD":{"cls":"other","kind":"ETF","sh":30,"cost":215.0},
      "CHYM":{"cls":"us_equity","kind":"个股","sh":300,"cost":24.0},
      "FIG": {"cls":"us_equity","kind":"个股","sh":150,"cost":58.0},
      "KLAR":{"cls":"us_equity","kind":"个股","sh":400,"cost":36.0}}
THV={"us_equity":2.0,"other":FB["theta_v"]}

def rob(v):
    m=st.median(v); return m, 1.4826*st.median([abs(x-m) for x in v])

S={}
for s in BOOK:
    rows=[]
    for l in RAW[s].strip().split('\n'):
        if not l: continue
        p=l.split(',')
        if p[0]>ASOF: continue
        # d,c,v,o,h,l —— 缺 OHLC 时退化成收盘价，K 线图会画成一条线而不是蜡烛
        o,h,lo = (float(p[3]),float(p[4]),float(p[5])) if len(p)>=6 else (float(p[1]),)*3
        rows.append((p[0],float(p[1]),float(p[2]),o,h,lo))
    rows.sort()
    S[s]={"d":[r[0] for r in rows],"c":[r[1] for r in rows],"v":[r[2] for r in rows],
          "o":[r[3] for r in rows],"h":[r[4] for r in rows],"l":[r[5] for r in rows]}

baselines={}; ent_of={}; scan=[]; findings=[]; total=0.0; vals={}
for s,B in BOOK.items():
    d,c,v=S[s]["d"],S[s]["c"],S[s]["v"]; n=len(c)
    vals[s]=B["sh"]*c[-1]; total+=vals[s]
    usable = n>=MIN_USABLE
    src = "validated" if B["cls"]=="us_equity" else "fallback_solved"
    tv=THV[B["cls"]]
    ent={"sigmaRobust":None,"sigmaAnn":None,"baselineDays":n,"usable":usable,
         "m23":{"rho":None,"n":0,"verdict":"insufficient_sample"},
         "thresholds":{"theta_z":THETA_Z,"theta_v":tv,"source":src,
                       "theta_z_bar":None,"theta_v_bar":None},
         "triggerLine":{"session":None,"bar":None},
         "historicalTriggers":{"PV1":0,"PV5":None,"windowSessions":n,
                               "last7":{"PV1":0,"PV5":None}},
         # ⚠️ `signalGrades` 原来是空的，而 findings 那边写着 `cappedBy: "symbol_grade"` ——
         #    契约要求 `cappedBy` 指向的那一处**确实等于** level，空的就对不上。
         #    ETF 的阈值是兜底反解的，没人验证过，所以证据等级封顶 L2 —— 这是真的分档，不是凑数。
         "signalGrades":({"PV1":{"maxDelivery":"L2","verdict":"unvalidated_class"}}
                         if B["cls"]=="other" else {}),
         "degraded":None if n>=MIN_USABLE else "short_baseline"}
    if usable:
        ret=[None]+[c[i]/c[i-1]-1 for i in range(1,n)]
        m,sg=rob([x for x in ret[-W:] if x is not None])
        vm=st.median(v[-W:])
        ent["sigmaRobust"]=round(sg,6)
        ent["sigmaAnn"]=round(st.pstdev([x for x in ret[-min(60,n-1):] if x is not None])*math.sqrt(252),4)
        ent["triggerLine"]["session"]={"price":round(THETA_Z*sg,5),"volume":tv}
        today_z=(ret[-1]-m)/sg if sg>0 else 0
        today_rv=v[-1]/vm if vm>0 else 0
        trig=abs(today_z)>=THETA_Z and today_rv>=tv
        # 历史触发天数
        hits=0; histrows=[]; zs=[]
        for i in range(W+1,n):
            mm,ss=rob([x for x in ret[i-W:i] if x is not None]); vv=st.median(v[i-W:i])
            if ss<=0 or vv<=0: continue
            zi=(ret[i]-mm)/ss; rvi=v[i]/vv
            zs.append(abs(zi))
            if abs(zi)>=THETA_Z and rvi>=tv:
                hits+=1; histrows.append({"d":d[i],"signalId":"PV1",
                                          "z":round(zi,2),"rvol":round(rvi,2)})
        ent["historicalTriggers"]["PV1"]=hits
        ent["alertHistory"]=histrows          # 与 historicalTriggers 同一次计算，不能两处各算
        # M23 分布可用性（决策 #10）。样本 < 250 → PV4 覆盖标注
        if len(zs)>=250:
            rho=sum(1 for x in zs if x>=THETA_Z)/len(zs)
            ent["m23"]={"rho":round(rho,4),"n":len(zs),
                        "verdict":"pass" if 0.02<=rho<=0.60 else ("too_tight" if rho<0.02 else "too_loose")}
        else:
            ent["m23"]={"rho":None,"n":len(zs),"verdict":"insufficient_sample"}
        a=sorted(abs(x) for x in ret[1:] if x is not None)
        ent["distribution"]={"p50":round(a[len(a)//2],5),"p95":round(a[int(len(a)*.95)],5),
                             "p99":round(a[int(len(a)*.99)],5)}
        scan.append({"symbol":s,"state":"triggered" if trig else "quiet","unit":"session",
                     "price":{"today":round(ret[-1],5),"line":round(THETA_Z*sg,5),"usual":round(sg,5)},
                     "volume":{"rvol":round(today_rv,3),"line":tv,"partial":False},
                     "bar":None})
        if trig:
            findings.append({"id":f"{ASOF}:{s}:PV1","symbol":s,"signalId":"PV1",
              "episodeId":f"{ASOF}:{s}","unit":"session",
              "triggeredAt":ASOF+"T16:00:00-04:00","knownAt":ASOF+"T16:00:00-04:00",
              "severity":"warning","priority":None,"novelty":None,
              # ⚠️ `delivery` 是契约必填 —— 缺了它这条 finding 在页面上没有投递层，
              #    而 committed 的 fixture 里一直有。也就是说**生成器和它生成的数据早就分叉了**，
              #    因为从来没人重跑过它。ETF 的证据等级封顶 L2（阈值是兜底反解的）。
              "delivery":{"level":"L2","cappedBy":"symbol_grade"},
              "assetClass":B["cls"],
              "measured":{"z":round(today_z,3),"rvol":round(today_rv,3),"move":round(ret[-1],5)},
              "trigger":{"unit":"session","moveAt":ASOF+"T16:00:00-04:00",
                         "thresholdSource":src,"barSlot":None},
              "context":{"benchmark":{"symbol":None,"benchmarkMove":None,"symbolMove":None,"applicable":False},"sizeRank":None,
                         "pnl":{"today":None,"shares":B["sh"],"lifetime":None},
                         "attribution":{"timing":"none","summary":None,"sources":[],
                                        "model":None,"generatedAt":None}}})
    else:
        scan.append({"symbol":s,"state":"insufficient_baseline","baselineDays":n,
                     "unit":"session","price":None,"volume":None,"bar":None})
    ent_of[s]=ent.pop("alertHistory",[])
    baselines[s]=ent

CASH=1500.0; total+=CASH
hold=[{"symbol":s,"name":s,"assetClass":BOOK[s]["cls"],"logo":None,
       "last":round(S[s]["c"][-1],2),
       "todayPct":round(S[s]["c"][-1]/S[s]["c"][-2]-1,5),
       "fiveDayPct":round(S[s]["c"][-1]/S[s]["c"][-6]-1,5) if len(S[s]["c"])>6 else None,
       "shares":BOOK[s]["sh"],"avgCost":BOOK[s]["cost"],
       "value":round(vals[s],2),"weight":round(vals[s]/total,4),
       "lifetimePnl":round(BOOK[s]["sh"]*(S[s]["c"][-1]-BOOK[s]["cost"]),2),
       "vol30d":None,"fromHighPct":round(S[s]["c"][-1]/max(S[s]["c"][-60:])-1,4),
       "spark":[round(x,4) for x in S[s]["c"][-30:]],"notes":[]} for s in BOOK]
cost=sum(BOOK[s]["cost"]*BOOK[s]["sh"] for s in BOOK)
byc={}
for s in BOOK: byc[BOOK[s]["cls"]]=byc.get(BOOK[s]["cls"],0)+vals[s]
port={"linked":True,"asOf":ASOF+"T16:00:00-04:00","cash":CASH,
 "kpi":{"totalValue":round(total,2),
        "totalPnl":{"abs":round(total-CASH-cost,2),"pctOnCost":round((total-CASH-cost)/cost,4)},
        "todayPnl":{"abs":None,"pct":None},
        "fromHigh":{"pct":None,"high":None,"sessionsAgo":None}},
 "holdings":hold,
 "allocation":{"byHolding":[{"key":s,"value":round(vals[s],2),"weight":round(vals[s]/total,4)} for s in BOOK],
   "byAssetClass":[{"key":k,"value":round(v,2),"weight":round(v/total,4)} for k,v in byc.items()],
   "byTheme":[]},
 "checks":[]}

json.dump(baselines,open(OUT+'/baselines.json','w'),ensure_ascii=False,indent=1)
json.dump(port,open(OUT+'/portfolio.json','w'),ensure_ascii=False,indent=1)
json.dump({"asOf":ASOF+"T16:00:00-04:00","findings":findings,"scan":scan,
           "scanned":{"holdings":len(BOOK),"newsItems":0,"newsPassed":0},
           "gaps":[]},open(OUT+'/findings.json','w'),ensure_ascii=False,indent=1)
json.dump({"specVersion":"2026-08-22","generatedAt":ASOF+"T16:00:00-04:00","nextRun":None,
  "freshness":{"prices":ASOF+"T16:00:00-04:00"},
  # ⚠️ 这两条原来叫 `..._etf` 与 `..._new_listings` —— 页面按第一个 `:` 之前查表，
  #    带下划线后缀的名字一个都查不到，于是把裸 id 印给用户。
  #    canonical 名字加冒号负载才对（`unvalidated_asset_class:3,2.0`）。
  #    同一个概念两种拼法，本身就是重复定义。
  "gaps":[f"unvalidated_asset_class:{sum(1 for x in BOOK if BOOK[x]['cls']=='other')},2.0",
          f"insufficient_baseline:{','.join(x for x in BOOK if BOOK[x]['cls']!='other')}",
          "no_intraday_for_this_book"]},open(OUT+'/meta.json','w'),ensure_ascii=False,indent=1)
for s in BOOK:
    K=S[s]
    json.dump({"symbol":s,"kline":[{"d":d,"o":round(o,4),"h":round(h,4),"l":round(lo,4),
                                    "c":round(c,4),"v":round(v,1)}
               for d,o,h,lo,c,v in zip(K["d"][-260:],K["o"][-260:],K["h"][-260:],
                                       K["l"][-260:],K["c"][-260:],K["v"][-260:])],
               "alertHistory":ent_of.get(s,[]),
               "range52w":{"low":round(min(S[s]["c"][-252:]),2),"high":round(max(S[s]["c"][-252:]),2),"asOf":ASOF},
               "coverage":{"pv5From":None}},
              open(f'{OUT}/symbols/{s}.json','w'),ensure_ascii=False)

print(f"账本 as-of {ASOF} · {len(BOOK)} 只 · 总额 {total:,.2f}")
print(f"{'标的':6s} {'类别':10s} {'基线':>5s} {'阈值来源':16s} {'状态':20s} {'θv':>5s}")
for s in BOOK:
    b=baselines[s]; sc=[x for x in scan if x['symbol']==s][0]
    print(f"{s:6s} {BOOK[s]['kind']:10s} {b['baselineDays']:5d} {b['thresholds']['source']:16s} "
          f"{sc['state']:20s} {b['thresholds']['theta_v']:5.2f}")
print(f"\n今日触发 {len(findings)} 条 · 基线不足 {sum(1 for x in scan if x['state']=='insufficient_baseline')} 只")
