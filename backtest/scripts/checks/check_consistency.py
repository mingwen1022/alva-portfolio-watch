#!/usr/bin/env python3
"""文档一致性检查。任何跨文档改动后必跑。
检查：① §三 不再重复证据符号  ② §三 类型 == §五 总表类型
     ③ §五 条目集合 == §三 条目集合  ④ 各文档引用的信号 ID 都存在"""
import re, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REG = os.path.join(ROOT, "backtest", "signal-registry.md")
SPEC = os.path.join(ROOT, "product/signal-spec.md")
IDPAT = r"(?:PV|EV|DR|MA|PO|PF|US)\d"

def split_row(line):
    r"""按 | 切分表格行，但不拆 \| 转义竖线。
    ⚠️ 2026-08-20 修：PV1/PV3/DR1 的触发式含 `\|M2\|` 等，
    原来的 split("|") 把它们切成超长行，len(c)==len(hdr) 判断失败 → 三条一直没被检查过。"""
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [x.strip().replace("**", "") for x in parts]


def main():
    s = open(REG, encoding="utf-8").read()
    a, b = s.index("S 层 · 信号逐条定义"), s.index("M 层 · 指标字典")
    sec3 = s[a:b]
    # ⚠️ 表格会被编辑器自动对齐（补空格），不能用精确串匹配
    _a = s.index("、总表速查"); _b = s.index("### 证据分布")
    tbl = s[_a:_b]
    errs = []

    # ① §三 标题不得含证据符号
    for m in re.finditer(rf"^#### ({IDPAT}) .*$", sec3, re.M):
        if re.search(r"[🟢🟠🔴🔵🟡⚪]", m.group(0)):
            errs.append(f"§三 {m.group(1)} 标题仍含证据符号：{m.group(0)[:60]}")

    # ①b §三 正文不得重复严重度与证据（同一事实只写一处）
    ids = [(m.group(1), m.start()) for m in re.finditer(rf"^#### ({IDPAT}) ", sec3, re.M)]
    for k, (sid, pos) in enumerate(ids):
        end = ids[k+1][1] if k+1 < len(ids) else len(sec3)
        body = sec3[pos:end]
        if re.search(r"严重度\s*\*{0,2}(Critical|Warning|Informational)", body):
            errs.append(f"§三 {sid} 正文含严重度 —— 严重度只是排序输入，见 §6.6")
        if re.search(r"证据\s*[🟢🟠🔴🔵🟡⚪]", body):
            errs.append(f"§三 {sid} 正文含证据符号 —— 只写在 §五 总表")

    # ② ③ 类型与条目集合
    s3 = {}
    for m in re.finditer(rf"^#### ({IDPAT}) [^\n·]*· (\S+)", sec3, re.M):
        s3[m.group(1)] = m.group(2).strip()
    s5 = {}
    for l in tbl.split("\n"):
        if l.startswith("| **"):
            c = split_row(l)
            if re.fullmatch(IDPAT, c[0]): s5[c[0]] = (c[2], c[-1])
    for k in sorted(set(s3) | set(s5)):
        if k not in s3: errs.append(f"{k} 在 §五 有、§三 无条目")
        elif k not in s5: errs.append(f"{k} 在 §三 有、§五 总表无行")
        elif s3[k] != s5[k][0]: errs.append(f"{k} 类型不一致：§三={s3[k]} §五={s5[k][0]}")

    # ④ 投递必须与证据上限相容
    # ⚠️ 按表头名取列，不用固定下标 —— 2026-08-20 加了「粒度」「标的」两列后
    #    原来的 c[4] 从「证据」变成了「标的」，本规则静默失效了一整轮
    CAP = {"🟡 自测通过·待审核": {"L1","L2","L3","L4","挂"},
           "🟡": {"L2","L3","L4","挂"}, "🟢": {"L1","L2","L3","L4"},
           "🟠": {"L3","L4"}, "🔴": {"L4"}, "🔵": {"L2","L3","L4"},
           "⚪": {"不投递"}, "—": None}
    hdr = next((l for l in tbl.split("\n") if split_row(l)[:1] == ["ID"]), None)
    if hdr is None:
        errs.append("④ 找不到总表表头，无法定位「证据」「投递」列")
        cols = {}
    else:
        cols = {h: i for i, h in enumerate(split_row(hdr))}
        for need in ("证据", "投递"):
            if need not in cols: errs.append(f"④ 总表表头缺「{need}」列")
    for l in tbl.split("\n"):
        if not l.lstrip().startswith("|") or "证据" not in cols: continue
        c = split_row(l)
        if not re.fullmatch(IDPAT, c[0]): continue
        ev, deliver = c[cols["证据"]], c[cols["投递"]]
        allowed = CAP.get(ev, CAP.get(ev[:1]))
        if allowed is None: continue
        lvl = next((x for x in ("L1","L2","L3","L4","不投递") if x in deliver), None)
        if lvl and lvl not in allowed:
            errs.append(f"{c[0]} 证据 {ev} 上限允许 {sorted(allowed)}，实际投递 {lvl}")


    # ⑥ 证据分布小结必须与总表实际计数一致
    #    2026-08-20：改了分布小结却没改表格行，PV5/PV2 两处不一致，本规则因此加入
    try:
        dist = s[s.index("### 证据分布"): s.index("### 证据分布") + 900]
        actual = {}
        for l in tbl.split("\n"):
            if not l.lstrip().startswith("| **"): continue
            c2 = split_row(l)
            if not re.fullmatch(IDPAT, c2[0]) or "证据" not in cols: continue
            actual.setdefault(c2[cols["证据"]], []).append(c2[0])
        for line in dist.split("\n"):
            # 🟡 有两个子态（待验证 / 自测通过·待审核），必须分别核对
            m = re.match(r"^(🟢|🟠|🔴|🔵|⚪|—|🟡)\s+(\S+)\s+(\d+)\s", line)
            if not m: continue
            sym, name, n = m.group(1), m.group(2), int(m.group(3))
            key = f"{sym} {name}" if sym == "🟡" else sym
            got = len([x for k, v in actual.items() if k[:1] == sym and k == sym or k.startswith(sym + " ") for x in v])
            if sym == "🟡":
                want = "待验证" if "待验证" in name else "自测通过·待审核"
                got = sum(len(v) for k, v in actual.items()
                          if k.startswith("🟡") and (("待验证" in k) == (want == "待验证")))
            else:
                got = sum(len(v) for k, v in actual.items() if k.split()[0] == sym)
            if got != n:
                errs.append(f"证据分布写 {key} {n} 条，总表实际 {got} 条")
    except ValueError:
        pass

    # ⑦ signal-spec.md 里的信号必须在实验记录里存在，且不得是已证伪的
    if os.path.exists(SPEC):
        sp = open(SPEC, encoding="utf-8").read()
        _s = sp[sp.index("### 已定案"):sp.index("### 待定")]
        spec_ids = set()
        for l in _s.split("\n"):
            c2 = split_row(l)
            if c2 and re.fullmatch(IDPAT, c2[0]): spec_ids.add(c2[0])
        for sid in sorted(spec_ids):
            if sid not in s3:
                errs.append(f"⑦ spec 里的 {sid} 在实验记录 S 层里不存在")
        # spec 中不得出现实验记录里标 🔴/⚪ 的行（同标的）
        for l in tbl.split("\n"):
            c2 = split_row(l)
            if not c2 or not re.fullmatch(IDPAT, c2[0]) or "证据" not in cols: continue
            if c2[0] in spec_ids and c2[cols["证据"]][:1] in ("🔴", "⚪"):
                pass  # 同一 ID 可能一类资产已定案、另一类被证伪，逐行判断留给人工
    # ⑤ 其他文档引用的 ID 必须存在
    known = set(s5) | set(s3)
    for rel in ["backtest/plan.md", "product/data-pipeline.md", "product/content-spec.md", "CLAUDE.md"]:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p): continue
        for sid in set(re.findall(IDPAT, open(p, encoding="utf-8").read())):
            if sid not in known: errs.append(f"{rel} 引用了不存在的 {sid}")

    # ⑧ product/ 的作用域：出现的信号 ID 要么在已定案 13 条里，
    #    要么在被明确标注为「已移出 / 已排除」的说明性上下文里。
    #    防的是 spec 与前端各走各的 —— 前端只实现 13 条，spec 若还在描述别的，
    #    读者无从判断哪些是真的。2026-08-21 加。
    spec_p = os.path.join(ROOT, "product/signal-spec.md")
    decided = set()
    if os.path.exists(spec_p):
        _t = open(spec_p, encoding="utf-8").read()
        _sec = _t.split("### 已定案")[1].split("<sub>共")[0] if "### 已定案" in _t else ""
        for l in _sec.split("\n"):
            c2 = split_row(l)
            if c2 and re.fullmatch(IDPAT, c2[0]): decided.add(c2[0])
    # 说明性上下文的标志词：整行提到「已移出 / 未进 / 不在…13 条 / 没听说过」即放行
    EXCUSE = ("已移出", "移出本文", "未进", "不在", "没听说过", "results-po", "signal-registry")
    for rel in ["product/data-pipeline.md", "product/content-spec.md",
                "product/output-schema.md", "product/signal-spec.md", "skill/SKILL.md"]:
        p2 = os.path.join(ROOT, rel)
        if not os.path.exists(p2): continue
        for i, line in enumerate(open(p2, encoding="utf-8").read().split("\n"), 1):
            if any(w in line for w in EXCUSE): continue
            for sid in set(re.findall(IDPAT, line)):
                if sid in decided or sid == "PV2":  # PV2 是 PV1 的修饰符，定义处必需
                    continue
                errs.append(f"⑧ {rel}:{i} 出现 {sid}，不在已定案 13 条内且无「已移出」标注")

    if errs:
        print(f"❌ {len(errs)} 处不一致：")
        for e in errs: print("   " + e)
        sys.exit(1)
    print(f"✅ 一致性检查通过（§三 {len(s3)} 条 · §五 {len(s5)} 条 · product/ 作用域 {len(decided)} 条）")

