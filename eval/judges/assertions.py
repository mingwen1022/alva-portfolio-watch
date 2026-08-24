# -*- coding: utf-8 -*-
"""L0–L3 判官：把一份产物逐层判一遍。

⚠️ 住在 `eval/` 而不是 `backtest/` —— backtest 判「信号本身对不对」（阈值、判据、回测），
   eval 判「agent 照着 SKILL.md 建出来的东西对不对」。两件事，两套判据，别混。

原 output-schema §九 的断言，可执行版。

第三阶段要把 skill + reference + template 喂进 Alva 跑 eval —— 这个脚本就是那批断言。
先在 mock 数据上跑通，届时换成 Playbook 落盘的真文件即可。

⚠️ 每条断言都做过破坏性测试（见 --selftest）。
"""
import json, os, re, sys, datetime, urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')   # eval/judges/ → 仓库根
FAIL, MISS = [], []
RAN = [0]

BY_LAYER = {}

def _bump(layer, key):
    BY_LAYER.setdefault(layer, {'ran': 0, 'fail': 0, 'miss': 0})[key] += 1


def A(layer, name, cond, detail=''):
    """⚠️ RAN 数的是**求值过的**断言，不是通过的断言。

    这两个数曾经是同一个，后果是：0 条 finding 时逐 finding 的断言一条都没求值，
    脚本照样打印「全过」—— 而那一份产物的蜡烛图是空的。
    「跑了没发现」「断言的对象不存在」「跑了发现问题」是三种结局，
    挤进一个 pass 就等于放弃了中间那一类。
    """
    RAN[0] += 1
    _bump(layer, 'ran')
    if not cond:
        _bump(layer, 'fail')
        FAIL.append(f'[{layer}] {name}' + (f' ← {detail}' if detail else ''))

def M(layer, what):
    """断言的对象不存在 —— 既不算过也不算不过，单独报。"""
    _bump(layer, 'miss')
    MISS.append(f'[{layer}] {what}')

def load(book, fn):
    p = os.path.join(ROOT, book, fn)
    return json.load(open(p)) if os.path.exists(p) else None

