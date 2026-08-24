"""从留存的原始 LLM 输出里把被 L5 拦下的那批标签取回来（0 调用）。

为什么必须取回：L5 是「判 factual 时证据须含数值/生效时点/持仓公司/已完成动作」的规则复核。
被它拦下的 56 条恰恰是**LLM 认为 factual、但没引出客观锚点**的那批 —— 把它们一律降级成
rhetorical，等于用规则把 LLM 的标签改成规则自己的答案，之后再问「LLM 和规则一致吗」
就是自问自答。所以两套标签都要留：
  spec_llm   LLM 自己说的
  spec_pipe  流水线口径（过不了 L5 的 factual 降级为 rhetorical，即 registry 的保守方向）
"""
import os, sys, json, gzip, re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_NUM = re.compile(r"\d")
RE_DATE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
RE_EFF = re.compile(r"\b(effective|starting|begins|beginning|as of|takes effect|deadline|by the end of|no later than)\b", re.I)
RE_CO = re.compile(r"\b(NVDA|AMD|MSFT|Nvidia|Microsoft)\b")
RE_DONE = re.compile(r"\b(signed|approved|revoked|imposed|sanctioned|banned|enacted|issued|announced|filed|published|passed|ratified|terminated|suspended|lifted|granted|denied|finalized|rescinded)\b", re.I)


def l5(ev):
    return bool(RE_NUM.search(ev) or RE_DATE.search(ev) or RE_EFF.search(ev)
                or RE_CO.search(ev) or RE_DONE.search(ev))


def strip_fence(s):
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if m:
        return m.group(1).strip()
    a, b = s.find("["), s.rfind("]")
    return s[a:b + 1] if a >= 0 and b > a else s


def main():
    raws = json.load(gzip.open(f"{BASE}/derived/m18_raw.json.gz", "rt", encoding="utf-8"))
    meta = json.load(gzip.open(f"{BASE}/derived/llm_meta.json.gz", "rt", encoding="utf-8"))
    passed = {o["id"]: o for o in json.load(gzip.open(f"{BASE}/derived/m18_labels.json.gz", "rt", encoding="utf-8"))}
    out, badparse = {}, 0
    for r in raws:
        try:
            arr = json.loads(strip_fence(r["raw1"] or ""))
        except Exception:
            badparse += 1
            continue
        for o in arr:
            cid = str(o.get("id", ""))
            if cid not in meta:
                continue
            ev = str(o.get("specificity_evidence") or "")
            sp = o.get("specificity")
            if sp not in ("factual", "rhetorical"):
                continue
            out[cid] = dict(id=cid, spec_llm=sp, event_type=o.get("event_type"),
                            direction=o.get("direction"), evidence=ev,
                            l5_ok=l5(ev),
                            spec_pipe=("factual" if (sp == "factual" and l5(ev)) else "rhetorical"),
                            passed_full=cid in passed,
                            tickers=[str(x).upper() for x in (o.get("objects") or {}).get("tickers", [])],
                            dedup_key=o.get("dedup_key"))
    print(f"原始输出解析失败的批次 {badparse}/{len(raws)}")
    print(f"抽样 {len(meta)} · 从原始输出取回 {len(out)} 条（六层全过的 {len(passed)}）")
    miss = [c for c in meta if c not in out]
    print(f"两处都没有的 {len(miss)}", miss[:10])
    print("LLM 原标签：", dict(Counter(v['spec_llm'] for v in out.values())))
    print("流水线标签：", dict(Counter(v['spec_pipe'] for v in out.values())))
    n_f = sum(1 for v in out.values() if v["spec_llm"] == "factual")
    n_f5 = sum(1 for v in out.values() if v["spec_llm"] == "factual" and not v["l5_ok"])
    print(f"LLM 判 factual 共 {n_f}，其中 {n_f5} 条（{n_f5/max(n_f,1):.0%}）的引文过不了 L5 → 流水线降级为 rhetorical")
    with gzip.open(f"{BASE}/derived/m18_full.json.gz", "wt", encoding="utf-8") as f:
        json.dump(list(out.values()), f, ensure_ascii=False)
    print("→ derived/m18_full.json.gz")


if __name__ == "__main__":
    main()