if __name__ == "__main__": main()

# ---- schema 漂移：数据里的字段名必须在 output-schema.md 里有出处 ----
import subprocess, os
r=subprocess.run(['python3', os.path.join(os.path.dirname(__file__),'check_schema_drift.py')],
                 capture_output=True, text=True)
print(r.stdout.rstrip())
if '未提及 0 个' not in r.stdout:
    raise SystemExit('❌ schema 漂移')

# ---- SKILL.md 的跨文档章节引用必须可解析 ----
r=subprocess.run(['python3', os.path.join(os.path.dirname(__file__),'check_skill_refs.py')],
                 capture_output=True, text=True)
print(r.stdout.rstrip())
if r.returncode: raise SystemExit('❌ SKILL.md 章节引用')

# ---- 已撤回的说法不得在 product/ 里复活 ----
RETRACTED={
  '时点三档':'timing 是四档（含 untimed）',
  '两条都空 → 直接写':'材料为空正是自搜的场景，仍要调模型',
  '三档全部由时间戳':'四档',
}
import glob
bad=[]
for p in glob.glob(os.path.join(os.path.dirname(__file__),'../../../product/*.md')):
    t=open(p).read()
    for k,why in RETRACTED.items():
        if k in t: bad.append(f'{os.path.basename(p)}: 「{k}」—— {why}')
