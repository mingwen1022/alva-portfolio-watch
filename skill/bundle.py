# -*- coding: utf-8 -*-
"""把 skill/ 打成一个自包含目录。

references/ 在仓库里是指向 product/ 的软链 —— 单一事实来源，改一处就够。
但 Skill 是按目录安装的：单独拷出去、打包、上传，这四个链接全断，
**而且断得很安静** —— 目录还在，文件名还在，打开是个坏链接。

所以交付前必须跑这一步，把软链变成真文件，并核对内容一致。
"""
import os,re,shutil,sys,hashlib,pathlib
SRC=pathlib.Path(__file__).parent; DIST=SRC.parent/'dist'/'portfolio-watch'
REQUIRED=['SKILL.md',
          'references/alva-platform.md','references/signal-spec.md',
          'references/data-contract.md','references/data-sources.md',
          # ⚠️ scripts/ 曾整个漏在清单外 —— 打出来的包里一个脚本都没有，
          #    而 SKILL.md 通篇让 agent「照抄 scripts/」。缺了不报错，装上去才发现。
          'scripts/lib.js','scripts/init.js','scripts/producer.js','scripts/producer-intraday.js',
          'scripts/producer-context.js','scripts/producer-market.js',
          'scripts/userlines.js','scripts/portfolio-link.js','scripts/attribution.js']
OPTIONAL=['template/index.html']

if DIST.exists(): shutil.rmtree(DIST)
DIST.mkdir(parents=True)

def h(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()[:12]

missing=[]
for rel in REQUIRED+OPTIONAL:
    s=SRC/rel
    if not s.exists():
        (missing if rel in REQUIRED else []).append(rel)
        if rel in REQUIRED: print(f'❌ 缺 {rel}')
        else: print(f'⏳ 未产出 {rel}（前端交付后再打包）')
        continue
    d=DIST/rel; d.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(s,d)                       # 跟随软链，拷内容
    assert not d.is_symlink()
    if rel.endswith('.md'):
        # 指向包外的相对链接在安装后是死链，且死得很安静 —— 链接文字还在，点开是 404。
        # 回测证据不随 Skill 分发，所以把链接降级成带标注的纯文本。
        t=open(d, encoding='utf-8').read()
        t2=re.sub(r'\[([^\]]+)\]\(\.\./[^)]+\)', r'\1（证据在项目回测目录，不随 Skill 分发）', t)
        if t2!=t: open(d,'w',encoding='utf-8').write(t2)
    print(f'✅ {rel:34s} {os.path.getsize(d):7d} B')

# 打完再走一遍：不许有软链，也不许有任何逃出包外的相对引用
left=[str(p.relative_to(DIST)) for p in DIST.rglob('*') if p.is_symlink()]
if left: print('❌ 仍有软链:',left); sys.exit(1)
# ⚠️ 本包**一个 markdown 链接都没有** —— 交叉引用一律写成反引号里的文件名。
#    原来只查 `](...)` 语法，于是这段检查对着空集永远通过，
#    而六处指向不发布文件的引用（signal-math.md 等）它一个都没看见。
#    一个不可能失败的断言等于没有断言 —— 改成查实际用的那种写法。
SHIPPED = {q.name for q in DIST.rglob('*') if q.is_file()}
# agent 自己产出的文件名 —— 它们本来就不该在包里，引用它们是对的
PRODUCED = {'README.md', 'index.html'}
# ⚠️ 模板也要查。它是包里最大的文件，注释里指向不发布的文档同样是死引用 ——
#    而只扫 *.md 的检查从来没看过它。第六类：检查的对象与以为在检查的对象不是一个。
NOT_SHIPPED = ['content-spec.md', 'output-schema.md', 'data-pipeline.md', 'signal-math.md']
esc=[]
_tpl = DIST/'template'/'index.html'
if _tpl.exists():
    _t = open(_tpl, encoding='utf-8').read()
    for _n in NOT_SHIPPED:
        if _n in _t: esc.append(f'template/index.html 提到不在包里的 {_n}')
for p in DIST.rglob('*.md'):
    t = open(p, encoding='utf-8').read()
    # ① markdown 链接（现在没有，将来可能有）
    for m in re.finditer(r'\]\((\.\./[^)]+|/[^)]+)\)', t):
        esc.append(f'{p.relative_to(DIST)} → {m.group(1)}')
    for m in re.finditer(r'\]\(([a-zA-Z0-9_./-]+\.md)\)', t):
        if not (p.parent/m.group(1)).exists(): esc.append(f'{p.relative_to(DIST)} → {m.group(1)} 不存在')
    # ② 反引号里的文件名 —— 本包实际使用的写法
    for m in re.finditer(r'`([a-zA-Z0-9_-]+\.(?:md|js|html))`', t):
        n = m.group(1)
        if n not in SHIPPED and n not in PRODUCED:
            esc.append(f'{p.relative_to(DIST)} 引用了不在包里的 {n}')
    # ③ 反引号里的包内路径
    for m in re.finditer(r'`((?:scripts|references|template)/[a-zA-Z0-9_.-]+)`', t):
        if not (DIST/m.group(1)).exists():
            esc.append(f'{p.relative_to(DIST)} 引用了不存在的 {m.group(1)}')
if esc:
    print('❌ 包外引用或死链:'); [print('   ',e) for e in esc]; sys.exit(1)
print('✅ 无软链 · 无包外引用 · 包内链接全部可解析')
if missing: print(f'\n❌ 缺 {len(missing)} 个必需文件，不完整'); sys.exit(1)
print(f'\n✅ 自包含包在 {DIST}')
