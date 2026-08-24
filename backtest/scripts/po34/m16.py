"""M16 组合宏观/主题敏感度 —— 事前可算的参考实现。

设计约束（来自任务书）：新用户的组合上必须能直接算，不能依赖任何回测结果。
因此三个分支的输入全部是运行时可得的量：

  分支            输入                                      是否依赖回测
  ─────────────────────────────────────────────────────────────────────
  C  registry 现行  持仓权重 · 各标的 β(vs SPY) · 资产类别        否
  A  主题敞口重叠    持仓权重 · 各标的 GICS 部门 · 事件点名部门     否
  B  事件类型敏感度  持仓权重 · 各标的 GICS 部门 · 拟合矩阵         ⚠️ 是

⚠️ 回测结论（本目录 results-draft.md）：
   A 与 B 在 2026-01→04 构造、2026-05→08 检验的切半设计下都没有存活。
   **B 分支默认关闭**（enable_fitted=False），保留只为可复现；A 分支可以算但不构成筛选。
   本模块目前只有 C 分支有 registry 背书，而 C 在本次样本上同样区分不出确认率。

事件侧输入 event 只用 M18 那一遍 LLM 已经产出的字段（event_type · sectors），
不新增任何 LLM 调用。
"""
from __future__ import annotations
import re, json, os

# ---------------------------------------------------------------- 部门词表
# LLM 自由文本部门 → GICS 部门。只按经济学常识写，未覆盖的词一律丢弃（不猜）。
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
_W2S = {w: s for s, ws in SECTOR_MAP.items() for w in ws}

BETA_HIGH = 1.2        # registry M16：β_组合 > 1.2
CRYPTO_HIGH = 0.20     # registry M16：E_加密 > 20%
FITTED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m16_fitted_H1.json")


def normalize_sectors(raw):
    """把 M18 产出的自由文本 sectors 映到 GICS 部门集合。"""
    out = set()
    for x in (raw or []):
        k = re.sub(r"[-_]+", " ", str(x).strip().lower())
        if k in _W2S:
            out.add(_W2S[k])
    return out


def _norm_weights(holdings):
    tot = sum(max(h.get("weight", 0.0), 0.0) for h in holdings)
    if tot <= 0:
        n = len(holdings)
        return [1.0 / n] * n
    return [max(h.get("weight", 0.0), 0.0) / tot for h in holdings]


# ---------------------------------------------------------------- C 分支
def m16_registry(holdings):
    """registry 现行定义：β_组合 > 1.2 或 E_加密 > 20% → 高敏感。
    holdings: [{symbol, weight, sector, asset_class, beta}]
    加密标的不计入 β_组合，只计入 E_加密（registry 明确规定）。"""
    w = _norm_weights(holdings)
    e_cry = sum(wi for wi, h in zip(w, holdings) if h.get("asset_class") == "crypto" or h.get("sector") == "加密")
    eq = [(wi, h) for wi, h in zip(w, holdings)
          if not (h.get("asset_class") == "crypto" or h.get("sector") == "加密") and h.get("beta") is not None]
    wsum = sum(wi for wi, _ in eq)
    beta_p = (sum(wi * float(h["beta"]) for wi, h in eq) / wsum) if wsum > 0 else 0.0
    hi = (beta_p > BETA_HIGH) or (e_cry > CRYPTO_HIGH)
    return dict(branch="C", high=bool(hi), beta_portfolio=round(beta_p, 3),
                crypto_exposure=round(e_cry, 4),
                why=f"β_组合={beta_p:.2f}" + (f" · E_加密={e_cry:.0%}" if e_cry else ""))


# ---------------------------------------------------------------- A 分支
def m16_theme_overlap(holdings, event, threshold=0.20):
    """主题敞口重叠：事件点名的部门里，我的持仓占多少权重。
    threshold 是「高敏感」的判定线，默认 20%（与 registry 的 E_加密 门槛同刻度）。"""
    secs = normalize_sectors(event.get("sectors"))
    w = _norm_weights(holdings)
    ov = sum(wi for wi, h in zip(w, holdings) if h.get("sector") in secs)
    return dict(branch="A", high=bool(ov > threshold), score=round(ov, 4),
                matched_sectors=sorted(secs & {h.get("sector") for h in holdings}),
                event_sectors=sorted(secs),
                why=f"事件点名 {sorted(secs) or '—'}，命中持仓权重 {ov:.0%}")


# ---------------------------------------------------------------- B 分支
def _load_fitted():
    if not os.path.exists(FITTED_PATH):
        return None
    return json.load(open(FITTED_PATH))


def m16_fitted(holdings, event, matrix=None):
    """事件类型 × 部门 敏感度矩阵加权。⚠️ 回测未存活，默认不启用。"""
    matrix = matrix or _load_fitted()
    if not matrix:
        return None
    row = matrix.get(event.get("event_type") or "", {})
    w = _norm_weights(holdings)
    sc = sum(wi * row.get(h.get("sector") or "", 0.0) for wi, h in zip(w, holdings))
    return dict(branch="B", high=bool(sc > 0), score=round(sc, 5),
                why=f"事件类型 {event.get('event_type')} 的部门敏感度加权 {sc*100:+.2f}pp",
                caveat="拟合矩阵切半不存活，仅供复现，不应用于投递决策")


# ---------------------------------------------------------------- 对外入口
def m16(holdings, event, enable_fitted=False):
    """输入组合与事件，输出敏感度判定。
    holdings 每项需要 symbol / weight / sector / asset_class / beta（beta 可缺）。
    event 需要 event_type 与 sectors（M18 那遍 LLM 已产出，不新增调用）。"""
    out = {"C": m16_registry(holdings), "A": m16_theme_overlap(holdings, event)}
    if enable_fitted:
        b = m16_fitted(holdings, event)
        if b:
            out["B"] = b
    # 现行有效判定只认 C（唯一有 registry 背书的分支）
    out["verdict"] = "高敏感" if out["C"]["high"] else "低敏感"
    out["evidence"] = "🔴 A/B 分支切半不存活；C 分支在本次样本上区分不出确认率，见 results-draft.md"
    return out


if __name__ == "__main__":
    # 作业里的示例组合，事前算得出来
    port = [dict(symbol="NVDA", weight=0.4, sector="科技", asset_class="us_equity", beta=1.75),
            dict(symbol="TSLA", weight=0.3, sector="可选消费", asset_class="us_equity", beta=1.98),
            dict(symbol="AAPL", weight=0.3, sector="科技", asset_class="us_equity", beta=1.18)]
    for ev in [dict(event_type="export-control", sectors=["semiconductors", "China"]),
               dict(event_type="monetary", sectors=["central banking", "interest rates"]),
               dict(event_type="tariff", sectors=["shipping", "automotive"])]:
        r = m16(port, ev)
        print(f"{ev['event_type']:16} {r['verdict']:5}  C: {r['C']['why']:28}  A: {r['A']['why']}")
    port2 = [dict(symbol="BTC", weight=0.5, sector="加密", asset_class="crypto"),
             dict(symbol="KO", weight=0.5, sector="必需消费", asset_class="us_equity", beta=0.55)]
    print()
    r = m16(port2, dict(event_type="monetary", sectors=["monetary policy"]))
    print(f"{'BTC+KO monetary':16} {r['verdict']:5}  C: {r['C']['why']}  A: {r['A']['why']}")
