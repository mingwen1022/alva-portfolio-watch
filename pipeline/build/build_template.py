# -*- coding: utf-8 -*-
"""从 mock 产出 skill/template/index.html。

⚠️ 存在理由：交付物必须是**可重跑产出**，不是手工另存一份。
   mock 每改一次，template 手工同步一次 —— 那两份必然分家，
   而分家的表现是「按 skill 建出来的页面和我们验过的那个不一样」。

模板与 mock 的差别只有两处，都是**减法**：
  ① 去掉 mock 自述块（#w-disc）—— 「这是探索工具、不是规格来源」那段
     以及它里面的 demo 切换器。真实 Playbook 只有一本账，切换器指向的
     data-outpool / data-us 等目录并不存在。
  ② 页面标题换掉。

其余一个字不动 —— 数据全部来自 fetch，换一份 JSON 就是另一个组合的页面。
"""
import re, os, sys

SRC = 'mock/portfolio-watch-mock.html'
DST = 'skill/template/index.html'
s = open(SRC).read()
lines = s.split('\n')

# ── ① 定位 #w-disc 整块，按「同级 div 配平」找结束，不用 index 找分隔符 ──
#    ⚠️ CLAUDE.md 硬规则：区段编辑禁止用 s.index 找结束位 —— 分隔符会跨节匹配。
try:
    start = next(i for i, l in enumerate(lines) if 'id="w-disc"' in l)
except StopIteration:
    sys.exit('❌ 找不到 #w-disc —— mock 的结构变了，先看清楚再改这里')
depth = 0
end = None
for i in range(start, len(lines)):
    depth += len(re.findall(r'<div\b', lines[i])) - len(re.findall(r'</div>', lines[i]))
    if i > start and depth <= 0:
        end = i
        break
if end is None:
    sys.exit('❌ #w-disc 没有配平的结束标签')
removed = end - start + 1
if not (100 <= removed <= 200):
    sys.exit(f'❌ 要删的块是 {removed} 行，超出预期区间 —— 停下来看看删的是不是它')

out = lines[:start] + lines[end + 1:]

# ── ② 标题 ──
txt = '\n'.join(out)
txt = txt.replace('<title>Portfolio Watch — Page 1 Mock</title>',
                  '<title>Portfolio Watch</title>')

# ⚠️ 发布用的模板要带 ALFS 根 —— 相对路径在网关托管下读不到，实测整页 404。
#    留空则是本地预览。真流程里这一步由建 playbook 的 agent 填成它自己的目录。
ROOT_ARG = os.environ.get('ALFS_ROOT')
if ROOT_ARG:
    old_cfg = '<script type="application/json" id="playbook-config">{"alfsRoot": null}</script>'
    assert old_cfg in txt, '找不到 playbook-config 块'
    txt = txt.replace(old_cfg,
        f'<script type="application/json" id="playbook-config">{{"alfsRoot": "{ROOT_ARG}"}}</script>', 1)

os.makedirs(os.path.dirname(DST), exist_ok=True)
# ⚠️ 这里**不写盘**。此前先写一次、再做后续删改、中途 sys.exit ——
#    任何一次失败都把半成品留在 skill/template/index.html 上，而 bundle.py 照打不误。
#    全程在内存里改，最后一次性写。

# ── ③ demo 残留：账本切换器与写死日期 ──
#    交付模板里 STATE.book 一次都不会被赋值（切换器已删），所以 BOOK_FILTER / BOOK_ROOT
#    永远走 'all' 那一支；fid / iso 声明了但零处调用，却带着写死的 2026-08-21。
#    留着不会出错，但它们是 agent 会误以为「需要我改」的东西，
#    而一个写死的日期出现在交付物里读起来就是个 bug。
# ⚠️ SINGLE_SYM 不在这张表里 —— 它由下面整块替换掉。
#    放进来会让它先被删，后面找不到它，整块替换静默失败。
_DEMO_CONSTS = [
    r"^const DAY='[^']*';\n",
    r"^const fid=\(sym,sig\)=>[^\n]*\n",
    r"^const iso=t=>[^\n]*\n",
]
_removed = 0
for _pat in _DEMO_CONSTS:
    txt, _n = re.subn(_pat, '', txt, flags=re.M)
    _removed += _n
# 账本切换机制整套替换。交付模板里 STATE.book 一次都不会被赋值，
# 所以它只会走 'all' 那一支；留着 SINGLE_SYM='NVDA' 与 data-outpool
# 既是死代码，又像是在告诉 agent「这里要改」。
_m = re.search(r"^const SINGLE_SYM = .*?^const BOOK_ROOT = \{.*?\};\n", txt, re.S | re.M)
if not _m:
    sys.exit('❌ 找不到账本切换机制 —— mock 的结构变了')
txt = (txt[:_m.start()]
       + "/* 交付模板只有一本账：切换器由 build_template.py 移除，STATE.book 恒为 'all'。 */\n"
         "const BOOKS     = { all:()=>true };\n"
         "const BOOK_ROOT = { all:'data' };\n"
       + txt[_m.end():])
if _removed != len(_DEMO_CONSTS):
    sys.exit(f'❌ demo 常量只删掉 {_removed}/{len(_DEMO_CONSTS)} 条 —— mock 的结构变了，先看清楚')

