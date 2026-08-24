# -*- coding: utf-8 -*-
"""从原始价量算 M 层 → S 层 → 落 output-schema 的文件。纯本地，无网络。"""
import json, os, sys, statistics as st, math, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import US, CR, OT, POS, CASH, NAME, LOGO, THEME   # ⚠️ 账本单一来源，见 book.py
ALL = US + CR + OT
FB  = json.load(open('pipeline/raw/fallback_solved.json'))   # ETF 池级反解出的 θv

RAW = json.load(open('pipeline/raw/daily.json'))
OUT = 'mock/data'
CLS = {**{s:"us_equity" for s in US}, **{s:"crypto" for s in CR}, **{s:"other" for s in OT}}
THETA_Z = 1.5
# ⚠️ 「其他」的 θv 不是拍的，也不是套美股 —— 它是在 18 只 ETF 的池上反解出来的，
#    对齐同一个池级触发率锚。实测 1.75 而美股是 2.00：GLD 今天量比 1.913，
#    美股那条线会漏掉它。数值读 fallback_solved.json，不在这里写死。
THETA_V = {"us_equity":2.0, "crypto":3.0, "other":FB["theta_v"]}
W       = 90     # σ_rob 与量中位的窗口
MIN_BASE= 60     # PV4 覆盖门槛
HIST    = 502    # 「过去两年」窗口

# 模拟持仓：股数与成本是编的，价格与基线全是真的

def bars(sym):
    rows=[]
    for line in RAW["daily"][sym].splitlines():
        d,o,h,l,c,v = line.split(",")
        rows.append((d,float(o),float(h),float(l),float(c),float(v)))
    rows.sort()                                  # 返回是倒序，排正
    return rows

def robust(vals):
    m=st.median(vals); mad=st.median([abs(x-m) for x in vals])
    return m, 1.4826*mad

def build_symbol(sym):
    b=bars(sym); cls=CLS[sym]
    d=[x[0] for x in b]; c=[x[4] for x in b]; v=[x[5] for x in b]
    rets=[(d[i], c[i]/c[i-1]-1, v[i]) for i in range(1,len(b))]
    n=len(rets)
    # 今日读数
    win=[x[1] for x in rets[n-1-W:n-1]]
    med,sig = robust(win)
    vmed = st.median([x[2] for x in rets[n-1-W:n-1]])
    z    = (rets[-1][1]-med)/sig if sig>0 else None
    rvol = rets[-1][2]/vmed if vmed>0 else None
    tv   = THETA_V[cls]
    fired= (z is not None and abs(z)>=THETA_Z and rvol is not None and rvol>=tv)
    # 历史触发
    def scan(k):
        out=[]
        for i in range(W, n):
            w=[x[1] for x in rets[i-W:i]]
            m2,s2 = robust(w)
            if s2<=0: continue
            zz=(rets[i][1]-m2)/s2
            vm=st.median([x[2] for x in rets[i-W:i]])
            rv=rets[i][2]/vm if vm>0 else 0
            if abs(zz)>=THETA_Z and rv>=tv:
                # 线是**当日**的（θz × 当日窗口的 σ），不是今天的
                out.append((rets[i][0], round(zz,2), round(rets[i][1],5),
                            round(rv,2), round(THETA_Z*s2,5)))
        return out
    trig = scan(HIST)
    tail = [t for t in trig if t[0] >= d[max(0,len(d)-HIST)]]
    last7= [t for t in trig if t[0] >= d[max(0,len(d)-8)]]
    # 分布
    allr=[x[1] for x in rets[-HIST:]]
    absr=sorted(abs(x) for x in allr)
    q=lambda p: absr[min(len(absr)-1,int(p*len(absr)))]
    lo,hi=min(allr),max(allr); bw=(hi-lo)/40 if hi>lo else 1
    counts=[0]*40
    for x in allr:
        k=min(39,int((x-lo)/bw)); counts[k]+=1
    # 幅度分位
    today=rets[-1][1]
    rank=sum(1 for x in allr if x<=today) if today<0 else sum(1 for x in allr if x>=today)
    # 52 周
    yr=b[-252:] if len(b)>=252 else b
    lo52=min(x[3] for x in yr); hi52=max(x[2] for x in yr)
    baseline_days=min(n, HIST)
    return dict(sym=sym, cls=cls, bars=b, rets=rets, d=d, c=c,
        sigma=sig, vmed=vmed, z=z, rvol=rvol, fired=fired, tv=tv,
        trig=tail, last7=last7, counts=counts, lo=lo, bw=bw,
        p50=q(.5), p95=q(.95), p99=q(.99), rank=rank, nrank=len(allr),
        lo52=lo52, hi52=hi52, baseline_days=baseline_days,
        usable=baseline_days>=MIN_BASE, today=today)

