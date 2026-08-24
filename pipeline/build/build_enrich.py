# -*- coding: utf-8 -*-
"""补齐 symbols 与 findings 里 build.py 不产出的部分：新闻 · 资金费率 · 用户线。

⚠️ 这三块原来都没有生产者，重跑 build.py 就会丢。审计发现的「管线产不出自己的数据」
   有一半是它们。
"""
import json, os, statistics as st, datetime as dt
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..')  # build/ → 仓库根
D=os.path.join(ROOT,'mock/data')
RAW=json.load(open(os.path.join(ROOT,'pipeline/raw/daily.json')))
NEWS=json.load(open(os.path.join(ROOT,'pipeline/raw/news_market.json')))['news']
CFG=json.load(open(os.path.join(ROOT,'mock/config/alerts.json')))
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import US, CR, POS, CASH, NAME, LOGO   # ⚠️ 账本单一来源，见 book.py
DR1_THRESHOLD=0.0005      # |费率| ≥ 0.05% / 8h

def num(x, d=None):
    try: return float(x)
    except Exception: return d

# ── 新闻 ──────────────────────────────────────────────────────────
SENT={"Bearish":-0.7,"Somewhat-Bearish":-0.35,"Neutral":0.0,
      "Somewhat-Bullish":0.35,"Bullish":0.7}
def iso(t):
    # 端点给 "2026-08-21 21:07:12-00" —— 空格分隔、两位偏移量，不是合法 ISO 8601
    if not t: return None
    t=t.strip().replace(' ','T')
    if len(t)>=3 and t[-3] in '+-' and t[-3:].lstrip('+-').isdigit(): t=t+':00'
    return t
by={}
for sym,items in NEWS.items():
    rows=[]
    for it in items:
        rows.append({
          "title":it.get('title'),"url":it.get('url'),
          "publishedAt":iso(it.get('t')),"source":it.get('src'),
          "summary":it.get('sum'),
          # ⚠️ 端点给的是标签串。契约要数值 —— 在这里转，
          #    不要让界面拿 Math.abs("Somewhat-Bullish") 去比 0.35（结果是 NaN，着色规则静默失效）
          "sentiment":SENT.get(it.get('sent')) if isinstance(it.get('sent'),str) else num(it.get('sent')),
          "sentimentLabel":it.get('sent') if isinstance(it.get('sent'),str) else None,
          "relevance":num(it.get('rel'))})
    by[sym]=rows

# ── 资金费率 ───────────────────────────────────────────────────────
def funding(s):
    txt=RAW['funding'].get(s) or ''
    pts=[]
    for l in txt.strip().split('\n'):
        if not l: continue
        p=l.split(',')
        r=num(p[1]) if len(p)>1 else None
        if r is None: continue
        pts.append({"t":p[0],"rate":round(r,8)})
    pts.sort(key=lambda x:x['t'])
    days=sorted({p['t'][:10] for p in pts if abs(p['rate'])>=DR1_THRESHOLD})
    return {"asOf":pts[-1]['t'] if pts else None,"unit":"8h","threshold":DR1_THRESHOLD,
            "normalized":False,
            "normalizeNote":"本窗口全部落在 2025-12 单位变更之后，无需归一。",
            "points":pts,"extremeDays":days}

for s in US+CR:
    p=f'{D}/symbols/{s}.json'; d=json.load(open(p))
    d['news']=sorted(by.get(s,[]),key=lambda x:str(x['publishedAt']),reverse=True)[:8]
    if s in CR: d['funding']=funding(s)
    json.dump(d,open(p,'w'),ensure_ascii=False)

