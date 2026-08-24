"""从 raw/pass1 的原始输出里取回**首轮 LLM 原标签**（只过 schema，不过 L5）。

区分两个口径：
  spec_raw   首次调用给出的 specificity —— LLM 自己的判断
  spec_pipe  六层校验（含 L5 复核 + 重试 + 降级）之后的流水线标签
两者的差就是「规则复核推翻了多少 LLM 的 factual」。
"""
import os, sys, json, gzip, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m18lib as L

S = os.environ["S"]; ROOT = f"{S}/porun2"

def main():
    raw = {}
    for f in sorted(glob.glob(f"{ROOT}/raw/pass1/*.json")):
        try:
            obj = json.loads(L.strip_fence(open(f).read())[0])
        except Exception:
            continue
        arr = L.coerce_array(obj)
        if not arr: continue
        for o in arr:
            if not isinstance(o, dict): continue
            i = o.get("id")
            if not i or i in raw: continue
            if o.get("specificity") not in L.SPECS: continue
            ev = str(o.get("specificity_evidence") or "")
            raw[i] = {"spec_raw": o["specificity"], "ev_raw": ev[:300],
                      "event_type_raw": o.get("event_type"), "direction_raw": o.get("direction"),
                      "l5_ok_raw": L.l5full(ev)}
    json.dump(raw, open(f"{ROOT}/out/rawlabels.json", "w"), ensure_ascii=False)
    print(f"首轮原标签 {len(raw)} 条")
    from collections import Counter
    print(dict(Counter(v["spec_raw"] for v in raw.values())))

if __name__ == "__main__":
    main()
