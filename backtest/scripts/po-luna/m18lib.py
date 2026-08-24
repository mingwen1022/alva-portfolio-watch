"""M18 抽取的共用件：提示词构造 + 六层校验（从 gen_llm.py 的 JS 版逐条移植）。"""
import re, json, unicodedata

PORTFOLIO = ["NVDA", "AMD", "MSFT"]
EVENT_TYPES = {"tariff","export-control","regulation","personnel","geopolitical","monetary","other"}
DIRECTIONS = {"bullish","bearish","mixed","neutral"}
SPECS = {"factual","rhetorical"}

FOLD_MAP = {
    0x2018:"'",0x2019:"'",0x201A:"'",0x201B:"'",0x2032:"'",0x02BC:"'",
    0x201C:'"',0x201D:'"',0x201E:'"',0x2033:'"',
    0x2010:"-",0x2011:"-",0x2012:"-",0x2013:"-",0x2014:"-",0x2015:"-",0x2212:"-",
    0x00A0:" ",0x2007:" ",0x202F:" ",0x200B:" ",0x200C:" ",0x200D:" ",0xFEFF:" ",
}
def fold(x):
    s = str(x).translate(FOLD_MAP).replace("…","...").replace("&amp;","&")
    return s
def norm(x):
    return re.sub(r"\s+"," ",fold(x)).strip().lower()

RE_NUM  = re.compile(r"\d")
RE_DATE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
RE_EFF  = re.compile(r"\b(effective|effective immediately|starting|begins|beginning|as of|takes effect|deadline|by the end of|no later than)\b", re.I)
RE_CO   = re.compile(r"\b(NVDA|AMD|MSFT|Nvidia|Microsoft)\b")
RE_DONE = re.compile(r"\b(signed|approved|revoked|imposed|sanctioned|banned|enacted|issued|announced|filed|published|passed|ratified|terminated|suspended|lifted|granted|denied|finalized|rescinded)\b", re.I)

def l5strict(ev): return bool(RE_NUM.search(ev) or RE_DATE.search(ev) or RE_EFF.search(ev) or RE_CO.search(ev))
def l5full(ev):   return bool(l5strict(ev) or RE_DONE.search(ev))

SYS = ("You are a strict information-extraction engine for a financial alerting pipeline. "
       "You output JSON only. No prose, no explanation, no markdown commentary. "
       "Do not use any tools. Do not read or write files. Answer directly.")

def build_prompt(items, err_note=None):
    p = []
    p.append(SYS)
    p.append("")
    p.append("Task: for EACH post below, extract a structured record. This is a classification task, not a summary.")
    p.append("")
    p.append("specificity is the ONLY field that gates the alert. It measures whether the post contains ACTIONABLE CONTENT, NOT whether the post is important.")
    p.append("  factual    = satisfies ANY of: (a) contains a concrete number (rate, amount, quota, date, percentage); "
             "(b) states an effective time (effective immediately / starting <date> / as of ...); "
             "(c) names a portfolio company or its specific product (" + ", ".join(PORTFOLIO) + ", Nvidia, AMD, Microsoft); "
             "(d) announces a COMPLETED action (signed, approved, revoked, imposed, sanctioned, banned, filed, published).")
    p.append("  rhetorical = everything else: intent (considering / may / will / plans to), opinion, praise, blame, vague generalities with no concrete object.")
    p.append("")
    p.append("specificity_evidence MUST be a VERBATIM contiguous substring copied character-for-character from that post's text. "
             "Copy punctuation exactly as it appears (curly apostrophes, dashes, ampersands). Do not fix typos, do not translate, "
             "do not shorten with ellipsis, and NEVER join two separate fragments. Keep it under 120 characters. "
             "If specificity is rhetorical, quote the phrase that shows it is rhetorical.")
    p.append("tickers: ONLY tickers from this portfolio " + json.dumps(PORTFOLIO) + ". Use [] if none are named.")
    p.append("direction is the direction of the EVENT itself, not of any single holding.")
    p.append("dedup_key.topic and dedup_key.object are short kebab-case strings; dedup_key.direction equals direction.")
    p.append("")
    p.append("Output EXACTLY one record per input id, ids echoed exactly, same set, no extras.")
    if err_note:
        p.append("")
        p.append("Your previous answer was rejected. Fix exactly this: " + err_note)
    p.append("")
    p.append("POSTS:")
    for it in items:
        p.append('id=' + it["id"])
        p.append('text="""' + it["text"] + '"""')
        p.append("")
    p.append("Return the records now.")
    return "\n".join(p)

