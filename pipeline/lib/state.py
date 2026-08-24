# -*- coding: utf-8 -*-
"""告警生命周期状态机。规格见 signal-spec §5.3.1 与 output-schema §一。

事件型：每轮从当日数据重算，「消失」即「今天的 findings 里没有它」。不需要状态。
状态型：需要一个 bit（上一轮成不成立）才能说出「已解除」。
"""
STATEFUL = {"US1","US2","US3","DR1","PF2"}          # 其余为事件型
CLEAR_HOLD = 1                                       # 解除后再留几个周期
COOLDOWN_DAYS = {"EV1": 45, "EV2": 45, "EV3": 45, "EV5": 45}

def _blank(): return {"on": False, "since": None, "lastPush": None,
                      "clearedAt": None, "armedFor": None}

def step(prev, live, now, pushed=None, armed=None):
    """一轮状态推进。

    prev    上一轮的 state.json（dict），首轮传 {}
    live    本轮成立的键集合 {"MSTR:US1", ...} —— 只含状态型才有意义
    now     本轮时刻（ISO 串）
    pushed  本轮真的推了手机的键集合
    armed   {key: 当前配置里的线值}。⚠️ 用户改了线，这一条就是一条新规则 ——
            旧的「已经推过了」不该压住新线的第一次触发。线值变了即重置

    返回 (新 state, 事件列表)。事件是 ("fired"|"cleared"|"rearmed"|"expired", key)。
    """
    pushed = pushed or set(); armed = armed or {}
    keys = {k: dict(v) for k, v in (prev.get("keys") or {}).items()}
    events = []

    # 线值变了 → 这一条重新武装，之前的状态一概作废
    for k, v in armed.items():
        e = keys.get(k)
        if e and e.get("armedFor") is not None and e["armedFor"] != v:
            keys[k] = _blank(); events.append(("rearmed", k))

    for k in sorted(live | set(keys)):
        sig = k.split(":", 1)[1]
        e = keys.setdefault(k, _blank())
        if sig in STATEFUL:
            if k in live and not e["on"]:
                e.update(on=True, since=now, clearedAt=None); events.append(("fired", k))
            elif k not in live and e["on"]:
                e.update(on=False, since=None, clearedAt=now); events.append(("cleared", k))
        else:
            # 事件型：on 恒为 false，只记 lastPush 供去重与冷却用
            if k in live and k not in keys: events.append(("fired", k))
        if k in armed: e["armedFor"] = armed[k]
        if k in pushed: e["lastPush"] = now

    # 裁剪：解除已过保留期 → 删；lastPush 早于最长冷却 → 删
    keep = {}
    for k, e in keys.items():
        if e["clearedAt"] and e["clearedAt"] < now and _cycles(e["clearedAt"], now) > CLEAR_HOLD:
            events.append(("expired", k)); continue
        if not e["on"] and not e["clearedAt"] and not e["lastPush"]:
            continue
        keep[k] = e
    return {"asOf": now, "keys": keep}, events

def _cycles(a, b):
    """两个 ISO 串之间隔了几个「日界」。同日为 0。"""
    return 0 if a[:10] == b[:10] else (_d(b) - _d(a)).days

def _d(iso):
    import datetime
    return datetime.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10]))

def in_cooldown(state, key, now):
    """EV 族 45 日冷却。lastPush 记的是「推过手机」，不是「算出来过」。"""
    sig = key.split(":", 1)[1]
    d = COOLDOWN_DAYS.get(sig)
    if not d: return False
    e = (state.get("keys") or {}).get(key)
    if not e or not e["lastPush"]: return False
    return _cycles(e["lastPush"], now) < d


def standing_days(entry, now):
    """已经持续多少个交易日 —— 界面上「持续中」那一组用它排序与措辞。

    ⚠️ 持续很久的不是「更紧急」，是「更该被读成状态而不是新闻」。
    """
    return _cycles(entry["since"], now) if entry.get("since") else None