S={s:build_symbol(s) for s in ALL}
ASOF=max(S[s]["d"][-1] for s in S)

# ─────────────── 这一轮的时刻 ───────────────
# ⚠️ 加密没有 16:00 收盘。Binance 日线按 UTC 切，自然日 D 那根收在 D+1 00:00Z
#    —— 夏令时下是 D 20:00 ET。把所有标的的 PV1 一律写成 16:00 ET，
#    等于让这一轮报出四小时后才知道的收盘价：
#    实测 DOGE 卡片写「16:00 ET $0.0916」，而 16:00 ET 当时是 $0.0849。
#    这是不用统计就能发现的边界矛盾 —— 任何 finding 都不能晚于产出它的那一轮。
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")

def close_dt(cls, d):
    """该类资产在自然日 d 的收盘时刻。夏冬令时由 tz 库决定，不写死偏移。"""
    if cls == "crypto":
        return (dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc)
                + dt.timedelta(days=1)).astimezone(ET)
    return dt.datetime.fromisoformat(d + "T16:00:00").replace(tzinfo=ET)

def close_ts(cls, d): return close_dt(cls, d).isoformat()

# 本账本的 asOf = 持仓里最晚的那个收盘 —— 混合账本由加密决定
ASOF_TS = max(close_dt(S[s]["cls"], ASOF) for s in S).isoformat()
print(f"asOf {ASOF_TS}\n")
print(f"{'标的':6s} {'类别':10s} {'σ_rob':>7s} {'价格线':>8s} {'今日':>8s} {'量比':>6s} {'量线':>5s} {'z':>7s} {'触发':>4s} {'两年':>4s} {'近7':>4s}")
for s in ALL:
    x=S[s]
    print(f"{s:6s} {x['cls']:10s} {x['sigma']*100:6.2f}% {THETA_Z*x['sigma']*100:7.2f}% "
          f"{x['today']*100:7.2f}% {x['rvol']:6.2f} {x['tv']:5.1f} {x['z']:7.2f} "
          f"{'✅' if x['fired'] else '—':>4s} {len(x['trig']):4d} {len(x['last7']):4d}")
json.dump({s:{k:v for k,v in S[s].items() if k not in('bars','rets','d','c')} for s in S},
          open('pipeline/raw/computed.json','w'), default=float)

# ─────────────────────────── 落盘 ───────────────────────────
import shutil
os.makedirs(f'{OUT}/symbols', exist_ok=True); os.makedirs('mock/config', exist_ok=True)

def last_close(s): return S[s]["c"][-1]
vals={s: POS[s]["sh"]*last_close(s) for s in S}
total=sum(vals.values())+CASH

# ---------- portfolio.json ----------
hold=[]
for s in ALL:
    x=S[s]; c=last_close(s); cost=POS[s]["cost"]*POS[s]["sh"]
    five=(c/S[s]["c"][-6]-1) if len(S[s]["c"])>6 else None
    hold.append({"symbol":s,"name":NAME[s],"assetClass":x["cls"],"logo":LOGO.get(s),
        "shares":POS[s]["sh"],"avgCost":POS[s]["cost"],
        "last":round(c,4),"todayPct":round(x["today"],5),
        "fiveDayPct":round(five,5) if five is not None else None,
        "value":round(vals[s],2),"weight":round(vals[s]/total,4),
        "lifetimePnl":round(vals[s]-cost,2),
        "vol30d":round(st.pstdev([S[s]["c"][i]/S[s]["c"][i-1]-1 for i in range(-30,0)]),5),   # 日频，与 sigmaRobust 同量纲

        # M22：距高点回撤 = 与全历史 running max 比，不是与近 60 根的最大值比。
        # 60 根窗口下 DOGE/SOL/BTC 全印 0.0000 —— 页面说它们在自己的高点上，
        # 而 DOGE 实际低 86.7%。它还是 US3 的输入。
        "fromHighPct":round(c/max(S[s]["c"])-1,4),
        "spark":[round(v,4) for v in S[s]["c"][-30:]],
        "notes":[]})
