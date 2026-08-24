# -*- coding: utf-8 -*-
import re
# 免责声明按句式检测，不靠词表
ZH = re.compile(r'(不(构成|是|作为)\s*(任何)?\s*(投资|买卖|操作)?\s*(建议|意见|依据)'
                r'|仅(供|作|为)\s*(信息|参考|资讯|informational)?\s*(参考|用途|之用)?'
                r'|非\s*投资\s*(建议|意见)'
                r'|风险自担|据此操作.{0,6}风险自担)')
EN = re.compile(r'(not\s+(investment|financial|trading)\s+advice'
                r'|for\s+informational\s+purposes(\s+only)?'
                r'|does\s+not\s+constitute\s+(investment|financial)\s+advice'
                r'|not\s+(a\s+)?(\w+\s+){0,3}recommendation|not\s+(a\s+)?(\w+\s+){0,3}advice)', re.I)
def find_disclaimer(text):
    hits=[]
    for m in ZH.finditer(text): hits.append(('zh', m.group(0)))
    for m in EN.finditer(text): hits.append(('en', m.group(0)))
    return hits

CASES = [
    # (文本, 期望命中)
    ("本文只作信息用途，不是投资意见。", True),           # ← 实测漏网的那条
    ("仅供参考，不构成投资建议。", True),
    ("以上分析基于你提供的事件与指标，不构成投资建议。", True),
    ("非投资建议。", True),
    ("据此操作，风险自担。", True),
    ("This is an event attribution, not a forecast or trading recommendation.", True),
    ("For informational purposes only.", True),
    ("苹果股价下跌与库克披露全球内存短缺、成本上升及供应受限直接相关。", False),
    ("两则报道均点名苹果及存储芯片短缺、成本上升与供应受限。", False),
    ("报道晚于收盘 127 分钟，属于事后归因。", False),
    ("参考期指引下调。", False),                        # ← 「参考」单独出现不该命中
    ("这不是第一次出现供应问题。", False),
    ("The report does not recommend any position.", False),                # ← 「不是」单独出现不该命中
]
bad=0
for t,want in CASES:
    got=bool(find_disclaimer(t))
    ok = (got==want)
    if not ok: bad+=1
    print(("✅" if ok else "❌"), f"want={str(want):5s} got={str(got):5s}  {t[:46]}")
    if got: print("      命中:", find_disclaimer(t))
print(f"\n{len(CASES)-bad}/{len(CASES)} 通过" + ("" if bad==0 else f"  ❌ {bad} 条不符"))
