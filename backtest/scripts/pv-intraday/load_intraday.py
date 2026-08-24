"""把 raw/*.json（fetch15.js 输出）解析成 (session, slot) 网格。

美股   时间戳是真 UTC。session = 美东日历日；ETH 网格 04:00–19:45 ET 共 64 槽，
       RTH 网格 09:30–15:45 ET 共 26 槽。**必须转美东**：冬令时 20:00 ET = 次日
       01:00 UTC，按 UTC 日切会把尾盘划到第二天。
加密   session = UTC 日，96 槽。
"""
import json, glob, os, numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"

_cache = None
def _index():
    global _cache
    if _cache is not None: return _cache
    _cache = {}
    for f in sorted(glob.glob(f"{BASE}/raw/*_b*.json")):
        kind = "crypto" if os.path.basename(f).startswith("crypto") else "stock"
        try: d = json.load(open(f))
        except Exception: continue
        if not d.get("result"): continue
        try: r = json.loads(d["result"])
        except Exception: continue
        for sym, v in r.items():
            if v.get("csv"): _cache[sym] = (kind, v["csv"], v.get("n"))
    return _cache

def symbols():
    return sorted(_index().keys())

def raw_bars(sym):
    kind, csv_s, _ = _index()[sym]
    ts, c, v = [], [], []
    for rec in csv_s.split(";"):
        a = rec.split(",")
        if len(a) != 3: continue
        try: ts.append(int(a[0])); c.append(float(a[1])); v.append(float(a[2]))
        except ValueError: continue
    ts = np.array(ts, dtype=np.int64); c = np.array(c); v = np.array(v)
    o = np.argsort(ts)
    return kind, ts[o], c[o], v[o]

def to_grid(sym, session="ETH"):
    """session: 'ETH'(美股扩展 64 槽) | 'RTH'(美股常规 26 槽) | 'UTC'(加密 96 槽)"""
    kind, ts, c, v = raw_bars(sym)
    if kind == "crypto":
        import pandas as pd
        loc = pd.to_datetime(ts, unit="s", utc=True)
        slot = ((ts % 86400) // 900).astype(int)
        nslots = 96
        keep = np.ones(len(ts), bool)
        # 与美股一致，用 YYYYMMDD 整数做 session 键（原来误用「距 epoch 天数」）
        daykey = (loc.year * 10000 + loc.month * 100 + loc.day).to_numpy()
    else:
        # 转美东（向量化）：分钟数与日期
        import pandas as pd
        loc = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York")
        mins = (loc.hour * 60 + loc.minute).to_numpy()
        daykey = (loc.year * 10000 + loc.month * 100 + loc.day).to_numpy()
        if session == "ETH":
            start, nslots = 4 * 60, 64        # 04:00 → 19:45
        else:
            start, nslots = 9 * 60 + 30, 26   # 09:30 → 15:45
        slot = (mins - start) // 15
        keep = (slot >= 0) & (slot < nslots) & (((mins - start) % 15) == 0)
        slot = slot.astype(int)
    ts, c, v, slot, daykey = ts[keep], c[keep], v[keep], slot[keep], daykey[keep]
    udays, sess = np.unique(daykey, return_inverse=True)
    return dict(sym=sym, kind=kind, nslots=nslots, sess=sess, slot=slot,
                close=c, vol=v, ts=ts, days=udays, D=len(udays))
