# -*- coding: utf-8 -*-
"""给超过 100 行的 reference 加目录（Anthropic skill 规范：>100 行必须有目录，
否则 agent 局部读取时看不到全貌，会静默漏掉整节）。

目录由标题生成，不手写 —— 手写副本在标题一改的那一刻就过期。
"""
import re, sys, os
MARK_A = "<!-- toc:start -->"
MARK_B = "<!-- toc:end -->"

def anchor(t):
    a = t.strip().lower()
    a = re.sub(r'[^\w一-鿿\s-]', '', a)
    return re.sub(r'\s+', '-', a).strip('-')

def build(path, top_only=False):
    src = open(path).read()
    # ⚠️ 连同前后空行一起吃掉。只吃块本身会每跑一次多留一个空行 ——
    # 文件单调变长，而「行数骤变」正是吞节事故的报警信号，噪音会盖住它。
    body = re.sub(rf'\n*{MARK_A}.*?{MARK_B}\n*', '\n', src, flags=re.S)
    lines = body.split('\n')
    fence = False; rows = []
    for ln in lines:
        if ln.lstrip().startswith('```'): fence = not fence; continue
        if fence: continue
        m = re.match(r'^(#{2,3})\s+(.+?)\s*$', ln)
        if m and not (top_only and len(m.group(1))>2): rows.append((len(m.group(1)), m.group(2)))
    if len(lines) < 100 or len(rows) < 3: return None
    toc = [MARK_A, "**目录**（自动生成，改标题后重跑 `backtest/scripts/add_toc.py`）", ""]
    for lvl, t in rows:
        toc.append(("- " if lvl == 2 else "  - ") + f"[{t}](#{anchor(t)})")
    toc += ["", MARK_B]
    # 插在第一个 ## 之前
    i = next(i for i, ln in enumerate(lines) if ln.startswith('## '))
    head = lines[:i]
    while head and head[-1].strip() == '': head.pop()
    out = head + [''] + toc + [''] + lines[i:]
    return '\n'.join(out), len(rows)

for p in ['product/signal-spec.md','product/signal-math.md','product/content-spec.md',
          'product/output-schema.md','product/data-pipeline.md','product/eval-plan.md','skill/SKILL.md']:
    r = build(p, top_only=p.endswith('SKILL.md'))
    if not r: print(f'跳过 {p}'); continue
    txt, n = r
    open(p,'w').write(txt)
    print(f'✅ {os.path.basename(p):22s} {n:2d} 条目录 · {txt.count(chr(10))} 行')