tot_cost=sum(POS[s]["cost"]*POS[s]["sh"] for s in S)
day_pnl=sum(POS[s]["sh"]*last_close(s)*S[s]["today"]/(1+S[s]["today"]) for s in S)
byc={}
for s in S: byc[S[s]["cls"]]=byc.get(S[s]["cls"],0)+vals[s]

# 主题：PF2/PF3 与 Tab 1「按主题」切面共用这一份。仅美股 —— 加密没有主题维度。
# ⚠️ 界面不得自带主题表：漏一只标的会让它静默落进「无主题数据」，
#    读者看到的是「我们没数据」，实际是「我们表里没有它」。
byt={}
for s in US:
    t=THEME.get(s)
    if t is None: raise SystemExit(f"❌ {s} 没有主题归类 —— 补进 THEME，不要留空")
    byt[t]=byt.get(t,0)+vals[s]
port={"linked":True,"asOf":ASOF_TS,
 "cash":round(CASH,2),
 "kpi":{"totalValue":round(total,2),
        "totalPnl":{"abs":round(total-CASH-tot_cost,2),"pctOnCost":round((total-CASH-tot_cost)/tot_cost,4)},
        "todayPnl":{"abs":round(day_pnl,2),"pct":round(day_pnl/(total-day_pnl),5)},
        "fromHigh":{"pct":None,"high":None,"sessionsAgo":None}},
 "holdings":hold,
 "allocation":{"byHolding":[{"key":s,"value":round(vals[s],2),"weight":round(vals[s]/total,4)} for s in ALL],
   "byAssetClass":[{"key":k,"value":round(v,2),"weight":round(v/total,4)} for k,v in byc.items()],
   # ⚠️ 带上 members。没有成员，界面就无法按账本重算 ——
   #    实测加密only 的账本里这一栏列着五只美股，合计 $46.8K 而账本只有 $18.4K。
   #    界面不该去猜哪只属于哪个主题，数据该把它说出来。
   "byTheme":[{"key":k,"value":round(v,2),"weight":round(v/total,4),
               "members":sorted(x for x in US if THEME.get(x)==k)}
              for k,v in sorted(byt.items(), key=lambda kv:-kv[1])]},
 "checks":[{"signalId":"PF2","value":round(max(byt.values())/sum(byt.values()),4),
            "detail":{"theme":max(byt,key=byt.get),
                      "holdings":sum(1 for s in US if THEME[s]==max(byt,key=byt.get))}}]}

# ---------- series.json ----------
days=sorted(set.intersection(*[set(S[s]["d"]) for s in S]))[-HIST:]
idx={s:{d:c for d,c in zip(S[s]["d"],S[s]["c"])} for s in S}
pts=[]; prev=None
for d in days:
    v=sum(POS[s]["sh"]*idx[s][d] for s in S)+CASH
    pts.append({"d":d,"value":round(v,2),
                "dayPnl":round(v-prev,2) if prev else 0,
                "cumReturn":round(v/(sum(POS[s]["sh"]*idx[s][days[0]] for s in S)+CASH)-1,4)})
    prev=v
hi=max(pts,key=lambda p:p["value"])
port["kpi"]["fromHigh"]={"pct":round(pts[-1]["value"]/hi["value"]-1,4),"high":hi["value"],
                         "sessionsAgo":len(pts)-1-pts.index(hi)}