# ── 用户线 findings ────────────────────────────────────────────────
F=f'{D}/findings.json'; fj=json.load(open(F)); ASOF=fj['asOf']; day=ASOF[:10]
port=json.load(open(f'{D}/portfolio.json')); H={h['symbol']:h for h in port['holdings']}
bl=json.load(open(f'{D}/baselines.json'))
fj['findings']=[f for f in fj['findings'] if not f['signalId'].startswith('US')]
KIND={'US1':lambda c,dd,v: c<=v, 'US2':lambda c,dd,v: c>=v, 'US3':lambda c,dd,v: dd<=v}
TIME={'US1':'14:22','US2':'11:05','US3':'16:00'}
for sym,lines in CFG['userLines'].items():
    h=H.get(sym)
    if not h: continue
    for sig,v in lines.items():
        actual = h['fromHighPct'] if sig=='US3' else h['last']
        if not KIND[sig](h['last'], h['fromHighPct'], v): continue
        fj['findings'].append({
          "id":f"{day}:{sym}:{sig}","symbol":sym,"assetClass":h['assetClass'],
          "signalId":sig,"unit":"session","severity":"warning",
          "triggeredAt":f"{day}T{TIME[sig]}:00-04:00","knownAt":f"{day}T{TIME[sig]}:00-04:00",
          "episodeId":f"{day}:{sym}","novelty":None,"priority":None,
          "measured":{"z":None,"rvol":None,"move":h['todayPct']},
          "trigger":{"unit":"session","moveAt":f"{day}T{TIME[sig]}:00-04:00",
                     "thresholdSource":"user_set","barSlot":None,
                     "userLine":{"kind":sig,"value":v,"actual":round(actual,5)}},
          "delivery":{"level":"L1","cappedBy":None},
          "context":{"benchmark":None,"sizeRank":None,"pnl":None,
                     "attribution":{"timing":"none","summary":None,"sources":[],
                                    "model":None,"generatedAt":None}}})
fj['findings'].sort(key=lambda f:(f['triggeredAt'],f['symbol']))
SCANNED_HOLDER={}   # 在 news.json 写完之后回填，见文件末尾
fj.pop('gaps',None)          # gaps 只在 meta.json，一处
json.dump(fj,open(F,'w'),ensure_ascii=False,indent=1)
print(f"新闻 {sum(len(v) for v in by.values())} 条 · 用户线 findings "
      f"{[f['id'] for f in fj['findings'] if f['signalId'].startswith('US')]}")
for s in CR:
    f=json.load(open(f'{D}/symbols/{s}.json'))['funding']
    print(f"  {s:5s} 费率 {len(f['points']):3d} 点 · 极端日 {len(f['extremeDays'])}")

# ── data/news.json · Tab 1 底部的今日相关新闻（宽链）──────────────
MINREL=0.80
raw_n=sum(len(v) for v in by.values())
# ⚠️ 按 URL 去重。端点对同一篇稿件按每个提及的标的各返回一次 ——
#    不去重的话读者会在列表里看到同一条头条四遍（NVDA + AMD × 两个来源）。
seen={}
for sym,rows in by.items():
    for r in rows:
        if (r.get('relevance') or 0) < MINREL: continue
        u=r.get('url')
        if u in seen: seen[u]['symbols'].append(sym); continue
        seen[u]=dict(r, symbol=sym, symbols=[sym])
flat=sorted(seen.values(), key=lambda r: str(r['publishedAt']), reverse=True)
json.dump({"asOf":ASOF,"chain":"wide","minRelevance":MINREL,"items":flat[:12]},
          open(f'{D}/news.json','w'), ensure_ascii=False, indent=1)
print(f"news.json {len(flat[:12])} 条 · 取回 {raw_n} 条 · 过筛去重后 {len(flat)} 条")

# scanned 的三个数各有各的含义，不能互相顶替：
#   newsItems  取回多少条（去重前）
#   newsPassed 过了相关度门且去重后剩多少条 —— 这一句存在的意义就是报出被滤掉了多少
fj=json.load(open(F))
fj['scanned']={"holdings":len(port['holdings']),"newsItems":raw_n,"newsPassed":len(flat)}
json.dump(fj,open(F,'w'),ensure_ascii=False,indent=1)
print(f"scanned: {fj['scanned']}")

# ── series.benchmark：SPY 序列 ─────────────────────────────────────
SP=os.path.join(ROOT,'pipeline/raw/spy.csv')
if os.path.exists(SP):
    spy={l.split(',')[0]: float(l.split(',')[1]) for l in open(SP) if l.strip()}
    S_=f'{D}/series.json'; sj=json.load(open(S_))
    days=[p['d'] for p in sj['points']]
    base=next((spy[d] for d in days if d in spy), None)
    if base:
        sj['benchmark']['points']=[{"d":d,"cumReturn":round(spy[d]/base-1,5)}
                                   for d in days if d in spy]
        json.dump(sj,open(S_,'w'),ensure_ascii=False)
        print(f"benchmark SPY {len(sj['benchmark']['points'])} 点")