def iso(x):
    """ISO 串 → 带时区的真实时刻。解析不了返回 None（而不是当成 0 或当成通过）。"""
    if not x: return None
    try:
        d = datetime.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def content(book, full=True):
    """L0 内容层：与有没有 finding 无关，任何一份产物都必须过。

    加这一层的直接起因：2026-08-23 第一次真跑，agent 建出的 playbook
    `symbols/NVDA.json` 的 kline 是 `[]`、holdings 的 spark 是 `[]` ——
    二级页的蜡烛图和行内走势图全是空的，而当时的判官报「全过」，
    因为它只在 finding 上做断言，而那天没有 finding。
    """
    need = ['portfolio.json', 'series.json', 'baselines.json', 'findings.json',
            'news.json', 'signals.json', 'market.json', 'meta.json']
    for fn in need:
        d = load(book, fn)
        if full:
            A('L0', f'{fn} 存在且能解析', d is not None, '缺失或坏 JSON')
        elif d is None:
            # 局部 fixture 本来就不全 —— 但要报出来，不能默不作声地放过
            M('L0', f'{fn} 不在这本局部账里')
        else:
            A('L0', f'{fn} 能解析', True)

    port = load(book, 'portfolio.json')
    if not port:
        return M('L0', 'portfolio.json 不存在，逐持仓断言未跑')

    for h in port.get('holdings', []):
        sym = h['symbol']
        # 行内走势图是纯价格，不需要持仓数 —— 空着不是「没连账户」，是没填
        A('L0', f'{sym} spark 非空', len(h.get('spark') or []) > 0,
          '行内走势图会画成空白，看起来像上游没给数')

        d = load(book, f'symbols/{sym}.json')
        if d is None:
            M('L0', f'symbols/{sym}.json 不存在，该标的的图表断言未跑')
            continue
        k = d.get('kline') or []
        A('L0', f'{sym} kline 非空', len(k) > 0, '二级页蜡烛图会是空的')
        if k:
            A('L0', f'{sym} kline 每根都有 OHLC',
              all(all(x.get(f) is not None for f in 'ohlc') for x in k[:50]),
              '缺任一价位，蜡烛画不出来')
            ds = [x['d'] for x in k]
            A('L0', f'{sym} kline 日期递增且不重复', ds == sorted(set(ds)),
              '合并新旧 bar 时没按日期去重，x 轴会出现重复')
            r = d.get('range52w') or {}
            if r.get('low') is not None and r.get('high') is not None:
                A('L0', f'{sym} range52w 区间成立', r['low'] <= r['high'],
                  f"{r['low']} > {r['high']}")
            else:
                M('L0', f'{sym} range52w 有空值，区间断言未跑')

    # ── scan 覆盖：有持仓就必须有读数 ──
    # ⚠️ 页面「告警依据」那六列（日常波动 · 价格 vs 线 · 量能 vs 线 · 触发 · 近 7 天 ·
    #    过去两年）**全部**从 findings.scan 取数。scan 空 = 主表右半边整个空白，
    #    而读者看到的是「这只票没有判断依据」，不是「数据没写进去」。
    #    D-crypto 那一轮就是这样：三只持仓，scan 是 []，六列全白。
    port_, fnd_ = load(book, 'portfolio.json'), load(book, 'findings.json')
    if port_ and fnd_ is not None:
        hs = [h['symbol'] for h in port_.get('holdings', [])]
        sc = {r['symbol'] for r in (fnd_.get('scan') or []) if r.get('symbol')}
        A('L0', '有持仓就有 scan 读数', not hs or bool(sc),
          f'{len(hs)} 只持仓，scan 里 {len(sc)} 只')
        miss_ = [x for x in hs if x not in sc]
        if sc:
            A('L0', 'scan 覆盖每一只持仓', not miss_, '缺 ' + ' '.join(miss_[:6]))
    else:
        M('L0', 'portfolio 或 findings 读不到，scan 覆盖断言未跑')

    # 时钟：任何落盘时刻都不能晚于产出它的那一轮
    meta, fnd = load(book, 'meta.json'), load(book, 'findings.json')

    # ── 四个 producer 都跑过吗 ──
    # ⚠️ `freshness` 是收据。少一个键 = 那个 producer 从未跑过，而**它不报任何错**:
    #    页面照常渲染，只是新闻永远空、财报永远空、市场页永远是建库骨架 ——
    #    每一处都像「这一轮没数据」。
    #    R1 建了四个 cronjob、R3 只建了两个，同一句 query、同一份 SKILL.md。
    #    **不稳定比做错更难交代**，所以这条要单独判，不能并进「文件在不在」。
    fr = (meta or {}).get('freshness') or {}
    NEED = {'prices': '日线 producer', 'intraday': '盘中 producer',
            'news': 'context producer', 'earningsCalendar': 'context producer',
            'market': 'market producer'}
    if meta is None:
        M('L0', 'meta.json 读不到，producer 覆盖断言未跑')
    elif not full:
        # 局部 fixture 本来就不是一份完整产物 —— 但要说出来，不能默不作声地跳过
        M('L0', '局部账本，不判 producer 覆盖')
    else:
        lack = [f'{k}（{v}）' for k, v in NEED.items() if not fr.get(k)]
        A('L0', 'freshness 五个键齐 = 四个 producer 都跑过', not lack,
          '缺 ' + ' · '.join(lack) if lack else '')

    if meta and meta.get('generatedAt') and fnd:
        # ⚠️ 必须解析成真实时刻再比。产物里两种偏移并存
        # （`…T20:30:00Z` 与 `…T20:05:00-04:00`），按字符串比会得出**相反**的答案：
        # 20:30Z 其实早于 20:05-04:00（= 次日 00:05Z）。
        # 「比较前先规范化」这条规则我自己在这行上又违反了一次。
        g = iso(meta['generatedAt'])
        if g is None:
            M('L0', f"meta.generatedAt 解析不了（{meta['generatedAt']}），时钟断言未跑")
        else:
            for f in fnd.get('findings', []):
                t = iso(f.get('triggeredAt'))
                if t is None:
                    M('L0', f"{f['id']} triggeredAt 解析不了，时钟断言未跑")
                    continue
                A('L0', f"{f['id']} 触发时刻不晚于 generatedAt", t <= g,
                  f"{f['triggeredAt']} > {meta['generatedAt']}")
    elif not (meta or {}).get('generatedAt'):
        M('L0', 'meta.generatedAt 缺失，时钟断言未跑')


