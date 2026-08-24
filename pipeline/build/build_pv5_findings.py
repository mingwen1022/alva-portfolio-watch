# -*- coding: utf-8 -*-
"""把 PV5 的当日触发根写进 findings 与 baselines。

⚠️ 一天多根就是多条 finding —— signal-spec §5.3.1「日内 findings 累积不替换」。
   只留最强那根会丢掉方向相反的早盘根（实测 DOGE 09:00 向下、21:30 向上）。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from book import POS                      # ⚠️ 账本单一来源，见 book.py
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..')  # build/ → 仓库根
D=os.path.join(ROOT,'mock/data')
PV5=json.load(open(os.path.join(ROOT,'pipeline/raw/pv5.json')))
# ⚠️ 逐日明细与条数现在同源，都来自 pv5.json —— 见 build_pv5.py 里的说明。
#    `pv5_full.json` 已废弃：它读的 /tmp/full_*.csv 不存在，重跑不出来。
CLS={s:v['cls'] for s,v in POS.items()}   # 第六份副本，已并入 book.py
TV_BAR={'us_equity':2.0,'crypto':3.0}

F=os.path.join(D,'findings.json'); fj=json.load(open(F))
ASOF=fj['asOf']; day=ASOF[:10]
fj['findings']=[f for f in fj['findings'] if f['signalId']!='PV5']

B=os.path.join(D,'baselines.json'); bl=json.load(open(B))
for s,o in PV5.items():
    cls=CLS[s]; b=bl[s]
    b['thresholds']['theta_z_bar']=o['tz']; b['thresholds']['theta_v_bar']=o['tv']
    # ⚠️ 逐槽位基线要进契约。运行期的盘中 producer 只取当天，
    #    对着这份基线算 —— 没有它就得每 15 分钟重拉 135 天分钟线。
    b['slotBaselines']=o.get('slotBaselines') or {}
    b.setdefault('triggerLine',{})['bar']=({"price":o['line'],"volume":o['tv']} if o['line'] else None)
    ht=b['historicalTriggers']; ht['PV5']=o['triggerDays']; ht['last7']['PV5']=o['last7Days']
    for bar in o['todayFiredBars']:
        fj['findings'].append({
          "id":f"{day}:{s}:PV5:{bar['slot']}","symbol":s,"assetClass":cls,"signalId":"PV5",
          "unit":"bar","severity":"critical",
          "triggeredAt":bar['t']+":00Z","knownAt":bar['t']+":00Z",
          "episodeId":f"{day}:{s}","novelty":None,"priority":None,
          "measured":{"z":bar['z'],"rvol":bar['rvol'],"move":bar['move']},
          "trigger":{"unit":"bar","moveAt":bar['t']+":00Z",
                     "thresholdSource":b['thresholds']['source'],"barSlot":bar['slot'],
                     # ⚠️ 这根 bar 的收盘价。日线卡有价格、盘中卡没有，不是刻意留白 ——
                     #    契约里本来就没有这个字段，页面于是只能不印。
                     "barClose":bar['close']},
          "delivery":{"level":"L1","cappedBy":None},
          "context":{"benchmark":{"symbol":None,"benchmarkMove":None,"symbolMove":None,"applicable":False},
                     "sizeRank":None,
                     "attribution":{"timing":"none","summary":None,"sources":[],
                                    "model":None,"generatedAt":None}}})
    # scan 行的盘中块
    row=next((x for x in fj['scan'] if x['symbol']==s),None)
    if row is not None:
        strongest=o.get('todaySlot')
        row['bar']={"z":o['todayZ'],"rvol":o['todayRvol'],"slot":strongest,
                    "line":o['line'],"volumeLine":TV_BAR[cls],
                    "bars":o['todayBars'],
                    "state":"triggered" if o['firedToday'] else "quiet"}
fj['findings'].sort(key=lambda f:(f['triggeredAt'],f['symbol']))
json.dump(fj,open(F,'w'),ensure_ascii=False,indent=1)
json.dump(bl,open(B,'w'),ensure_ascii=False,indent=1)

# alertHistory 的 PV5 条目
for s,o in PV5.items():
    p=os.path.join(D,f'symbols/{s}.json'); d=json.load(open(p))
    hist=[x for x in d.get('alertHistory',[]) if x.get('signalId')!='PV5']
    days=sorted(o['byDay'].items())[-bl[s]['historicalTriggers']['PV5']:] if o['byDay'] else []
    for dd,bars in days:
        top=max(bars,key=lambda b:abs(b['z']))
        hist.append({"d":dd,"signalId":"PV5","n":len(bars),"z":top['z'],"rvol":top['rvol'],
                     # byDay 的每一项已经带 slot，不再从 't' 现切 —— 那是旧结构的字段
                     "bars":[{"slot":b['slot'],"z":b['z'],"rvol":b['rvol']} for b in bars]})
    d['alertHistory']=sorted(hist,key=lambda x:x['d'])
    json.dump(d,open(p,'w'),ensure_ascii=False)
n5=[f for f in fj['findings'] if f['signalId']=='PV5']
print(f"PV5 findings {len(n5)} 条：", [(f['symbol'],f['trigger']['barSlot'],f['measured']['z']) for f in n5])
