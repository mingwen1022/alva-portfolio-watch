# -*- coding: utf-8 -*-
"""asOf 裁切的单一来源。

⚠️ 存在理由：**任何 finding 都不能晚于产出它的那一轮。**
   加密 24 小时交易，`raw/iv_*.csv` 里的 15 分钟 bar 一直延到取数那一刻，
   而 asOf 钉在 16:00 ET 收盘。不裁的话页面上会出现
   「16:05 跑出来的那一轮里，有一条 17:30 的告警」——
   实测 DOGE 的 20:30Z / 21:30Z 两根就是这么进来的。

   这是一条不需要任何统计就能发现的边界矛盾（CLAUDE.md §三·五 硬规则 1）。
   check_consistency.py 里有对应的断言，改这里要同时看那边。
"""
import json, datetime as dt

def asof_cut(path='mock/data/portfolio.json'):
    """返回裁切用的 UTC 串 `YYYY-MM-DDTHH:MM`，与 raw csv 的时间列同格式。

    bar 以**开盘时刻**打标，所以判据是 `t < cut`：
    正好开在 asOf 那一刻的 bar 还没收盘，不能算。
    """
    iso = json.load(open(path))["asOf"]
    return dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