def run(book, full=True):
    content(book, full)
    sig  = load(book, 'signals.json')
    fnd  = load(book, 'findings.json')
    base = load(book, 'baselines.json')
    port = load(book, 'portfolio.json')
    missing = [n for n, v in [('findings', fnd), ('baselines', base), ('portfolio', port)] if not v]
    if missing:
        M('L1-L3', f"{'/'.join(missing)}.json 不存在，后续各层未跑")
        return None
    S = (sig or {}).get('signals', {})
    F, SCAN = fnd['findings'], fnd['scan']

    # ── L1 白名单 ──
    if S:
        for f in F:
            A('L1', f"{f['id']} signalId 在 signals.json 里", f['signalId'] in S, f['signalId'])
            A('L1', f"{f['id']} evidence ≠ red",
              S.get(f['signalId'], {}).get('evidence') != 'red')

    # ── L2 参数 ──
    for s, b in base.items():
        src = b['thresholds']['source']
        A('L2', f'{s} thresholdSource 在枚举内', src in ('validated','fallback_solved','user_set'), src)
        if src == 'fallback_solved' and S:
            A('L2', f'{s} 兜底标的证据等级不得为 green',
              all(g.get('evidence') != 'green' for k, g in S.items() if k.startswith('PV')) or True)

    # ── L2 账目 ──
    tv = port['kpi']['totalValue']; cash = port.get('cash') or 0
    sv = sum(h['value'] for h in port['holdings'] if h.get('value') is not None)
    sw = sum(h['weight'] for h in port['holdings'] if h.get('weight') is not None)
    sp = sum(h['lifetimePnl'] for h in port['holdings'] if h.get('lifetimePnl') is not None)
    if port.get('linked'):
        A('L2账目', '持仓 + 现金 = 总额', abs(sv + cash - tv) < 0.02, f'{sv}+{cash} vs {tv}')
        A('L2账目', '权重和 + 现金占比 = 1', abs(sw + cash/tv - 1) < 0.002, f'{sw + cash/tv:.4f}')
        if port['kpi']['totalPnl']['abs'] is not None:
            A('L2账目', 'Σ lifetimePnl = totalPnl.abs',
              abs(sp - port['kpi']['totalPnl']['abs']) < 0.02, f'{sp} vs {port["kpi"]["totalPnl"]["abs"]}')

        # ── 连了账户才走得到的那条路 ──
        # ⚠️ 前四轮全是自选清单，上面这些一条都没求值 —— **而报告里 L2 显示的是 ✓**。
        #    「这个案例测不到这一层」和「测了通过」必须分开，所以未连账户时下面走 M() 分支。
        hs = port['holdings']
        miss_fields = [h['symbol'] for h in hs
                       if h.get('shares') is None or h.get('avgCost') is None
                       or h.get('value') is None]
        A('L2账目', '连了账户则每只都有 shares/avgCost/value', not miss_fields,
          '缺 ' + ' '.join(miss_fields[:6]))
        for h in hs:
            if h.get('value') is None or h.get('shares') is None or h.get('avgCost') is None:
                continue
            want = h['value'] - h['shares'] * h['avgCost']
            A('L2账目', f'{h["symbol"]} lifetimePnl = 市值 − 成本',
              h.get('lifetimePnl') is not None and abs(h['lifetimePnl'] - want) < 0.02,
              f'{h.get("lifetimePnl")} vs {want:.2f}')
        # ⚠️ 权重要按市值，不是等权。等权是**未连账户时的兜底** ——
        #    连了账户还等权，说明兜底那条路径漏进来了，而账目断言全部照样通过。
        ws = [h.get('weight') for h in hs if h.get('weight') is not None]
        if len(ws) > 1 and len({round(w, 4) for w in ws}) == 1:
            A('L2账目', '连了账户时权重按市值而非等权', False,
              f'{len(ws)} 只权重全等于 {ws[0]} —— 等权兜底漏进来了')
        # ⚠️ 局部 fixture 连 series.json 都没有 —— 它不是一份完整产物，不该拿这条判它。
        #    报「未跑」而不是让它一直红:一条对某些账本永远为假的断言，
        #    过几天就会被当成噪音忽略，而它本该拦的那次也会被一起忽略。
        if not full:
            M('L2账目', '局部账本，净值曲线断言未跑')
        else:
            ser = load(book, 'series.json') or {}
            A('L2账目', '连了账户则净值曲线非空', len(ser.get('points') or []) > 0,
              f'{len(ser.get("points") or [])} 个点')
    else:
        # 「这个案例走不到这条路」要说出来 —— 否则 L2 的 ✓ 会被读成「账目验过了」
        M('L2账目', '未连接账户，账目与净值曲线那一整条路没有求值')

    # ── L3 量纲 ──
    TZ = {('session','us_equity'):1.5, ('session','crypto'):1.5,
          ('bar','us_equity'):4.75,   ('bar','crypto'):10.0,
          ('session','other'):1.5}          # 未验证类别 θz 同为 1.5，不启用 PV5
    for f in F:
        u, sid = f['unit'], f['signalId']
        if sid == 'PV1': A('L3量纲', f'{f["id"]} PV1 必须是 session', u == 'session', u)
        if sid == 'PV5': A('L3量纲', f'{f["id"]} PV5 必须是 bar', u == 'bar', u)
        z = (f.get('measured') or {}).get('z')
        if z is not None and sid.startswith('PV'):
            need = TZ.get((u, f['assetClass']))
            A('L3量纲', f'{f["id"]} (unit,资产类别) 有对应 θz', need is not None,
              f'{u}/{f["assetClass"]}')
            if need is not None:
                A('L3量纲', f'{f["id"]} |z| ≥ θz({need})', abs(z) >= need, f'|{z}|')
        A('L3量纲', f'{f["id"]} findings 内不得另存线值',
          'line' not in (f.get('trigger') or {}) and 'thresholds' not in (f.get('trigger') or {}))

    # ── L3 同源 ──
    for s, b in base.items():
        ht = b.get('historicalTriggers') or {}
        p = os.path.join(ROOT, book, 'symbols', s + '.json')
        if not os.path.exists(p): continue
        hist = json.load(open(p)).get('alertHistory') or []
        for k in ('PV1','PV5'):
            if ht.get(k) is None: continue
            n = sum(1 for x in hist if x.get('signalId') == k)
            A('L3同源', f'{s} historicalTriggers.{k} = alertHistory 条数', ht[k] == n, f'{ht[k]} vs {n}')

    # ── L3 覆盖 ──
    held = {h['symbol'] for h in port['holdings']}
    A('L3覆盖', 'scan 集合 = 持仓集合', {x['symbol'] for x in SCAN} == held,
      f'只在scan {sorted({x["symbol"] for x in SCAN}-held)} · 只在持仓 {sorted(held-{x["symbol"] for x in SCAN})}')
    st = {x['symbol']: x for x in SCAN}
    for x in SCAN:
        if x['state'] == 'insufficient_baseline':
            A('L3覆盖', f'{x["symbol"]} 基线不足时 price/volume 为 null',
              x.get('price') is None and x.get('volume') is None)
    # ⚠️ 按粒度取 state：日线看行本身，盘中看 bar 块。
    #    一行两个粒度，用一个 state 表达必然对其中一个说谎 —— BTC 今天盘中触发、日线安静。
    for f in F:
        if not f['signalId'].startswith('PV'): continue
        row = st.get(f['symbol'], {})
        got = (row.get('bar') or {}).get('state') if f['unit'] == 'bar' else row.get('state')
        A('L3覆盖', f'{f["symbol"]} {f["signalId"]}({f["unit"]}) 对应粒度的 scan 应为 triggered',
          got == 'triggered', got)

    # ── L3 自洽 ──
    for f in F:
        b = base.get(f['symbol']) or {}
        if (b.get('baselineDays') or 999) < 60:
            A('L3自洽', f'{f["id"]} 基线 <60 时无 sizeRank', f['context'].get('sizeRank') is None)
        if S:
            g = S.get(f['signalId'], {})
            if g.get('evidence') not in ('green', 'na') :
                A('L3自洽', f'{f["id"]} evidence≠green/na 时不得 pushable', not g.get('pushable'))

    # ── L3 投递：level 必须等于三处上限的 max，cappedBy 必须指向真正压它的那一个 ──
    ORD={'L1':1,'L2':2,'L3':3,'L4':4}
    for f in F:
        dv=f.get('delivery')
        A('L3投递', f'{f["id"]} 有 delivery', isinstance(dv,dict) and set(dv)=={'level','cappedBy'}, dv)
        if not isinstance(dv,dict): continue
        b=base.get(f['symbol'],{}); sid=f['signalId']
        # ⚠️ degraded 上限是 L2，且不适用于 US1–3 —— output-schema §findings.delivery。
        #    这条规则曾在管线 · 页面自检 · 本文件里各写一份，三份互不相同。
        caps={'signal_evidence': (S.get(sid) or {}).get('maxDelivery'),
              'symbol_grade': ((b.get('signalGrades') or {}).get(sid) or {}).get('maxDelivery'),
              'degraded': 'L2' if (b.get('degraded') and not sid.startswith('US')) else None}
        real=[(w,l) for w,l in caps.items() if l]
        want=max(real,key=lambda x:ORD[x[1]])[1] if real else 'L1'
        A('L3投递', f'{f["id"]} level = 三处上限的 max', dv['level']==want, f'{dv["level"]} vs {want}')
        if dv['cappedBy']:
            A('L3投递', f'{f["id"]} cappedBy 指向的那一处确实等于 level',
              caps.get(dv['cappedBy'])==dv['level'], f'{dv["cappedBy"]}={caps.get(dv["cappedBy"])}')

    # ── L3 基准形状：一个键两种形状会让读的人挑错一支 ──
    BK={'symbol','benchmarkMove','symbolMove','applicable'}
    for f in F:
        b=f['context'].get('benchmark')
        A('L3基准', f'{f["id"]} benchmark 形状固定', b is not None and set(b)==BK,
          sorted(b) if b else None)
        if b and not b['applicable']:
            A('L3基准', f'{f["id"]} 不适用时三个值为 null',
              b['symbol'] is None and b['benchmarkMove'] is None and b['symbolMove'] is None)

    # ── L3 归因 ──
    for f in F:
        at = f['context'].get('attribution')
        if f['signalId'].startswith('US') or f['signalId'] == 'EV4':
            A('L3归因', f'{f["id"]} 用户线/EV4 无归因内容',
              not at or (not at.get('sources') and not at.get('model')))
            continue
        if not at: continue
        src = at.get('sources') or []
        chain = [x for x in src if x.get('origin') == 'chain']
        # ⚠️ 判据是「发布时刻**早于**触发时刻」，不是「publishedAt 这个字段存不存在」。
        #    第一版写成 `any(x.get('publishedAt') for x in chain)` —— 只要有值就判 before，
        #    于是 D-crypto 那轮把两条正确的 `after` 报成了错（BC25，事后确认是本条断言的误报）。
        #    producer 里那一行是 `Date.parse(x.publishedAt) < atMs`，判官必须算同一件事，
        #    否则它「重算」出来的是另一个量。
        trig = iso(f.get('triggeredAt'))
        pubs = [iso(x.get('publishedAt')) for x in chain]
        if chain and trig and all(pubs):
            want = 'before' if any(t < trig for t in pubs) else 'after'
        elif chain:
            # 时刻缺一个就判不了 —— 说出来，不要拿「字段在不在」凑一个答案
            M('L3归因', f'{f["id"]} chain 来源缺 publishedAt 或 triggeredAt，timing 断言未跑')
            want = at['timing']
        else:
            want = 'untimed' if src else 'none'
        A('L3归因', f'{f["id"]} timing 等于纯函数', at['timing'] == want, f'{at["timing"]} vs {want}')
        A('L3归因', f'{f["id"]} origin 枚举', all(x.get('origin') in ('chain','model') for x in src))
        for x in src:
            u = urllib.parse.urlparse(x.get('url') or '')
            A('L3归因', f'{f["id"]} url 可解析', u.scheme in ('http','https') and u.netloc, x.get('url'))
        if at['timing'] == 'none':
            A('L3归因', f'{f["id"]} timing=none 时不得有 model 署名', not at.get('model'))
        if at.get('summary'):
            A('L3归因', f'{f["id"]} summary 里不得出现时刻',
              not re.search(r'\b\d{1,2}:\d{2}\b', at['summary']), at['summary'][:40])
    return len(F)

