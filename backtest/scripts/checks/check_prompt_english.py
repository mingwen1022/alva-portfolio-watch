# -*- coding: utf-8 -*-
"""送进模型的提示词必须全英文。

⚠️ 存在理由：禁用词表是**在英文上实测出来的一组词**。
   `significant` 触发的是一批措辞，中文的「显著」既是统计词也是日常词，
   触发的是另一批 —— data-pipeline §九 明写「中文表不能靠机器翻译这一组得到」。
   提示词里混进中文，等于让模型在一套没测过的约束下工作，而输出照样合法。

   注释里的中文不算 —— 它们不进模型。这个检查只看**字符串字面量**。
"""
import re, sys, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..')
SRC  = os.path.join(ROOT, 'skill/scripts/attribution.js')
if not os.path.exists(SRC):
    print('⚠️ 没有 attribution.js，跳过'); raise SystemExit(0)

s = open(SRC).read()
# 先剥注释 —— 块注释与行尾注释都剥
s = re.sub(r'/\*[\s\S]*?\*/', '', s)
s = re.sub(r'(?m)//.*$', '', s)

# 取出所有字符串字面量（含模板串）
lits = re.findall(r'`([^`]*)`|"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', s)
bad = []
for tup in lits:
    for v in tup:
        if v and re.search(r'[一-鿿]', v):
            bad.append(v.strip()[:100])

if bad:
    print(f'❌ 提示词里有中文（{len(bad)} 处）：')
    [print('  ', b) for b in bad]
    raise SystemExit(1)
print('✅ 提示词全英文（注释不计）')
