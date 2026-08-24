# -*- coding: utf-8 -*-
"""数据里出现的字段名，output-schema.md 全文必须提到过。

不解析 spec 里的 JSON 代码块 —— 那些块带省略号和注释，解析器会大面积失败，
把「没读进来」报成「漂了」。一个报 126 条误报的检查等于没有检查。
改成：数据里的叶子字段名，在 spec 全文里搜得到就算文档化。
"""
import json,re,collections
SPEC='product/output-schema.md'
FILES=['findings.json','baselines.json','portfolio.json','market.json',
       'meta.json','signals.json','series.json',
       '../config/alerts.json']
# 值当键用的，不是字段名。⚠️ 这里原来是写死的字面量 —— 账本的第八份副本。
# 往账本里加两只标的，这个检查就把它们报成「schema 漂移」，
# 而它们是**值**不是字段名。列表只有一个家：pipeline/book.py。
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../pipeline/lib'))
from book import POS as _BOOK
SYMS = set(_BOOK) | {'SPY','QQQ','GLD','CHYM','FIG','KLAR'}   # 后六个是池外那本账
SKIP=re.compile(r'^\d{2}:\d{2}$|^\d{4}-\d{2}-\d{2}|^(PV|EV|DR|MA|PO|PF|US|M)\d+$')

spec=open(SPEC).read()
seen=collections.defaultdict(set)
def walk(o,pre,f,depth=0):
    if depth>7: return
    if isinstance(o,dict):
        for k,v in o.items():
            if k in SYMS or SKIP.match(k): walk(v,pre,f,depth+1); continue
            seen[k].add(f); walk(v,pre+'.'+k,f,depth+1)
    elif isinstance(o,list) and o:
        for x in o[:3]: walk(x,pre+'[]',f,depth+1)

for fn in FILES:
    try: walk(json.load(open(f'mock/data/{fn}')),'',fn.split('/')[-1])
    except Exception as e: print(f'⚠️ 读不到 {fn}: {e}')

# ⚠️ 要认带路径的写法。只认裸名会把 `trigger.barSlot` 报成「没文档」——
#    检查器说的话和它实际在查的东西不是一回事。
def documented(k):
    e=re.escape(k)
    return re.search(r'[`"](?:[A-Za-z_][\w\[\]]*\.)*'+e+r'[`"]', spec) or \
           re.search(r'^\s*'+e+r'\b', spec, re.M) or \
           re.search(r'[`"]'+e+r'\.', spec)
miss=sorted(k for k in seen if not documented(k))
print(f'数据字段 {len(seen)} 个 · schema 未提及 {len(miss)} 个')
if miss:
    print('\n⚠️ 数据里有、output-schema.md 全文找不到：')
    for k in miss: print(f'   {k:22s} 出现在 {" ".join(sorted(seen[k]))}')
else:
    print('✅ 全部字段在 schema 里有出处')
