"""PO 语料装载 + M17/M24 匹配 + M19 浅层去重。

与 backtest/scripts/po-corpus/{load,match}.py 同口径，差别只有两处：
  1) TSV 实际路径是 data/po-corpus/*.tsv（仓库里的 load.py 写的是 data/handles/*.tsv，找不到文件）
  2) `\bwar\b` 加了排除式 —— registry 词表章节说「已加排除式」，但 wordlist.py 里没有
"""
import os, re, glob, hashlib, importlib.util
from datetime import datetime, timezone

CORPUS = "/Users/ming/project/alva/backtest/data/po-corpus"
_WL = "/Users/ming/project/alva/backtest/scripts/m24/wordlist.py"

TIER = {
    "官方政策机构": "WhiteHouse POTUS USTreasury SecScottBessent federalreserve CommerceGov USTradeRep SECGov BLS_gov USDOL StateDept SpeakerJohnson".split(),
    "政策当事人": "realDonaldTrump SecRubio JDVance howardlutnick VP PressSec".split(),
    "央行与国际组织": "ecb bankofengland IMFNews OPECSecretariat".split(),
    "财经媒体与快讯": "DeItaone Schuldensuehner NickTimiraos markets economics CNBCnow ReutersBiz zerohedge".split(),
}
H2T = {h: t for t, hs in TIER.items() for h in hs}
LAYER_MAIN = TIER["官方政策机构"] + TIER["政策当事人"]          # 18
LAYER_CB = TIER["央行与国际组织"]                               # 4
LAYER_MEDIA = TIER["财经媒体与快讯"]                            # 7 实得
TIER_A = LAYER_MAIN + LAYER_CB                                  # 22 —— coverage-report 推荐口径

# ---------------- M24 ----------------
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

# registry「地缘供应链」组要求的 war 排除式（wordlist.py 尚未落实）
_WAR_EXCL = re.compile(
    r"\b(world war|war on drugs|war on christmas|war chest|price war|bidding war|war of words|"
    r"culture war|war room|war hero|war memorial|star wars|war crimes?)\b", re.I)
_WAR_RX = re.compile(r"\bwar\b", re.I)


def _war_ok(t):
    """裸 \bwar\b 命中后再判：命中位置若全部落在排除搭配里则不算 M24 命中。"""
    excl = [(m.start(), m.end()) for m in _WAR_EXCL.finditer(t)]
    for m in _WAR_RX.finditer(t):
        if not any(a <= m.start() and m.end() <= b for a, b in excl):
            return True
    return False


def m24_hits(t):
    out = []
    for rx, p in M24_ALL:
        if not rx.search(t):
            continue
        if p == r"\bwar\b" and not _war_ok(t):
            continue
        out.append(p)
    return out


def m24(t):
    return bool(m24_hits(t))


# ---------------- M17（半导体组合 NVDA+AMD+MSFT 的 themeExposure 展开） ----------------
M17_WORDS = ["AI", "artificial intelligence", "chip", "chips", "semiconductor", "semiconductors",
             "data center", "datacenter", "export control", "export controls", "tariff", "tariffs",
             "China", "GPU", "Nvidia", "AMD", "Microsoft", "cloud", "foundry", "TSMC", "wafer"]
_P17 = [(re.compile(r"\b" + re.escape(w) + r"\b", 0 if (w.isupper() and len(w) <= 4) else re.I), w)
        for w in M17_WORDS]


def m17_hits(t):
    return [w for rx, w in _P17 if rx.search(t)]


def m17(t):
    return any(rx.search(t) for rx, _ in _P17)


# ---------------- 装载 ----------------
_URL = re.compile(r"https?://\S+")


def _norm(t):
    return " ".join(_URL.sub("", t).lower().split())


def load(handles=None):
    rows = []
    for f in sorted(glob.glob(os.path.join(CORPUS, "*.tsv"))):
        h = os.path.basename(f)[:-4]
        if handles and h not in handles:
            continue
        for line in open(f, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 7:
                p = p + [""] * (7 - len(p))
            if len(p) < 5:
                continue
            own, src = p[2], p[5]
            text = (own + " " + src).strip() if src else own
            if not text.strip():
                continue
            try:
                ts = datetime.strptime(p[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            nz = _norm(text)
            if not nz:
                continue
            rows.append(dict(ts=ts, handle=h, own=own, ctype=p[3], pid=p[4], src=src,
                             src_handle=p[6], text=text, norm=nz, tier=H2T.get(h, "?"),
                             dk=hashlib.md5(nz.encode()).hexdigest()))
    rows.sort(key=lambda r: r["ts"])
    return rows


def dedup_l1(rows):
    """M19 L1：同一段正文（转推链 / 完全重复）只保留最早一条 —— 这条同时把 t0 回溯到
    语料内最早出现时刻（转推的 published_at 是转推时间，不是原帖时间）。"""
    seen, out = {}, []
    for r in rows:
        if r["dk"] in seen:
            seen[r["dk"]]["dupes"].append(r)
            continue
        r["dupes"] = []
        seen[r["dk"]] = r
        out.append(r)
    return out


def _grams(s, n=3):
    s = s if len(s) >= n else s + " " * (n - len(s))
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def dedup_l2(rows, thr=0.85, days=7):
    """M19 L2：字符 3-gram Jaccard > thr，窗口 = 近 days 日已保留内容。
    倒排索引（按 gram 取候选）避免 O(n^2)。"""
    from collections import defaultdict
    kept, killed = [], []
    inv = defaultdict(list)          # gram -> [(idx)]
    store = []                       # (ts, gramset)
    win = days * 86400
    for r in rows:
        g = _grams(r["norm"])
        t = r["ts"].timestamp()
        cand = {}
        for gm in g:
            for i in inv.get(gm, ()):
                cand[i] = cand.get(i, 0) + 1
        hit = None
        for i, inter in cand.items():
            ts_i, g_i = store[i]
            if t - ts_i > win:
                continue
            j = inter / (len(g) + len(g_i) - inter)
            if j > thr:
                hit = i
                break
        if hit is not None:
            r["l2_dup_of"] = hit
            killed.append(r)
            continue
        idx = len(store)
        store.append((t, g))
        for gm in g:
            inv[gm].append(idx)
        kept.append(r)
    return kept, killed