# ⚠️ 这条序列是用**今天的份额**回推历史收盘价得到的，不是真实净值。
#    契约 §十一 明确禁止在真实 Playbook 里这么做（我们没有历史持仓快照）。
#    mock 需要一条曲线，所以留着，但必须自报家门 —— 否则
#    「距高点 −39.23%，420 个交易日前」会被当成事实。
series={"unit":"USD","points":pts,
        "basis":"backcast",
        "basisNote":"用今日份额回推历史收盘价。真实 Playbook 只能从建立那天起记。",
        "benchmark":{"symbol":"SPY","points":[],"coverage":"us_equity_only"},
        "high":{"d":hi["d"],"value":hi["value"]}}

# ---------- baselines.json ----------
base={}
for s in ALL:
    x=S[s]
    base[s]={"sigmaRobust":round(x["sigma"],6),
      "sigmaAnn":round(x["sigma"]*math.sqrt(365 if x["cls"]=="crypto" else 252),4),
      "baselineDays":x["baseline_days"],"usable":x["usable"],
      "distribution":{"p50":round(x["p50"],5),"p95":round(x["p95"],5),"p99":round(x["p99"],5),
                      "histogram":{"from":round(x["lo"],5),"binWidth":round(x["bw"],6),"counts":x["counts"]}},
      # ⚠️ 未验证类别的来源写 fallback_solved —— 界面据此封住证据等级。
      # 写成 validated 等于把已验证的标记借给一条没测过的规则。
      "thresholds":{"theta_z":THETA_Z,"theta_v":x["tv"],
                    "source":("fallback_solved" if x["cls"]=="other" else "validated")},
      "triggerLine":{"session":{"price":round(THETA_Z*x["sigma"],5),"volume":x["tv"]}},
      "historicalTriggers":{"PV1":len(x["trig"]),"windowSessions":min(x["baseline_days"],HIST),
                            "last7":{"PV1":len(x["last7"])}},
      "degraded":("high_vol" if x["sigma"]*math.sqrt(365 if x["cls"]=="crypto" else 252)>(0.928 if x["cls"]=="crypto" else 0.50) else None)}

# ---------- findings.json ----------
fnd=[]; scan=[]
for s in ALL:
    x=S[s]
    scan.append({"symbol":s,"state":"triggered" if x["fired"] else ("insufficient_baseline" if not x["usable"] else "quiet"),
      "unit":"session",
      # ⚠️ 这一行的读数来自哪一根 bar，不是这一轮的时刻（契约 §findings.scan）。
      # 混合账本在周末有两个「最近收盘」：美股停在周五，加密每天都有。
      # 顶层 ASOF 是 max()，用它给每一行贴标签，等于把周五的读数说成周日的。
      # producer.js 一直写这个字段，本文件漏了 —— 于是 mock 从来没走过逐行那条路，
      # 页面的回退分支把差异盖住了，看起来两边一致。
      "asOf":x["d"][-1],
      "price":{"today":round(x["today"],5),"line":round(THETA_Z*x["sigma"],5),"usual":round(x["sigma"],5)},
      "volume":{"rvol":round(x["rvol"],3),"line":x["tv"],"partial":False}})
    if x["fired"]:
        fnd.append({"id":f"{ASOF}:{s}:PV1","symbol":s,"signalId":"PV1",
          "episodeId":f"{ASOF}:{s}","unit":"session",
          "triggeredAt":close_ts(x["cls"],ASOF),"knownAt":close_ts(x["cls"],ASOF),
          "severity":"critical","priority":None,"novelty":None,
          "measured":{"z":round(x["z"],3),"rvol":round(x["rvol"],3),"move":round(x["today"],5)},
          "trigger":{"unit":"session","moveAt":close_ts(x["cls"],ASOF),
                     "thresholdSource":("fallback_solved" if x["cls"]=="other" else "validated"),"barSlot":None},
          "context":{"sizeRank":{"rank":x["rank"],"of":x["nrank"]},
            "attribution":{"timing":"none","summary":None,"sources":[],"model":None,"generatedAt":None}}})