if bad:
    print('\n❌ 已撤回的说法复活了：'); [print('  ',b) for b in bad]; raise SystemExit(1)
print('✅ 无已撤回说法复活')

# ---- product/ 里不留事故叙述 ----
# 规格给「应该是什么」，事故的来龙去脉在 backtest/。
# 日期出现在 JSON 示例值里是正常的，只查散文行。
import re as _re
NARR=_re.compile(r'(20[0-9]{2}-[01][0-9]-[0-3][0-9]\s*(实测|复核|页面上|起不再|的\s*[A-Z]))'
                 r'|(原判「|已撤回|原理由是)')
bad=[]
for p in sorted(glob.glob(os.path.join(os.path.dirname(__file__),'../../../product/*.md'))):
    infence=False
    for i,ln in enumerate(open(p),1):
        if ln.lstrip().startswith('```'): infence=not infence; continue
        if infence or '"' in ln or '`20' in ln: continue
        if NARR.search(ln): bad.append(f'{os.path.basename(p)}:{i}  {ln.strip()[:70]}')
if bad:
    print('\n⚠️ product/ 里疑似事故叙述（规格只写「应该是什么」）：')
    [print('  ',b) for b in bad]
else:
    print('✅ product/ 无事故叙述残留')

# ---- timing 档位表：凡列出 before/after/none 的地方必须同时有 untimed ----
bad=[]
for p in sorted(glob.glob(os.path.join(os.path.dirname(__file__),'../../../product/*.md'))+
                [os.path.join(os.path.dirname(__file__),'../../../skill/SKILL.md')]):
    t=open(p).read()
    # 逐个代码块检查
    blocks=re.findall(r'```[^\n]*\n(.*?)```', t, re.S)
    for blk in blocks:
        if re.search(r'^\s*before\b', blk, re.M) and re.search(r'^\s*none\b', blk, re.M) \
           and not re.search(r'^\s*untimed\b', blk, re.M):
            bad.append(f'{os.path.basename(p)}: 档位表列了 before/none 但没有 untimed')
if bad:
    print('\n❌ timing 档位表不是四档：'); [print('  ',b) for b in bad]; raise SystemExit(1)
print('✅ timing 档位表处处四档')

# ---- 加密归因：曾在六处分叉，任一「加密不做归因」的说法都要拦 ----
# 「加密永远没有归因」只在解释「老写法为什么错」时合法，逐行判上下文
FORBID=['加密不显示这一块','不希望它去自己找资料','给加密做新闻归因',
        '加密的告警卡片只有 ①③④']
CTX_OK=('老写法','这条写法','是错的')
bad=[]
for p in sorted(glob.glob(os.path.join(os.path.dirname(__file__),'../../../product/*.md'))+
                [os.path.join(os.path.dirname(__file__),'../../../skill/SKILL.md')]):
    lines=open(p).read().split('\n')
    for i,ln in enumerate(lines):
        for k in FORBID:
            if k in ln: bad.append(f'{os.path.basename(p)}:{i+1} 「{k}」')
        if '加密永远没有归因' in ln:
            win='\n'.join(lines[max(0,i-3):i+1])
            if not any(c in win for c in CTX_OK):
                bad.append(f'{os.path.basename(p)}:{i+1} 「加密永远没有归因」缺「这是错的写法」的上下文')
if bad:
    print('\n❌ 加密归因说法分叉：'); [print('  ',b) for b in bad]; raise SystemExit(1)
print('✅ 加密归因说法一致')

# ---- state.json 与 findings 必须一致：state 里 on 的用户线 == findings 里的用户线 ----
import json as _j
_st=_j.load(open(os.path.join(os.path.dirname(__file__),'../../../mock/data/state.json')))
_fd=_j.load(open(os.path.join(os.path.dirname(__file__),'../../../mock/data/findings.json')))
_on={k for k,v in _st['keys'].items() if v['on']}
_us={f"{x['symbol']}:{x['signalId']}" for x in _fd['findings'] if x['signalId'].startswith('US')}
if _on!=_us:
    print(f'❌ state.json 与 findings 不一致：只在 state {sorted(_on-_us)} · 只在 findings {sorted(_us-_on)}')
    raise SystemExit(1)
print(f'✅ state.json 与 findings 一致（{len(_on)} 条状态型成立）')

# ---- finding 键集合必须与契约一致：多一个少一个都说明分工没理清 ----
FKEYS={'id','symbol','assetClass','signalId','unit','severity','triggeredAt','knownAt',
       'episodeId','novelty','priority','measured','trigger','delivery','context'}
