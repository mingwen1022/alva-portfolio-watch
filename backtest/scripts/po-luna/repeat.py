"""M18 可重复性 —— 用试跑阶段已经付过钱的重复标注量。

试跑期间同一批候选被独立标注了 2–3 次（老校验层 1 次 + 单批计时 1 次 + 硬化后校验层 1 次）。
这批数据本来是调试副产物，正好回答项目一直挂着的那条：
「LLM 判定不稳 —— specificity 在关键样本上 3 次重复出现 2:1 分歧」。
"""
import os, sys, json, glob
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")
SRC = [("raw/trial_000.json", "老校验层"), ("raw/one.json", "老校验层-单批"),
       ("rawtrial/run_000.json", "硬化校验层"), ("rawtrial/run_001.json", "硬化校验层")]


def main():
    runs = defaultdict(dict)      # tag -> cid -> spec
    for path, tag in SRC:
        f = os.path.join(BASE, path)
        if not os.path.exists(f) or os.path.getsize(f) == 0:
            continue
        j = json.load(open(f))
        if j.get("status") != "completed":
            continue
        r = json.loads(j["result"])
        for o in r["results"]:
            runs[path][o["id"]] = ("DOWNGRADED" if o.get("downgraded") else o["specificity"])
    keys = list(runs.keys())
    print("可用重复标注：", {k: len(v) for k, v in runs.items()})
    # 逐 cid 收集
    allc = defaultdict(list)
    for k in keys:
        for cid, s in runs[k].items():
            allc[cid].append((k, s))
    multi = {c: v for c, v in allc.items() if len(v) >= 2}
    print(f"被标注 ≥2 次的候选 {len(multi)}")

    # 只看两轮都给出真实标签（非降级）的
    agree = dis = 0
    pat = Counter()
    for c, v in sorted(multi.items()):
        labs = [s for _, s in v if s != "DOWNGRADED"]
        if len(labs) < 2:
            continue
        if len(set(labs)) == 1:
            agree += 1
        else:
            dis += 1
        pat[tuple(labs)] += 1
    tot = agree + dis
    print(f"两轮及以上均有真实标签的 {tot} 条：一致 {agree}（{agree/max(tot,1):.1%}）· 分歧 {dis}（{dis/max(tot,1):.1%}）")
    print("标签组合分布：", dict(pat))

    # 只比「老校验层 vs 硬化校验层」这一对（不同实现、不同调用）
    a = runs.get("raw/trial_000.json", {}); b = {}
    for k in ("rawtrial/run_000.json", "rawtrial/run_001.json"):
        b.update(runs.get(k, {}))
    both = [c for c in a if c in b and a[c] != "DOWNGRADED" and b[c] != "DOWNGRADED"]
    ag = sum(1 for c in both if a[c] == b[c])
    print(f"\n老校验层 vs 硬化校验层 同 {len(both)} 条：一致 {ag} = {ag/max(len(both),1):.1%}")
    fl = [(c, a[c], b[c]) for c in both if a[c] != b[c]]
    for c, x, y in fl[:12]:
        print(f"  {c}  {x} → {y}")


if __name__ == "__main__":
    main()