# 跨日时如实记 gap，与 producer.js 同一个键；页面的 gapSpan 文案读它。
_span=sorted({S[s]["d"][-1] for s in ALL})
findings={"asOf":ASOF_TS,"findings":fnd,"scan":scan,
  "scanned":{"holdings":len(S),"newsItems":0,"newsPassed":0},
  "gaps":(["holdings_span_multiple_sessions:"+",".join(_span)] if len(_span)>1 else [])}

def merge(old, new):
    """逐层合并。⚠️ build.py 只拥有自己算的那些字段 ——
    整体覆盖会把下游 builder 的产出冲成 null，而那看起来像上游没给。"""
    if not isinstance(old, dict) or not isinstance(new, dict): return new
    out = dict(old)
    for k, v in new.items(): out[k] = merge(old.get(k), v)
    return out

# ---------- symbols/<SYM>.json ----------
def ins(s):
    if s not in RAW["insider"] or not RAW["insider"][s]: return None
    # ⚠️ 真的按窗口筛。原来 filedInWindow 数的是整个拉取结果，
    #    而页面写着「30 天内 N 条」—— NVDA 实测窗口内只有 2 条，页面说 25 条。
    WIN=30
    cut=(dt.date.fromisoformat(ASOF)-dt.timedelta(days=WIN)).isoformat()
    items=[]; sells=[]; inwin=0
    for ln in RAW["insider"][s].splitlines():
        p=ln.split("|")
        if len(p)<4 or p[0]<cut: continue
        inwin+=1
        if p[1] not in ("P","S"): continue
        # ⚠️ `amount` 带符号：负 = 处置。股数取绝对值，方向由 `code` 说，
        #    两处各说各的会让「卖出 −8023 股」这种自相矛盾的写法出现在页面上。
        amt = float(p[3]) if len(p)>3 and p[3] not in("","None") else None
        px  = float(p[4]) if len(p)>4 and p[4] not in("","None") else None
        row={"filingDate":p[0],"owner":p[2],"code":p[1],
             "shares":(abs(int(amt)) if amt is not None else None),
             "price":px,
             # 这一笔的金额。股数与价都在，才说得出「卖了多少钱」
             "value":(round(abs(amt)*px,2) if (amt is not None and px) else None)}
        (items if p[1]=="P" else sells).append(row)
    items=sorted(items,key=lambda i:i["filingDate"],reverse=True)[:12]
    # ⚠️ 空列表也要返回。「这个资产类别没有内部人这回事」（加密，键缺省）
    #    与「这只票本期没有公开市场买入」（美股，键在但 items 为空）是两件事，
    #    合并成「键不在」会让页面留一个洞，读者只能读成「数据没取到」。
    sells=sorted(sells,key=lambda i:i["filingDate"],reverse=True)[:12]
    # 买入与卖出一起展示。⚠️ 只有买入是信号（EV1）——
    #    EV2 已证伪，且在大盘股上是反向的，当作预警会指错方向。
    return {"windowDays":WIN,
            "buys":  {"people":len({i["owner"] for i in items}),"filings":len(items),
                      "items":items,"signalId":"EV1"},
            "sells": {"people":len({i["owner"] for i in sells}),"filings":len(sells),
                      "items":sells,"signalId":None},
            "filedInWindow":inwin,"codeFilter":["P","S"]}
def earn(s):
    if s not in RAW["earnings"] or not RAW["earnings"][s]: return None
    rows=sorted([l.split(",") for l in RAW["earnings"][s].splitlines()], key=lambda r:r[0])
    fut=[r for r in rows if r[0]>ASOF]
    past=[r for r in rows if r[0]<=ASOF]
    # ⚠️ 没有未来日期就写 null，不要拿最近一次已发布的顶上 ——
    #    页面会把它印成「下次财报」，而那是三个月前的日子。
    #    「日历没覆盖到」和「下次在某天」是两句话。
    nxt=min(fut,key=lambda r:r[0]) if fut else None
    return {"next":(nxt[0] if nxt else None),
            "time":(nxt[1] if nxt else None),
            "lastReported":(past[-1][0] if past else None),
            "past":[{"d":r[0],"time":r[1]} for r in past[-8:]]}