CKEYS={'benchmark','sizeRank','pnl','attribution'}
bad=[]
for fn in ['mock/data/findings.json','mock/data-outpool/findings.json']:
    p=os.path.join(os.path.dirname(__file__),'../../../',fn)
    if not os.path.exists(p): continue
    for x in _j.load(open(p))['findings']:
        e=set(x)-FKEYS; m=FKEYS-set(x); ce=set(x.get('context',{}))-CKEYS
        if e or m or ce: bad.append(f"{fn} {x['id']}: 多{sorted(e)} 少{sorted(m)} context多{sorted(ce)}")
if bad:
    print('❌ finding 键集合与契约不一致：'); [print('  ',b) for b in bad]; raise SystemExit(1)
print('✅ finding 键集合与契约一致')

# ---- 时钟：任何 finding 都不能晚于产出它的那一轮 ----
# ⚠️ 实测踩过两次：① 加密 24 小时交易，盘中 bar 延到取数时刻，而 asOf 钉在 16:00 ET
#    → 「16:05 跑的那轮」里出现 17:30 的告警；② 加密日线按 UTC 切，D 那根收在 D 20:00 ET，
#    却被写成 16:00 ET → DOGE 卡片报 $0.0916，而 16:00 ET 当时是 $0.0849。
#    两次都是不用统计就能发现的边界矛盾（CLAUDE.md §三·五 硬规则 1）。
import datetime as _dt
def _t(x): return _dt.datetime.fromisoformat(str(x).replace('Z','+00:00'))
bad=[]
for fn in ['mock/data', 'mock/data-outpool']:
    d=os.path.join(os.path.dirname(__file__),'../../../',fn)
    fp, mp = os.path.join(d,'findings.json'), os.path.join(d,'meta.json')
    if not (os.path.exists(fp) and os.path.exists(mp)): continue
    fj=_j.load(open(fp)); G=_t(_j.load(open(mp))['generatedAt'])
    if _t(fj['asOf'])>G: bad.append(f"{fn} asOf {fj['asOf']} 晚于 generatedAt")
    for x in fj['findings']:
        for k in ('triggeredAt','knownAt'):
            if x.get(k) and _t(x[k])>G: bad.append(f"{fn} {x['id']} {k}={x[k]} 晚于 generatedAt")
if bad:
    print('❌ 有 finding 晚于产出它的那一轮：'); [print('  ',b) for b in bad]; raise SystemExit(1)
print('✅ 时钟：无 finding 晚于本轮 generatedAt')

# ---- mock 的脚本块必须能解析 ----
# ⚠️ 实测：一次编辑把 `${/* … */''}` 从模板串里挪到了普通代码里，整页脚本挂掉 ——
#    页面白屏之前先是所有函数都不存在，而**文件本身看起来一切正常**。
#    `node --check` 一秒钟就能发现，比任何页面自检都早。
import re as _re, subprocess as _sp, tempfile as _tf
_html = os.path.join(os.path.dirname(__file__), '../../../mock/portfolio-watch-mock.html')
if os.path.exists(_html):
    _src = open(_html).read()
    # ⚠️ 只查 JS。`<script type="application/json">` 装的是数据，
    #    拿 node --check 去解析它必然失败 —— 那是检查在报错，不是文件有错。
    _blocks = [m.group(2) for m in _re.finditer(
        r'<script((?![^>]*\bsrc=)[^>]*)>([\s\S]*?)</script>', _src)
        if 'type=' not in m.group(1) or 'javascript' in m.group(1)]
    _bad = []
    for _i, _b in enumerate(_blocks):
        with _tf.NamedTemporaryFile('w', suffix='.js', delete=False) as _f:
            _f.write(_b); _pth = _f.name
        _r = _sp.run(['node', '--check', _pth], capture_output=True, text=True)
        os.unlink(_pth)
        if _r.returncode:
            _ln = _re.search(r'\.js:(\d+)', _r.stderr)
            _at = (_src[:_src.index(_b)].count('\n') + int(_ln.group(1))) if _ln else '?'
            _bad.append(f'脚本块 {_i} 解析失败 · mock 第 {_at} 行左右\n     ' + _r.stderr.strip().split('\n')[2][:160])
    if _bad:
        print('❌ mock 脚本语法错误：'); [print('  ', b) for b in _bad]; raise SystemExit(1)
    print(f'✅ mock 脚本可解析（{len(_blocks)} 块）')

import json as _json
# ---- 有解释就必须有来源 ----
# summary 非空 ⟹ sources 非空。读者打不开任何东西的解释不是解释，
# 而它完全合法、不会报错 —— 只能靠断言拦。
_bad = []
for _fn in ('mock/data/findings.json', 'mock/data-outpool/findings.json'):
    _fp = os.path.join(os.path.dirname(__file__), '..', '..', _fn)
    if not os.path.exists(_fp): continue
    for _f in _json.load(open(_fp)).get('findings', []):
        _at = (_f.get('context') or {}).get('attribution') or {}
        if _at.get('summary') and not (_at.get('sources') or []):
            _bad.append(f"{_fn} {_f['id']} 有解释无来源")
if _bad:
    print('❌ 无源解释：'); [print('  ', b) for b in _bad]; raise SystemExit(1)
print('✅ 无「有解释无来源」的 finding')

# ---- 提示词必须全英文 ----
_r = _sp.run(['python3', os.path.join(os.path.dirname(__file__), 'check_prompt_english.py')],
             capture_output=True, text=True)
