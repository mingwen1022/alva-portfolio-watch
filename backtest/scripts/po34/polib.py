"""PO3/PO4 分析公用层：装载 · 事件去重 · 切半 · 部门归一。"""
import gzip, json, collections, re

DATA = "/Users/ming/project/alva/backtest/data/"
HERE = "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34/"

# ---- GICS 部门词表（把 LLM 自由文本 sectors 映到 universe.csv 的 12 个部门） ----
# 只用经济学常识写，不看任何回测结果。未覆盖的词一律丢弃（不猜）。
SECTOR_MAP = {
    "科技": ["semiconductor", "semiconductors", "chip", "chips", "artificial intelligence",
             "artificial-intelligence", "ai", "technology", "tech", "software", "cloud computing",
             "cloud", "data centers", "data center", "hardware", "cybersecurity", "robotics",
             "quantum computing", "electronics", "computing", "information technology", "internet"],
    "加密": ["cryptocurrency", "crypto", "bitcoin", "digital assets", "stablecoin", "stablecoins",
             "blockchain", "digital-assets"],
    "能源": ["energy", "oil", "oil and gas", "natural gas", "gas", "petroleum", "opec", "refining",
             "coal", "lng", "oil & gas"],
    "金融": ["banking", "banks", "finance", "financial services", "financial-services", "financials",
             "financial markets", "credit", "insurance", "asset management", "payments",
             "capital markets", "lending", "private equity"],
    "工业": ["defense", "aerospace", "shipping", "manufacturing", "industrials", "transportation",
             "logistics", "airlines", "rail", "construction", "machinery", "shipbuilding",
             "defence", "aerospace and defense"],
    "医疗": ["healthcare", "health care", "pharmaceuticals", "pharma", "biotech", "biotechnology",
             "medical devices", "health", "vaccines", "drugs"],
    "原材料": ["critical minerals", "mining", "metals", "steel", "aluminum", "chemicals", "copper",
               "rare earths", "materials", "gold", "commodities", "lumber", "fertilizer"],
    "可选消费": ["automotive", "autos", "retail", "consumer discretionary", "e-commerce",
                 "travel", "hospitality", "restaurants", "apparel", "luxury", "gaming", "leisure"],
    "必需消费": ["agriculture", "food", "consumer staples", "beverages", "tobacco", "grocery",
                 "farming", "food and beverage"],
    "公用事业": ["utilities", "nuclear", "electricity", "power", "renewables", "solar", "wind",
                 "power generation", "grid"],
    "房地产": ["real estate", "housing", "real-estate", "mortgages", "homebuilding", "property"],
    "通信服务": ["telecom", "telecommunications", "media", "social media", "entertainment",
                 "advertising", "streaming", "broadcasting"],
}
W2S = {}
for sec, ws in SECTOR_MAP.items():
    for w in ws:
        W2S[w] = sec


def norm_sectors(lst):
    """LLM 自由文本部门 → GICS 部门集合。未覆盖词丢弃。"""
    out = set()
    for x in (lst or []):
        k = re.sub(r"[-_]", " ", str(x).strip().lower())
        if k in W2S:
            out.add(W2S[k])
    return out


def load():
    cand = json.load(gzip.open(DATA + "po-derived/candidates.json.gz", "rt"))
    lab = {r["id"]: r for r in json.load(gzip.open(DATA + "po-labels/m18_l5fixed.json.gz", "rt"))}
    cp = json.load(gzip.open(HERE + "conf_ports.json.gz", "rt"))
    idx = {c: i for i, c in enumerate(cp["cids"])}
    recs = []
    for r in cand:
        l = lab[r["cid"]]
        i = idx[r["cid"]]
        dk = l.get("dedup_key") or {}
        recs.append(dict(cid=r["cid"], ts=r["ts"], day=r["ts"][:10], month=r["ts"][:7],
                         handle=r["handle"], layer=r["layer"], m17=bool(r["h17"]), m24=bool(r["h24"]),
                         etype=l.get("event_type"), spec=l.get("specificity"),
                         verdict=l.get("verdict"), direction=l.get("direction"),
                         secs=norm_sectors(l.get("sectors")), raw_secs=l.get("sectors") or [],
                         topic=(dk.get("topic") or ""), obj=(dk.get("object") or ""),
                         i=i))
    return recs, cp


def dedup_events(recs):
    """M19 深层去重：同 (topic, object, event_type) 在同一 UTC 日内只留最早一条。"""
    recs = sorted(recs, key=lambda r: r["ts"])
    seen = set()
    out = []
    for r in recs:
        key = (r["day"], r["topic"], r["obj"], r["etype"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def half(r):
    return "H1" if r["month"] <= "2026-04" else "H2"