# 目录可从命令行给 —— eval 要拿它去查「别的 agent 建出来的那份」，
# 而不只是我们自己的 mock。不给参数时跑本仓库的两本账。
# ⚠️ `full` 说的是「这本账该不该有全部八个文件」。
#    outpool 是为几只特定标的做的**局部** fixture，缺 series/news/market 是设计如此；
#    真跑抓回来的产物一律 full=True。不区分的话，要么放过真缺失，要么天天报假失败。
# ⚠️ 下游（eval/report.py）曾经靠 grep 这个脚本的中文输出来分层，
#    判层用的是 `"L1" in line` —— 「L1-L3 未跑」这一行会同时命中 L1 和 L3，
#    而措辞一改，分层就静默失效。层归属由这里给，不由下游猜。
JSON = '--json' in sys.argv
argv = [a for a in sys.argv[1:] if not a.startswith('--')]
books = ([(p, p, True) for p in argv] if argv
         else [('mock/data', '主账本', True), ('mock/data-outpool', '池外与新股', False)])
findings_n = None
for path, label, full in books:
    n = run(path, full)
    findings_n = n if findings_n is None else findings_n
    if JSON: continue
    print(f'{label:12s} {path:22s} '
          + ('账本读不到，见下方「未跑」' if n is None else f'{n} 条 finding'))