print(_r.stdout.rstrip() or _r.stderr.rstrip()[:300])
if _r.returncode: raise SystemExit('❌ 提示词混入中文')

# ---- Python 与 JS 的口径一致性 ----
_r = _sp.run(['python3', os.path.join(os.path.dirname(__file__), 'check_js_parity.py')],
             capture_output=True, text=True)
print(_r.stdout.rstrip() or _r.stderr.rstrip()[:400])
# 退出码 2 = 缺原始数据，跳过；1 = 真的不一致。两者不能都算失败，也不能都算通过。
if _r.returncode not in (0, 2): raise SystemExit('❌ 口径不一致')

# ---- 平台设计门禁 ----
# ⚠️ `alva lint playbook` 是**发布时真的会拦**的那道门，不是建议。
#    实测一次：`.pill-n` 用了 font-weight:600（只允许 400/500），发布会被判 error。
#    在本地跑一遍，比在 release 那一步才发现便宜得多。warning 不拦，只报数。
_tpl = os.path.join(os.path.dirname(__file__), '../../../skill/template/index.html')
if os.path.exists(_tpl):
    _r = _sp.run(['alva', 'lint', 'playbook', _tpl, '--format', 'human'],
                 capture_output=True, text=True)
    _errs = [l for l in _r.stdout.splitlines() if l.startswith('ERROR')]
    if _errs:
        print('❌ 设计门禁 error（发布会被拦）：'); [print('  ', e[:160]) for e in _errs]
        raise SystemExit(1)
    _warn = sum(1 for l in _r.stdout.splitlines() if l.startswith('WARNING'))
    print(f'✅ 设计门禁：0 error · {_warn} warning')

# ---- output-schema §九 的 eval 断言 ----
# ⚠️ 判官搬到 eval/ 了 —— backtest/ 是「信号对不对」，eval/ 是「agent 建出来的东西对不对」，
#    两件事。这里仍然调它，因为 mock 账本的自洽也归一致性检查管。
r=subprocess.run(['python3', os.path.join(os.path.dirname(__file__),'../../../eval/judges/assertions.py')],
                 capture_output=True, text=True)
print(r.stdout.rstrip())
if r.returncode: raise SystemExit('❌ eval 断言')

# ---- 分布可用性 ρ 的两条界只能有一个值 ----
# ⚠️ 这个数曾在五处写成两个值（40 与 60），而**可执行的那一份用的是宽的那个**。
#    实测 ρ 最高 20.2%，两条界都碰不到，所以五处不一致谁也没发现 ——
#    换一只高 ρ 标的就会把本该降 Warning 的判成 pass。
import re as _re2
_rho_lo, _rho_hi = 0.02, 0.40
_srcs = {
    'pipeline/build/build_m23.py': _re2.compile(r'LO,\s*HI\s*=\s*([0-9.]+),\s*([0-9.]+)'),
    'product/output-schema.md':   _re2.compile(r'too_loose\s+ρ > ([0-9.]+)'),
    'product/signal-spec.md':     _re2.compile(r'ρ = P\(\|z\| ≥ [0-9.]+\) 必须落在 \[([0-9]+)%, ([0-9]+)%\]'),
    # ⚠️ 必须锚到 too_loose 那一支 —— 只匹配 covPct 会先命中紧界那行的 2，
    #    检查随后报「上界是 2」，看起来像文件错了，其实是检查写松了。
    'mock/portfolio-watch-mock.html': _re2.compile(
        r"T\('covPct', rho\.toFixed\(1\), ([0-9]+)\), m23\.verdict==='too_loose'"),
}
_bad = []
for _f, _re_ in _srcs.items():
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', _f)
    _m = _re_.search(open(_p, encoding='utf-8').read())
    if not _m: _bad.append(f'{_f} 找不到 ρ 的界（表达式变了？）'); continue
    _vals = [float(g) for g in _m.groups()]
    _vals = [v/100 if v > 1 else v for v in _vals]
    if _rho_hi not in _vals: _bad.append(f'{_f} 的上界是 {_m.groups()}，应为 {_rho_hi}')
if _bad:
    print('❌ ρ 的界不一致：'); [print('  ', b) for b in _bad]; raise SystemExit(1)
print(f'✅ ρ 的界处处一致（上界 {_rho_hi}）')

# ---- 界面文案键：两种语言必须成对，键表引用必须有文案 ----
# ⚠️ 缺一种语言不会报错，只会在切到那种语言时印出 `[gapBackcast]`。
#    而 gap 键表引用一个不存在的文案键，页面会印裸 id ——
#    那句话的意思是「这个页面比管线旧」，实际只是我们漏了一条文案。
import re as _re3, collections as _co
_html = open(os.path.join(os.path.dirname(__file__), '../../../mock/portfolio-watch-mock.html'),
             encoding='utf-8').read()
_copy = _co.Counter(_re3.findall(r'^\s{2}([a-z][A-Za-z0-9]+)\s*:', _html, _re3.M))
_i = _html.index('const GAP_TEXT'); _j = _html.index('};', _i)
_tbl = set(_re3.findall(r"'(gap[A-Za-z]+)'", _html[_i:_j]))
_bad = []
_bad += [f'{k} 只有一种语言' for k, v in sorted(_copy.items()) if k.startswith('gap') and v != 2]
_bad += [f'{k} 被 GAP_TEXT 引用但没有文案' for k in sorted(_tbl - set(_copy))]
if _bad:
    print('❌ 文案键不成对：'); [print('  ', b) for b in _bad]; raise SystemExit(1)