for s in ALL:
    x=S[s]; b=x["bars"][-HIST:]
    doc={"symbol":s,
      "kline":[{"d":r[0],"o":r[1],"h":r[2],"l":r[3],"c":r[4],"v":r[5]} for r in b],
      "range52w":{"low":round(x["lo52"],4),"high":round(x["hi52"],4),"asOf":ASOF},
      # ⚠️ 只给 z 不够：marker tooltip 要报「价格 vs 当日的线 · 量比 vs 线」，
      #    缺了就印三个破折号。线是**当日**的，不是今天的
      "alertHistory":[{"d":t[0],"signalId":"PV1","z":t[1],"move":t[2],
                       "rvol":t[3],"priceLine":t[4],"volLine":x["tv"]}
                      for t in x["trig"]],
      "news":[]}
    if x["cls"]=="us_equity":
        i=ins(s);  e=earn(s)
        doc["insider"]=i          # 美股恒有此键，空是空态不是缺省
        if e: doc["earnings"]=e
    else:
        f=RAW["funding"].get(s,"")
        if f:
            doc["funding"]={"asOf":ASOF,"points":[{"t":l.split(",")[0],"rate":float(l.split(",")[1])}
                            for l in f.splitlines()[:60] if l.split(",")[1] not in("","None")]}
    p=f'{OUT}/symbols/{s}.json'
    prev=json.load(open(p)) if os.path.exists(p) else {}
    json.dump(merge(prev,doc),open(p,'w'),ensure_ascii=False)

# ⚠️ baselines 与 symbols 合并写，不整体覆盖 ——
#    m23 · signalGrades · theta_*_bar · triggerLine.bar · historicalTriggers.PV5 ·
#    distributionBar 都由下游 builder 产出。整体覆盖会把它们全冲掉，
#    而冲掉的表现是「字段变 null」，看起来像上游没给。
for name, obj in [("portfolio", port), ("series", series), ("findings", findings)]:
    json.dump(obj, open(f'{OUT}/{name}.json', 'w'), ensure_ascii=False)

p = f'{OUT}/baselines.json'
prev = json.load(open(p)) if os.path.exists(p) else {}
json.dump({s: merge(prev.get(s, {}), base[s]) for s in base}, open(p, 'w'), ensure_ascii=False)
# ---------- meta.json 的时间字段 ----------
# ⚠️ 这几个字段原来是手写的，改 asOf 时不会跟着动 —— 那正是「同一事实多个副本」。
#    gaps / specVersion 仍由人维护，所以合并写不覆盖。
_g = dt.datetime.fromisoformat(ASOF_TS) + dt.timedelta(minutes=5)
p_meta = f'{OUT}/meta.json'
prev = json.load(open(p_meta)) if os.path.exists(p_meta) else {}
# ⚠️ 这一轮真正产出了哪几条信号。页面据此把「没人在算」与「你关掉了」分开 ——
#    两者对读者意味着完全不同的下一步。本地管线跑的是全套。
json.dump(merge(prev, {"producedSignals": ["PV1","PV5","EV1","EV4","DR1","US1","US2","US3"],
                       "generatedAt": _g.isoformat(),
                       "nextRun": (_g + dt.timedelta(minutes=30)).isoformat(),
                       # ⚠️ 五个键都要写。`freshness` 是「四个 producer 都跑过」的收据 ——
                       #    判官靠它区分「这一轮没数据」与「这个 producer 从没跑过」。
                       #    本地管线跑的是全套，所以五个键都该有；此前只写 prices，
                       #    于是 mock 看起来像一份「只跑了一个 producer」的产物。
                       "freshness": {"prices": ASOF_TS, "intraday": ASOF_TS,
                                     "news": ASOF_TS, "earningsCalendar": ASOF_TS,
                                     "market": ASOF_TS}}),
          open(p_meta, 'w'), ensure_ascii=False, indent=1)

print("\n落盘：", ", ".join(sorted(os.listdir(OUT))))
print("symbols/:", ", ".join(sorted(os.listdir(f'{OUT}/symbols'))))
print(f"\n组合总值 ${total:,.2f} · 当日 {day_pnl:+,.2f} · 触发 {len(fnd)} 条")