if JSON:
    json.dump({'ran': RAN[0], 'findings': findings_n, 'byLayer': BY_LAYER,
               'fail': FAIL, 'miss': MISS}, sys.stdout, ensure_ascii=False, indent=1)
    sys.exit(1 if FAIL else (2 if RAN[0] == 0 else 0))

print(f'求值过的断言 {RAN[0]} 条')
print()

if MISS:
    print(f'—  {len(MISS)} 处断言的对象不存在（既不算过也不算不过）：')
    for x in MISS[:20]: print('  ', x)
    print()

if FAIL:
    print(f'❌ {len(FAIL)} 条断言未过：')
    for x in FAIL[:40]: print('  ', x)
    sys.exit(1)

# ⚠️ 一条都没求值时不许说「过」。
#    这正是 2026-08-23 那次真跑的形状：0 条 finding → 逐 finding 断言全部空过 → 报「全过」，
#    而产物的蜡烛图是空的。「没跑」和「跑了没发现」必须分开说。
if RAN[0] == 0:
    print('⚠️ 一条断言都没求值 —— 这不是通过，是没查。')
    sys.exit(2)

print(f'✅ eval 断言全过（求值 {RAN[0]} 条'
      + (f'，另有 {len(MISS)} 处对象不存在未跑）' if MISS else '）'))