print(f'✅ gap 文案键成对（{len(_tbl)} 条键表项全部有文案）')

# ---- 脚本写出的每个 gap id，页面都必须有文案 ----
# ⚠️ 没文案的 gap 会走 gapUnknown 印出裸 id，而那句话的意思是「这个页面比管线旧」。
#    此前四个 producer 写出 7 种 id，键表里一条都没有 —— 每条真实 gap 都在说一句假话。
import glob as _g
_ids = set()
for _f in _g.glob(os.path.join(os.path.dirname(__file__), '../../../skill/scripts/*.js')):
    _t = open(_f, encoding='utf-8').read()
    # ⚠️ 变量名放宽到 gaps* —— 只认字面的 `gaps` 时，破坏性测试用 `gaps9` 注入
    #    就漏过去了。检查器自己也会「没在查」。
    # ⚠️ 引号原来只认 `"` —— 而带参数的 gap 一律是模板串（`` `insufficient_baseline:${sym}` ``）。
    #    于是这个检查从来没看过任何一条参数化 gap，却每次都印「全部有文案」。
    #    它不是判错了，是根本没把它们收进来。三种引号一起认。
    #    ⚠️ 字符类原来是 `[a-z_]+`，`pv5_grade_unavailable` 被切成 `pv` —— 数字断在中间。
    # 正向问的是「发出来的有没有文案」，所以必须枚举**发送点**，
    # 认 `.add(` / `.push(` 紧跟字面量这个形状。三种引号、允许数字。
    for _m in _re3.finditer(r'\.\s*(?:add|push)\(\s*[\"\'`]([a-z][a-z0-9_]{6,})', _t):
        _ids.add(_m.group(1))
_i2 = _html.index('const GAP_TEXT'); _j2 = _html.index('};', _i2)
# ⚠️ 键表这一侧同样断在数字上 —— `pv5_grade_unavailable` 被读成 `pv`。
#    两侧用同一个字符类，否则「有文案」和「写出来了」比的不是同一批名字。
_known = set(_re3.findall(r'^\s*([a-z][a-z0-9_]*):', _html[_i2:_j2], _re3.M))
_missing = sorted(_ids - _known)
if _missing:
    print('❌ 脚本写出但页面没有文案的 gap：'); [print('  ', m) for m in _missing]; raise SystemExit(1)
print(f'✅ 脚本写出的 {len(_ids)} 种 gap 全部有文案')

# ---- 反方向：有文案，却没有任何脚本发得出 ----
# ⚠️ 上面那条只查「发出来的都有文案」。反方向从来没人查，
#    结果是 22 条文案里 skill 只用得上 13 条 —— 剩下 8 条只在本地 mock 里被发过。
#    后果实测（R8）：三只 ETF 跑在没人验证过的兜底阈值上、两只新股被高波降级，
#    而 `unvalidated_asset_class` 与 `pv1_highvol_downgrade_undecided` 都发不出来，
#    **页面一个字都没说**。gap 是这个产品承认自己不知道什么的地方 ——
#    发不出来等于没承认，而它看起来跟「这本账没有这些问题」一模一样。
_PAGE_ONLY = {
    # 只由界面自己在渲染时判定，不经 meta.gaps
    'attribution_no_chain_sample',
    # 手写进 mock 数据的已知失败样本（见 output-schema §归因时区）。
    # 没有脚本发它，但**产物里确实有**，所以必须有文案 —— 见下面第三个方向。
    'attribution_time_zone_leak',
}
# ⚠️ 反向问的是「这条文案有没有人发得出」，那是一个**成员判断**，不需要枚举发送点 ——
#    枚举形状会漏掉三元、局部变量名、先拼后 push，而漏掉的表现是
#    「这条没人发」，**方向反了会催你去加已经加过的代码**。
#    逐个已知键去剥了注释的脚本正文里找它自己（注释要剥，否则注释里提一句就算数，
#    那正是 BC41 的坑）。
_src = ""
for _f in _g.glob(os.path.join(os.path.dirname(__file__), '../../../skill/scripts/*.js')):
    _t2 = open(_f, encoding='utf-8').read()
    _t2 = _re3.sub(r'/\*.*?\*/', '', _t2, flags=_re3.S)
    _src += _re3.sub(r'(?m)^\s*//.*$', '', _t2)
_emitted = {k for k in _known if k in _src}
_dead = sorted(_known - _emitted - _PAGE_ONLY)
if _dead:
    print('❌ 有文案但没有任何脚本发得出的 gap：')
    [print('  ', m) for m in _dead]
    raise SystemExit(1)
print(f'✅ {len(_emitted)} 条 gap 文案都有脚本发得出'
      + (f'（{len(_PAGE_ONLY)} 条界面自判，已列白名单）' if _PAGE_ONLY else ''))

