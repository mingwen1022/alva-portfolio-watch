# -*- coding: utf-8 -*-
"""SKILL.md 引用的每个「文件 §章节」都必须真的存在。

章节号是最容易烂掉的引用：改文档时插一节，所有后续编号就偏了，
而 SKILL.md 里的「见 output-schema §六·三」不会报错，只会指错地方。
"""
import re,sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[3]
SKILL=ROOT/'skill/SKILL.md'
# ⚠️ 新增 reference 必须同时加进这里，否则它的章节引用不受任何检查 ——
#    「检查跑过了」而它根本没在查那一份。
# 迁移中：已改写成 agent 文档的指向 skill/references/，未迁的仍在 product/。
# 迁完之后 product/ 冻结留档，全部指向 skill/references/。
DOCS={'alva-platform':'skill/references/alva-platform.md',
      'signal-spec':  'skill/references/signal-spec.md',
      'data-contract':'skill/references/data-contract.md',
      'data-sources': 'skill/references/data-sources.md'}
CN='一二三四五六七八九十'

def sections(p):
    """收集文档里所有出现过的章节标记：§三 / §5.6 / ## 三、… / ### 六·三"""
    s=open(ROOT/p).read(); out=set()
    for m in re.finditer(r'^#{2,4}\s*([0-9]+\.[0-9]+|[一二三四五六七八九十]+[、·]?[一二三四五六七八九十]*)', s, re.M):
        out.add(m.group(1).rstrip('、'))
    return out,s

have={k:sections(v) for k,v in DOCS.items()}
bad=[]
txt=open(SKILL).read()
# ⚠️ 文档名从 DOCS 推导，不再各写一份。原来两个正则各硬编码一份四文档列表，
#    往 DOCS 里加了新 reference 也不会被检查 —— 破坏性测试当场发现：
#    把引用改成一个不存在的章节，检查器照样报「全部可解析」。
ALT='|'.join(re.escape(k) for k in DOCS)
REF=re.compile(r'`?('+ALT+r')(?:\.md)?`?\s*§\s*([0-9]+\.[0-9]+|[一二三四五六七八九十]+[·、]?[一二三四五六七八九十]*)')
for m in REF.finditer(txt):
    doc,sec=m.group(1),m.group(2).rstrip('、')
    secs,raw=have[doc]
    # ⚠️ 标题必须**以**该章节号开头。原来用 `^#{2,4}.*<sec>`，
    #    §三 会被 `## 十三、…` 命中 —— 那不是同一节。
    ok = sec in secs or re.search(r'^#{2,4}\s*'+re.escape(sec)+r'(?![0-9一二三四五六七八九十])', raw, re.M)
    if not ok: bad.append((doc,sec,txt[:m.start()].count('\n')+1))

# ── 按**章节名**引用（`doc` → Title）──
# ⚠️ 编号引用有个老毛病：插一节，后面全偏，而引用不会报错，只会指错地方。
#    章节名不随插入漂移，所以 reference 一律用名字。
#
# ⚠️ 不要靠标点去切「章节名到哪结束」。第一版按中文标点断句，
#    文档转英文之后整行被当成标题吞进去，20 处引用全部报错 ——
#    错的是检查器，不是文档。改成拿该文档**已知的标题集合**去前缀匹配：
#    捕获到行尾，再看有没有哪个真实标题是它的前缀。
HEADS={k:[m.group(1).strip() for m in re.finditer(r'^#{2,4}\s+(.+?)\s*$', v[1], re.M)]
       for k,v in have.items()}
# ⚠️ 一行里常有两三个指针（读表的单元格）。第一版用 `(.+)$` 吞到行尾，
#    于是**同一行的第二个指针永远不会被检查** —— 破坏性测试当场发现：
#    把第二个改成不存在的章节，检查器照报「全部可解析」。
#    改成：每个指针的尾巴只延伸到下一个指针开头或行尾。
NAMED=re.compile(r'`('+ALT+r')`\s*→\s*')
starts=[(m.start(), m.end(), m.group(1)) for m in NAMED.finditer(txt)]
for i,(a0,a1,doc) in enumerate(starts):
    eol = txt.find('\n', a1)
    if eol < 0: eol = len(txt)
    nxt = starts[i+1][0] if i+1 < len(starts) else len(txt)
    tail = txt[a1:min(eol, nxt)]
    cands = sorted(HEADS[doc], key=len, reverse=True)
    if not any(tail.startswith(h) for h in cands):
        bad.append((doc, f'→ {tail.split(chr(183))[0].strip()[:48]}', txt[:a0].count('\n')+1))

kinds=sorted({m.group(1) for m in REF.finditer(txt)} | {m.group(1) for m in NAMED.finditer(txt)})
print(f'SKILL.md 里的跨文档章节引用 {len(kinds)} 类：{" · ".join(kinds)}')
if bad:
    print(f'\n⚠️ 指不到的 {len(bad)} 处：')
    for d,sec,ln in bad: print(f'   SKILL.md:{ln}  {d} §{sec}')
    sys.exit(1)
print('✅ 全部章节引用可解析')
