import os, glob, hashlib
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER = {
 "官方政策机构": "WhiteHouse POTUS USTreasury SecScottBessent federalreserve CommerceGov USTradeRep SECGov BLS_gov USDOL StateDept SpeakerJohnson".split(),
 "政策当事人":   "realDonaldTrump SecRubio JDVance howardlutnick VP PressSec".split(),
 "央行与国际组织": "ecb bankofengland IMFNews OPECSecretariat".split(),
 "财经媒体与快讯": "DeItaone Schuldensuehner NickTimiraos markets economics CNBCnow ReutersBiz zerohedge".split(),
}
H2T = {h: t for t, hs in TIER.items() for h in hs}

def load():
    """列：ts handle own ctype id src_text src_handle
    text = 用于匹配的有效正文 —— 自有正文 + 被引用原文（转推的 full_text 恒为空）"""
    rows = []
    for f in sorted(glob.glob(os.path.join(D, "data/handles/*.tsv"))):
        h = os.path.basename(f)[:-4]
        for line in open(f, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 7: continue
            own, src = p[2], p[5]
            text = (own + " " + src).strip() if src else own
            if not text.strip(): continue
            rows.append({"ts": p[0], "handle": h, "own": own, "ctype": p[3], "id": p[4],
                         "src": src, "src_handle": p[6], "text": text,
                         "tier": H2T.get(h, "?"),
                         "dk": hashlib.md5(" ".join(text.lower().split()).encode()).hexdigest()})
    return rows

def dedup(rows):
    """跨账号去重：同一段正文（转推链）只保留最早一条。对应 M19 L1/L2 的下界。"""
    seen = {}
    for r in sorted(rows, key=lambda x: x["ts"]):
        seen.setdefault(r["dk"], r)
    return list(seen.values())