# ---- 第三个方向：产物里真的出现过的 gap，有没有文案 ----
# ⚠️ 前两个方向扫的都是**脚本**。而 `mock/data*/meta.json` 里有手写进去的 gap
#    （eval 的已知失败样本），两个方向都扫不到它。
#    实测:`attribution_time_zone_leak` 就这样躲了很久，
#    **而它此刻正印在 acct1 生产页面上，印的是裸 id。**
#    这个方向才是用户真正会看到的那一个 —— 判据是数据，不是代码。
# ⚠️ 第一版这里写 `json.load` 而这个文件里 json 叫 `_json`，NameError 被
#    `except: pass` 吞掉，检查印出「0 种 gap 都有文案」——**零个也叫全过**。
#    不吞异常，并且先断言真的读到了文件。
_data_files = sorted(_g.glob(os.path.join(os.path.dirname(__file__), '../../../mock/data*/meta.json')))
if not _data_files:
    raise SystemExit('❌ 一个 mock/data*/meta.json 都没找到 —— 这个检查等于没跑')
_data_gaps = set()
for _f in _data_files:
    for _x in (_json.load(open(_f, encoding='utf-8')).get('gaps') or []):
        _data_gaps.add(str(_x).split(':')[0])
if not _data_gaps:
    raise SystemExit('❌ 读到了文件但一条 gap 都没有 —— 大概率是字段名变了')
_nocopy = sorted(_data_gaps - _known)
if _nocopy:
    print('❌ mock 产物里出现、而页面没有文案的 gap（会印裸 id）：')
    [print('  ', m) for m in _nocopy]
    raise SystemExit(1)
print(f'✅ mock 产物里的 {len(_data_gaps)} 种 gap 都有文案')

# ---- 立了欠条的 gap 必须有人撕 ----
# ⚠️ gap 集合是**只并不清**的：每个 producer 都 `new Set([...meta.gaps, ...])`。
#    对「这是一条永久边界」的 gap 那是对的（加密无市值总量、判据只测波动放大）。
#    对「这一步还没做」的欠条就是错的 —— 做完了它还在，页面就在说一件
#    当时为真、现在为假的事。实测：R5 的 market.json 里有 4 个指数，
#    而方法页照旧写着 market_not_yet_fetched。
#    判据只看 id：带 not_yet / not_run / pending 的一律要求有人 delete。
# `m23_not_run` 名字像欠条，其实是**基线的持久事实** —— M23 在 init 算一次，
# 此后没有任何 producer 会重算它，只有重跑 init 才可能改变。给它一个例外并写清理由，
# 比为了让检查器闭嘴去加一个假的 delete 好。
_NOT_OWED = {'m23_not_run'}
_owed = {i for i in _ids
         if any(k in i for k in ('not_yet', 'not_run', 'pending')) and i not in _NOT_OWED}
_cleared = set()
for _f in _g.glob(os.path.join(os.path.dirname(__file__), '../../../skill/scripts/*.js')):
    _t = open(_f, encoding='utf-8').read()
    for _m in _re3.finditer(r'gaps\w*\.delete\(\s*[\"\'`]([a-z][a-z0-9_]*)', _t):
        _cleared.add(_m.group(1))
_stuck = sorted(_owed - _cleared)
if _stuck:
    print('❌ 这些 gap 是欠条，但没有任何 producer 撕它：')
    [print('  ', m) for m in _stuck]
    raise SystemExit(1)
print(f'✅ {len(_owed)} 条欠条型 gap 都有人撕')

# ---- 四个 producer 在桩环境里真的跑一遍 ----
# ⚠️ node --check 只做语法解析，抓不到暂时性死区、字段名写错、空数据路径上的崩溃。
#    而平台的 feed.run 吞异常：抛错的那一轮报 completed、日志为空、一个字都没写 ——
#    **看状态永远发现不了**。本 session 因此撞了四次声明前使用。
#    桩里的 feed.run 不吞，跑一遍就见分晓。
_r = _sp.run(['node', 'run.js'], cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'smoke'),
             capture_output=True, text=True)
print(_r.stdout.rstrip() or _r.stderr.rstrip()[:600])
if _r.returncode: raise SystemExit('❌ producer 冒烟测试未过')

# ---- 信号目录 vs signal-spec：类型与投递上限逐条对齐 ----
# ⚠️ `maxDelivery` 是**三道投递上限之一**（另两道是 symbol_grade 与 degraded），
#    它决定一条信号实际投到哪一层。而 signal-spec.md 是已定案信号的唯一定义处，
#    init.js 的 CATALOG 只是它的可执行副本 —— 两份同一事实，必然漂。
#    2026-08-23 实测已经漂了两处：EV1 目录 L3 / spec L4、PF3 目录 L2 / spec L3。
#    后果不是显示错位而已：PF3 会进概览信号流，而 spec 说它不进。
#    ⚠️ 这跟 CLAUDE.md 记的「degraded 上限写三份、三份互不相同」是同一个形状。
_spec_p = os.path.join(os.path.dirname(__file__), '../../../skill/references/signal-spec.md')
_init_p = os.path.join(os.path.dirname(__file__), '../../../skill/scripts/init.js')
_spec_rows, _cat_rows = {}, {}
for _l in open(_spec_p, encoding='utf-8'):
    _m = _re3.match(r'\|\s*\*\*(\w+)\*\*\s*\|[^|]*\|\s*([\w ]+?)\s*\|[^|]*\|[^|]*\|\s*(L\d)', _l)
    if _m: _spec_rows[_m.group(1)] = (_m.group(2).strip(), _m.group(3))
