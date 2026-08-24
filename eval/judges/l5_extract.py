# -*- coding: utf-8 -*-
"""L5 · 抽出需要判断的东西，交给 LLM 判官。

L0–L4 判的都是能用代码判的:字段在不在 · 数对不对 · 页面渲染得出来吗。
**L5 判的是「这句话站不站得住」** —— 归因说的内容有没有来源支撑、
措辞有没有越界（预测方向 · 投资建议 · 编造因果）、语言跟没跟随界面。

⚠️ 这一层的判官是**主 session 的子 agent**，不是 Alva 的 `ask()`：
   一次归因走 `ask()` 要 110–330 credits，三票就是一千。子 agent 不花 Alva credits，
   而且能真正独立开三个 —— 同一个上下文里问三遍不叫三票。

⚠️ 本脚本**不判任何东西**，只负责把题目抽干净。判决由 `eval/l5_collect.py` 收。
   分开是因为中间那一步不在 Python 里 —— 硬要脚本去调 LLM，就会变成
   「脚本假装能判」，而实际判的是别人。

用法:
    python3 eval/l5_extract.py <产物目录>            # 打印题目
    python3 eval/l5_extract.py <产物目录> --json     # 给编排读
"""
import json, sys, pathlib

ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
JSON_OUT = "--json" in sys.argv
if not ROOT or not (ROOT / "data").is_dir():
    sys.exit("用法: python3 eval/l5_extract.py <产物目录>")
D = ROOT / "data"


def j(name):
    p = D / name
    return json.load(open(p)) if p.exists() else None


items = []
skipped = []

# ── 1 · 归因:说的内容有没有来源支撑 ────────────────────────────────
fnd = j("findings.json") or {}
for f in fnd.get("findings", []):
    a = ((f.get("context") or {}).get("attribution")) or {}
    if not a.get("generatedAt"):
        # 「没问过」不是判断题。混进来会让通过率被一堆空卡稀释
        continue
    if not a.get("summary"):
        # 「问过了，没找到」是**合法答案**，也不判 —— 但要记下来，
        # 否则「一条都没判」和「判了都过」在报告里长得一样
        skipped.append({"id": f["id"], "why": "summary 为 null（合法:问过没找到）"})
        continue
    items.append({
        "kind": "attribution",
        "id": f["id"],
        "ask": "这段解释站得住吗",
        "payload": {
            "symbol": f["symbol"],
            "signal": f["signalId"],
            "triggeredAt": f.get("triggeredAt"),
            "measured": f.get("measured"),
            "summary": a.get("summary"),
            "timing": a.get("timing"),
            "sources": [{"title": s.get("title"), "source": s.get("source"),
                         "publishedAt": s.get("publishedAt"), "origin": s.get("origin"),
                         "summary": s.get("summary")}
                        for s in (a.get("sources") or [])],
        },
    })

# ── 2 · 缺口文案:说清楚了「缺什么」还是只说了「没有」────────────────
meta = j("meta.json") or {}
if meta.get("gaps"):
    items.append({
        "kind": "gaps", "id": "meta.gaps", "ask": "这些缺口说清楚了吗",
        "payload": {"gaps": meta["gaps"]},
    })

# ── 3 · 补零告警态:安静的一天有没有说成「什么都没发生」──────────────
scan = fnd.get("scan") or []
if scan:
    items.append({
        "kind": "quiet", "id": "findings.scan", "ask": "安静态表达得对吗",
        "payload": {
            "holdings": len(scan),
            "states": sorted({r.get("state") for r in scan if r.get("state")}),
            "sample": scan[:3],
        },
    })
else:
    skipped.append({"id": "findings.scan", "why": "scan 为空 —— L0 已经报了，不重复判"})

out = {"root": str(ROOT), "items": items, "skipped": skipped}

if JSON_OUT:
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    sys.exit(0)

print(f"L5 题目 {len(items)} 道 · 跳过 {len(skipped)} 道\n")
for it in items:
    print(f"── {it['id']}  ({it['kind']}) · {it['ask']}")
    print(json.dumps(it["payload"], ensure_ascii=False, indent=2)[:900])
    print()
if skipped:
    print("跳过（记下来，不然「没判」会被读成「判了都过」）:")
    for s in skipped:
        print(f"  {s['id']}  —  {s['why']}")