# ⚠️ 「删了标记，处理器自然失效」是错的 —— `document.getElementById('demo-ctl')
#    .addEventListener(...)` 在元素不存在时**当场抛异常**，整段脚本从那里断掉，
#    页面一行数据都渲染不出来。第一版就是这么挂的：标题对了、切换器没了、
#    而持仓 0 行、告警 0 条、34 条自检全红。
#    绑定必须跟着标记一起删，样式规则顺手清掉。
txt = re.sub(r'^  \.demo-b[^\n]*\n', '', txt, flags=re.M)
# ⚠️ 只删 .demo-b 会漏三样：.demo-ctl 的样式、syncDemoBar() 及其调用、写死的重放日期。
#    切换器的标记删了而查询它的函数还在，且仍被调用；
#    留着的那道检查数的是 HTML 属性，看不见 JS 字符串里的选择器。
_before = len(txt)
txt = re.sub(r'^  \.demo-ctl\{[^\n]*\n(?:[ ]{4}[^\n]*\n)*', '', txt, flags=re.M)
txt = re.sub(r'^function syncDemoBar\(\)\{\n(?:.*?\n)*?\}\n', 
             '/* syncDemoBar 已由 build_template.py 移除（切换器不随包发布） */\n',
             txt, flags=re.M)
txt = re.sub(r'^\s*syncDemoBar\(\);[^\n]*\n', '', txt, flags=re.M)
# 写死的重放日期：读一个不随包发布的 state-<date>.json
txt = txt.replace("""    const stateFile = STATE.day==='2026-08-04' && FS.root==='data'
      ? 'data/state-2026-08-04.json' : 'data/state.json';""",
                  "    const stateFile = 'data/state.json';")
if len(txt) == _before:
    sys.exit('❌ demo 残留一处都没删掉 —— mock 的结构变了，先看清楚')

# 三段绑定：disclaimer 的展开、demo-ctl 的 keydown 与 click
BINDINGS = [
    (r"document\.querySelector\('\.disc-head'\)\.addEventListener\(", 3),
    (r"document\.getElementById\('demo-ctl'\)\.addEventListener\('keydown'", 3),
    (r"document\.getElementById\('demo-ctl'\)\.addEventListener\('click'", None),
]
tl = txt.split('\n')
for pat, span in BINDINGS:
    idx = next((i for i, l in enumerate(tl) if re.search(pat, l)), None)
    if idx is None:
        sys.exit(f'❌ 找不到要删的绑定：{pat}')
    if span is None:
        # click 那段以 `renderAll(); });` 收尾，按括号配平找结束更稳
        depth = 0; end = None
        for j in range(idx, len(tl)):
            depth += tl[j].count('(') - tl[j].count(')')
            if j > idx and depth <= 0:
                end = j; break
        if end is None or end - idx > 60:
            sys.exit('❌ demo-ctl click 绑定的结束位找不到或跨度异常')
        span = end - idx + 1
    tl[idx:idx+span] = [f'/* demo 绑定已由 build_template.py 移除（{pat[:28]}…）*/']
txt = '\n'.join(tl)
# ⚠️ 自检必须在**全部删改之后**跑。此前它排在 demo 残留清理之前 ——
#    查的是还没改过的文本，于是既漏掉真残留，又对干净的产物报错。
#    node --check 同理：解析的必须是真正落盘的那份字节。
# ── 自检：删完之后必须还能解析，且 demo 切换器一个不剩 ──
import subprocess, tempfile
# ⚠️ 只查 JS。`<script type="application/json">` 装的是数据，
#    拿 node --check 解析它必然失败 —— 检查在报错，不是文件有错。
blocks = [m.group(2) for m in re.finditer(
    r'<script((?![^>]*\bsrc=)[^>]*)>([\s\S]*?)</script>', txt)
    if 'type=' not in m.group(1) or 'javascript' in m.group(1)]
for b in blocks:
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(b); p = f.name
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
    os.unlink(p)
    if r.returncode:
        sys.exit('❌ 产出的模板脚本无法解析：\n' + r.stderr[:500])
# ⚠️ 断言的是**标记**，不是字符串出现次数。
#    第一版数 `txt.count('demo-b')`，把 CSS 规则和已经失效的事件处理器也算了进去 ——
#    那两处不渲染任何东西，报出来只会让人以为没删干净。要查的是「页面上还有没有这个控件」。
# ⚠️ 原来只数 HTML 属性 —— 而残留大多在 JS 里：字符串选择器、函数名、写死的日期。
#    「查的对象与以为在查的对象不是一个」，所以这道检查一直是通过的。
left = []
if re.search(r'<[^>]*class="[^"]*\bdemo-b\b', txt): left.append('demo-b 标记')
if 'id="demo-ctl"' in txt: left.append('demo-ctl 元素')
if re.search(r'^\s*\.demo-ctl\{', txt, re.M): left.append('.demo-ctl 样式')
if re.search(r'^function syncDemoBar', txt, re.M): left.append('syncDemoBar 定义')
if re.search(r'^\s*syncDemoBar\(\);', txt, re.M): left.append('syncDemoBar 调用')
for pat, name in [(r"state-20\d\d-\d\d-\d\d", '写死的重放日期'),
                  (r"^const SINGLE_SYM", '示例标的常量'),
                  (r"^const DAY='", '写死的日期常量'),
                  (r"data-outpool", '池外目录分支')]:
    if re.search(pat, txt, re.M): left.append(name)
if left:
    sys.exit('❌ 模板里还剩 demo 残留：' + ' · '.join(left))

open(DST, 'w').write(txt)
# ⚠️ 报的必须是**落盘文件**的行数，不是中间量。
#    原来打印 `len(out)`（只减了自述块的那一步），比实际多 31 行 ——
#    而「行数骤降就是吞节的信号」这条自查，靠的正是这个数准确。
#    一个报错了的计数，比不报更坏：它让人以为核对过了。
_final = len(txt.split('\n'))
_css_and_bindings = len(out) - _final
print(f"skill/template/index.html  {_final} 行"
      f"（源 {len(lines)} − 自述块 {removed} − 样式与绑定 {_css_and_bindings}）"
      f"· 脚本可解析 · demo 切换器 0 处")