def strip_fence(s):
    """L1 剥包装。codex 的 --output-last-message 通常已经是纯 JSON，但保留该层。"""
    if not s: return "", False
    t = str(s).strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m: return m.group(1).strip(), True
    a, b = t.find("{"), t.rfind("}")
    a2, b2 = t.find("["), t.rfind("]")
    if a2 >= 0 and (a < 0 or a2 < a):
        if b2 > a2 and (a2 > 0 or b2 < len(t)-1): return t[a2:b2+1], True
        return t, False
    if a >= 0 and b > a and (a > 0 or b < len(t)-1): return t[a:b+1], True
    return t, False

def coerce_array(obj):
    if isinstance(obj, list): return obj
    if isinstance(obj, dict):
        for k in ("records","results","items","data","output","posts"):
            if isinstance(obj.get(k), list): return obj[k]
        if "id" in obj: return [obj]
    return None

def validate(items, arr):
    """L2 schema+枚举+id 对齐 · L3 引文逐字 · L4 持仓约束 · L5 factual 自洽。"""
    by_id = {it["id"]: it for it in items}
    errs, bad, rawlab, ok, seen = [], {}, {}, [], set()
    layer_hits = {"L2":0,"L3":0,"L4":0,"L5":0}
    def fail(i, layer, msg, o=None):
        if i not in bad:
            bad[i] = {"layer": layer, "msg": msg}
            layer_hits[layer] = layer_hits.get(layer,0)+1
        if o and o.get("specificity") in SPECS:
            rawlab[i] = {"specificity":o.get("specificity"),
                         "ev":str(o.get("specificity_evidence") or "")[:200],
                         "event_type":o.get("event_type"),"direction":o.get("direction")}
        errs.append(f"{layer}:{i}:{msg}")
    if not isinstance(arr, list):
        return {"fatal":"L2 output is not a JSON array","bad":bad,"errs":["L2:*:not array"],
                "ok":[],"rawlab":rawlab,"layer_hits":layer_hits}
    for o in arr:
        if not isinstance(o, dict) or not o.get("id"):
            errs.append("L2:?:missing id"); continue
        i = str(o["id"])
        if i not in by_id: errs.append(f"L2:{i}:unknown id"); continue
        if i in seen: fail(i,"L2","duplicate id",o); continue
        seen.add(i)
        src = by_id[i]["text"]
        if o.get("specificity") not in SPECS: fail(i,"L2","specificity out of enum",o); continue
        if o.get("event_type") not in EVENT_TYPES: fail(i,"L2","event_type out of enum",o); continue
        if o.get("direction") not in DIRECTIONS: fail(i,"L2","direction out of enum",o); continue
        if not isinstance(o.get("objects"), dict): fail(i,"L2","objects missing",o); continue
        dk = o.get("dedup_key")
        if not isinstance(dk, dict) or not dk.get("topic"): fail(i,"L2","dedup_key.topic missing",o); continue
        ev = "" if o.get("specificity_evidence") is None else str(o["specificity_evidence"])
        if not ev: fail(i,"L2","specificity_evidence empty",o); continue
        qmode = "exact"
        if ev not in src:
            if fold(ev) in fold(src): qmode = "typographic"
            elif norm(ev) in norm(src): qmode = "normalized"
            else:
                fail(i,"L3",f'specificity_evidence "{ev[:90]}" is not a contiguous substring of that post; copy it character-for-character',o)
                continue
        tk = [str(x).upper() for x in (o["objects"].get("tickers") or [])]
        outside = [x for x in tk if x not in PORTFOLIO]
        if outside: fail(i,"L4","tickers outside portfolio: "+",".join(outside),o); continue
        s5, f5 = l5strict(ev), l5full(ev)
        if o["specificity"] == "factual" and not f5:
            fail(i,"L5","labelled factual but evidence has no number/date/effective-time/portfolio-company/completed-action",o); continue
        ok.append({"id":i,"event_type":o["event_type"],"direction":o["direction"],
                   "specificity":o["specificity"],"specificity_evidence":ev,"tickers":tk,
                   "countries":o["objects"].get("countries") or [],
                   "sectors":o["objects"].get("sectors") or [],
                   "dedup_key":dk,"quote_mode":qmode,"l5_strict":s5,"l5_full":f5})
    for it in items:
        if it["id"] not in seen: fail(it["id"],"L2","id missing from output")
    return {"fatal":None,"bad":bad,"errs":errs,"ok":ok,"rawlab":rawlab,"layer_hits":layer_hits}
