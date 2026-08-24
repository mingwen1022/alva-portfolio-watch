# -*- coding: utf-8 -*-
"""告警生命周期的回放测试。

不造合成序列 —— 拿 MSTR 的真实日线和用户在 config/alerts.json 里设的止损线 125.0，
把两年真实收盘价喂进状态机，看 fired/cleared 发生在哪几天，再人工核对那几天的价格。
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../pipeline'))
import state as S

FAIL = []
def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + ("" if cond else f"  ← {detail}"))
    if not cond: FAIL.append(name)

# ── 1. 真实数据回放：MSTR US1 止损 125.0 ────────────────────────────
RAW = json.load(open('pipeline/raw/daily_full.json'))['MSTR']
rows = sorted((l.split(',')[0], float(l.split(',')[1])) for l in RAW.strip().split('\n') if l)[-500:]
LINE = json.load(open('mock/config/alerts.json'))['userLines']['MSTR']['US1']

st, log = {}, []
for d, c in rows:
    live = {"MSTR:US1"} if c <= LINE else set()
    st, ev = S.step(st, live, d + "T16:00:00-04:00", pushed={k for t, k in [] })
    log += [(d, t, round(c, 2)) for t, k in ev]

fired   = [x for x in log if x[1] == 'fired']
cleared = [x for x in log if x[1] == 'cleared']
print(f"\n真实回放 · MSTR 止损线 {LINE} · {rows[0][0]} → {rows[-1][0]} 共 {len(rows)} 根")
print(f"  触发 {len(fired)} 次 · 解除 {len(cleared)} 次")
for d, t, c in (fired + cleared)[:6]: print(f"    {d}  {t:8s} 收盘 {c}")

check("每次触发时收盘确实在线下", all(c <= LINE for d, t, c in fired), fired[:3])
check("每次解除时收盘确实在线上", all(c > LINE for d, t, c in cleared), cleared[:3])
seq = [t for d, t, c in sorted(log)]
check("触发与解除严格交替", all(a != b for a, b in zip(seq, seq[1:])), seq[:8])
check("序列以 fired 开头", seq[0] == 'fired' if seq else False, seq[:3])
check("触发次数与解除次数相差不超过 1", abs(len(fired) - len(cleared)) <= 1,
      f"{len(fired)} vs {len(cleared)}")

# ── 2. 破坏性测试：每条断言都要真的失败过一次 ──────────────────────
print("\n破坏性测试")
st2, _ = S.step({}, {"MSTR:US1"}, "2026-08-01T16:00:00-04:00")

# 反例回放：把线设成 0，真实收盘永远在线上 → 一次都不该触发
st_z = {}; ev_z = []
for d, c in rows:
    st_z, e = S.step(st_z, {"MSTR:US1"} if c <= 0 else set(), d + "T16:00:00-04:00")
    ev_z += e
check("线设成 0 时真实回放一次都不触发", ev_z == [], ev_z[:3])

# 反例回放：把线设成 10 万，真实收盘永远在线下 → 触发一次后再不解除
st_h = {}; ev_h = []
for d, c in rows:
    st_h, e = S.step(st_h, {"MSTR:US1"} if c <= 1e5 else set(), d + "T16:00:00-04:00")
    ev_h += e
check("线设成极大值时只触发一次且无解除",
      [t for t, k in ev_h] == ['fired'], ev_h[:3])

st3, ev3 = S.step({}, set(), "2026-08-01T16:00:00-04:00")
check("空输入不产生事件", ev3 == [], ev3)

st4, ev4 = S.step(st2, set(), "2026-08-02T16:00:00-04:00")
check("成立→不成立 产生 cleared", [t for t, k in ev4] == ['cleared'], ev4)
check("cleared 后 on=False 且 clearedAt 有值",
      st4['keys']['MSTR:US1']['on'] is False and st4['keys']['MSTR:US1']['clearedAt'], st4)

st5, ev5 = S.step(st4, set(), "2026-08-03T16:00:00-04:00")
check("解除后保留一个周期不删", 'MSTR:US1' in st5['keys'], st5)
st6, ev6 = S.step(st5, set(), "2026-08-05T16:00:00-04:00")
check("再过一个周期才删掉", 'MSTR:US1' not in st6['keys'], st6)

# ── 3. 事件型不产生 cleared ────────────────────────────────────────
st7, ev7 = S.step({}, {"NVDA:PV1"}, "2026-08-01T16:00:00-04:00")
st8, ev8 = S.step(st7, set(), "2026-08-02T16:00:00-04:00")
check("事件型消失时不产生 cleared", [t for t, k in ev8] == [], ev8)

# ── 4. 冷却读的是 lastPush 不是「算出来过」 ────────────────────────
sA, _ = S.step({}, {"NVDA:EV1"}, "2026-07-01T16:00:00-04:00")            # 算出来了没推
check("没推过就不在冷却里", not S.in_cooldown(sA, "NVDA:EV1", "2026-07-10T16:00:00-04:00"))
sB, _ = S.step({}, {"NVDA:EV1"}, "2026-07-01T16:00:00-04:00", pushed={"NVDA:EV1"})
check("推过之后 45 日内在冷却里", S.in_cooldown(sB, "NVDA:EV1", "2026-07-10T16:00:00-04:00"))
check("45 日之后不在冷却里", not S.in_cooldown(sB, "NVDA:EV1", "2026-09-01T16:00:00-04:00"))

# ── 5. 改线即重新武装 ──────────────────────────────────────────────
print("\n改线重新武装")
a,_ = S.step({}, {"MSTR:US1"}, "2026-08-01T16:00:00-04:00",
             pushed={"MSTR:US1"}, armed={"MSTR:US1":125.0})
check("首次触发记下线值", a['keys']['MSTR:US1']['armedFor']==125.0, a)
b,ev = S.step(a, {"MSTR:US1"}, "2026-08-02T16:00:00-04:00", armed={"MSTR:US1":125.0})
check("线没变时不重新武装", [t for t,k in ev]==[], ev)
c,ev = S.step(b, {"MSTR:US1"}, "2026-08-03T16:00:00-04:00", armed={"MSTR:US1":130.0})
check("线改了 → rearmed 且当轮重新 fired",
      [t for t,k in ev]==['rearmed','fired'], ev)
check("重新武装后 lastPush 清空（新线的第一次不该被旧的压住）",
      c['keys']['MSTR:US1']['lastPush'] is None, c['keys']['MSTR:US1'])
check("重新武装后记的是新线值", c['keys']['MSTR:US1']['armedFor']==130.0, c)
d2,ev = S.step(c, set(), "2026-08-04T16:00:00-04:00", armed={"MSTR:US1":130.0})
check("新线下不再成立 → cleared", [t for t,k in ev]==['cleared'], ev)

# 持续天数
e,_ = S.step({}, {"MSTR:US1"}, "2026-06-16T16:00:00-04:00", armed={"MSTR:US1":125.0})
check("持续天数按日历日算", S.standing_days(e['keys']['MSTR:US1'],"2026-08-21T16:00:00-04:00")==66,
      S.standing_days(e['keys']['MSTR:US1'],"2026-08-21T16:00:00-04:00"))

print(f"\n{'❌ 失败 '+str(len(FAIL)) if FAIL else '✅ 全过'}")
sys.exit(1 if FAIL else 0)
