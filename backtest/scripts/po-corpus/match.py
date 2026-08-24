# M17 / M24 匹配实现。规则见 signal-registry.md §四：词边界 + 缩写大小写敏感。
import re, os, importlib.util

_WL = "/Users/ming/project/alva/backtest/scripts/m24/wordlist.py"   # M24 词表唯一定义处，只读引用
spec = importlib.util.spec_from_file_location("wl", _WL)
wl = importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)

def _compile(group):
    out = []
    for p, cs in group:
        pat = p if p.startswith(r"\b") else r"\b" + p + r"\b"
        out.append((re.compile(pat, 0 if cs else re.I), p))
    return out

M24_BY_GROUP = {k: _compile(v) for k, v in wl.GROUPS.items()}
M24_ALL = [x for v in M24_BY_GROUP.values() for x in v]

def m24_hits(t):
    return [p for rx, p in M24_ALL if rx.search(t)]

def m24(t):
    return any(rx.search(t) for rx, _ in M24_ALL)

# M17 词表 —— 与 backtest/scripts/m24/test.py 逐字相同，保证与有偏语料的数字可比。
# 对应半导体组合 NVDA + AMD + MSFT 的 themeExposure 展开。
M17_WORDS = ["AI","artificial intelligence","chip","chips","semiconductor","semiconductors",
             "data center","datacenter","export control","export controls","tariff","tariffs",
             "China","GPU","Nvidia","AMD","Microsoft","cloud","foundry","TSMC","wafer"]
_P17 = [(re.compile(r"\b"+re.escape(w)+r"\b", 0 if (w.isupper() and len(w) <= 4) else re.I), w)
        for w in M17_WORDS]

def m17_hits(t):
    return [w for rx, w in _P17 if rx.search(t)]

def m17(t):
    return any(rx.search(t) for rx, _ in _P17)