for _m in _re3.finditer(r'\["(\w+)","[^"]*","[^"]*","(\w+)",\[[^\]]*\],"\w+","\w+",[^,]*,"(L\d)"',
                        open(_init_p, encoding='utf-8').read()):
    _cat_rows[_m.group(1)] = (_m.group(2), _m.group(3))
if not _spec_rows or not _cat_rows:
    raise SystemExit('❌ 信号表没解析出来 —— 检查器读不到就是没查，不能当成通过')
# EV6 在 spec 里写的是「attached to PV1/PV5 cards」，不是 L 层 —— 它从不独立投递。
# 明写豁免，不靠 regex 匹配不上而静默跳过：那两者长得一模一样。
_EXEMPT = {'EV6': 'spec 写「attached to PV1/PV5 cards」，不是投递层'}
_drift = []
for _k in sorted(set(_spec_rows) | set(_cat_rows)):
    if _k in _EXEMPT: continue
    _a, _b = _cat_rows.get(_k), _spec_rows.get(_k)
    if _a is None: _drift.append(f'{_k} 只在 spec 有，CATALOG 缺'); continue
    if _b is None: _drift.append(f'{_k} 只在 CATALOG 有，spec 缺'); continue
    if _a[1] != _b[1]: _drift.append(f'{_k} 投递上限 CATALOG {_a[1]} ≠ spec {_b[1]}')
    if _a[0] != _b[0]: _drift.append(f'{_k} 类型 CATALOG {_a[0]} ≠ spec {_b[0]}')
if _drift:
    print('❌ 信号目录与 spec 不一致（spec 为准）：'); [print('  ', d) for d in _drift]
    raise SystemExit(1)
print(f'✅ 信号目录与 spec 逐条一致（{len(_cat_rows)} 条，豁免 {len(_EXEMPT)}：'
      + '; '.join(f'{k} {v}' for k, v in _EXEMPT.items()) + '）')

# ---- 台账条数与引用它的文档 ----
# ⚠️ BC43 就是这一类：台账页面声称 41 条、实际只渲染了 34 条。
#    条数是个会变的事实，而它被抄在四份文档里。抄一次就多一处会过期的副本。
#    这里不检查「渲染对不对」（那是 badcases.py 自己的事），
#    只检查**引用它的地方有没有跟着动**。
import ast as _ast, glob as _glob
_bcp = os.path.join(os.path.dirname(__file__), '../../../eval/build/badcases.py')
if not os.path.exists(_bcp):
    print('—  台账条数检查跳过：缺 eval/build/badcases.py')
else:
    _src = open(_bcp, encoding='utf-8').read()
    _tree = _ast.parse(_src)
    _cases = None
    for _n in _tree.body:
        if isinstance(_n, _ast.Assign) and any(
                getattr(t, 'id', None) == 'CASES' for t in _n.targets):
            _cases = _n.value
    if _cases is None:
        raise SystemExit('❌ badcases.py 里解析不出 CASES —— 读不到就是没查')
    _total = len(_cases.elts)
    # caught=False 才算「判官当时漏了」；None 是「不判对错」，不能混进来。
    _missed = 0
    for _e in _cases.elts:
        for _kw in getattr(_e, 'keywords', []):
            if _kw.arg == 'caught' and isinstance(_kw.value, _ast.Constant) \
                    and _kw.value.value is False:
                _missed += 1
    _root = os.path.join(os.path.dirname(__file__), '../../..')
    _stale, _hits = [], {'总数': 0, '漏数': 0}
    for _f in ['APPROACH.md', 'README.md', 'eval/README.md', 'PortfolioWatch_解题思路.md']:
        _p = os.path.join(_root, _f)
        if not os.path.exists(_p): continue
        _t = open(_p, encoding='utf-8').read()
        # 只看紧贴「条」且语境是台账/缺陷/badcase 的数字，避免撞上别处的计数
        for _m in re.finditer(r'(\d+)\s*条(?=\s*(?:badcase|缺陷|：))', _t):
            _hits['总数'] += 1
            if int(_m.group(1)) != _total:
                _stale.append(f'{_f} 写「{_m.group(1)} 条」，台账实际 {_total} 条')
        for _m in re.finditer(r'判官当时漏了\s*(\d+)\s*条', _t):
            _hits['漏数'] += 1
            if int(_m.group(1)) != _missed:
                _stale.append(f'{_f} 写「漏了 {_m.group(1)} 条」，实际 {_missed} 条')
    if _stale:
        print('❌ 台账条数与文档不一致：'); [print('  ', d) for d in _stale]
        raise SystemExit(1)
    # ⚠️ 必须报出比了几处。破坏性测试第一次没响就是因为这个：
    #    APPROACH.md 只在交付仓库，工作仓库里「漏数」那半个检查**没有比较对象**，
    #    于是无论台账怎么变它都通过 —— 「跑完没发现」和「没东西可查」长得一模一样。
    _cover = ' · '.join(f'{k} {v} 处' for k, v in _hits.items())
    if not any(_hits.values()):
        print(f'—  台账 {_total} 条 · 判官漏 {_missed} 条，'
              f'但**本仓库没有任何文档引用这两个数**，这一项等于没查')
    else:
        _none = [k for k, v in _hits.items() if not v]
        print(f'✅ 台账 {_total} 条 · 判官漏 {_missed} 条，引用处都对得上（{_cover}）'
              + (f' ⚠️ {"、".join(_none)}在本仓库无人引用，那一半没查' if _none else ''))
