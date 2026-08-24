# -*- coding: utf-8 -*-
"""信号目录 signals.json。契约见 output-schema §二。

⚠️ 存在理由：这个文件原来是**手写**的，没有任何脚本产出它 ——
   于是往账本里加第三个资产类别时，十一条信号的 `assetClass` 一条都没跟着动。
   后果不是报错：ETF 会拿到反解出的 θv、算出 findings，
   然后每一条都因为「本条信号不适用于该资产类别」而在界面上不显示。
   今天没暴露，只因为五只 ETF 一只都没触发。

⚠️ 名称、类型、证据、投递上限的唯一定义处是 product/signal-spec.md §一。
   这里只是把那张表变成机器可读的形状，改内容要先改 spec。
"""
import json, os

# assetClass 逐条的适用范围。⚠️ 这是本文件唯一需要判断的一列 ——
#    其余全是 spec §一 那张表的誊抄。
#
#    other（ETF 等未验证类别）的取舍：
#      PV1  ✅ 阈值走池级反解，规则本身与资产类别无关
#      PV5  ❌ 盘中阈值没有兜底反解规则 —— SKILL §1.2 明令不启用
#      PV3  ✅ 幅度标注，任何价格序列都算得出
#      PV4  ✅ 覆盖标注是关于基线长度的元信息，与类别无关
#      US1–3 ✅ 用户自己填的线，与我们验没验过无关
#      EV1/EV4/EV6 ❌ ETF 没有内部人、没有财报、没有公司新闻
#      DR1  ❌ 仅加密
US, CR, OT = "us_equity", "crypto", "other"
CATALOG = [
 ("PV1", "价量异动 · 日线",      "Price-volume move · daily", "alert",       [US,CR,OT], "daily", "green",  "critical",      "L1", True),
 ("PV5", "价量异动 · 盘中 15 分钟","Price-volume move · 15-min","alert",      [US,CR],    "bar",   "green",  "critical",      "L1", True),
 ("PV3", "幅度标注",             "Size marker",               "display",     [US,CR,OT], "daily", "na",     None,            "L3", False),
 ("PV4", "覆盖标注",             "Coverage marker",           "display",     [US,CR,OT], "daily", "na",     None,            "L3", False),
 ("EV1", "内部人簇买",           "Insider cluster buy",       "record",      [US],       "daily", "na",     None,            "L3", False),
 ("EV4", "财报日历",             "Earnings calendar",         "calendar",    [US],       "daily", "na",     "informational", "L3", False),
 ("EV6", "公司新闻",             "Company news",              "attribution", [US],       "daily", "yellow", None,            "L3", False),
 ("DR1", "费率极端",             "Funding extremes",          "display",     [CR],       "daily", "amber",  None,            "L2", False),
 ("US1", "止损线",               "Stop line",                 "alert",       [US,CR,OT], "daily", "na",     "warning",       "L1", True),
 ("US2", "止盈线",               "Take-profit line",          "alert",       [US,CR,OT], "daily", "na",     "warning",       "L1", True),
 ("US3", "回撤线",               "Drawdown line",             "alert",       [US,CR,OT], "daily", "na",     "warning",       "L1", True),
]

out = {"generatedFrom": "signal-spec.md",
       "signals": {sid: {"name": {"zh": zh, "en": en}, "type": typ, "assetClass": ac,
                         "granularity": gran, "evidence": ev, "severity": sev,
                         "maxDelivery": md, "pushable": push}
                   for sid, zh, en, typ, ac, gran, ev, sev, md, push in CATALOG}}

for book in ("mock/data", "mock/data-outpool"):
    p = os.path.join(book, "signals.json")
    if os.path.isdir(book):
        json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)

n_ot = sum(1 for c in CATALOG if OT in c[4])
print(f"signals.json {len(CATALOG)} 条 · 适用于 other 的 {n_ot} 条："
      f" {[c[0] for c in CATALOG if OT in c[4]]}")
