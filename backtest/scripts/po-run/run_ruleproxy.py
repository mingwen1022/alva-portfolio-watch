"""规则代理跑全量 10,757 条候选（0 credits），并在有 LLM 标签的子集上量它的精确率/召回率。

registry M18 的 factual 四条判据里，前三条纯正则可判：
  ① 含具体数值（税率·金额·配额·日期）  ② 含生效时点  ③ 直接点名持仓公司或其产品
只有第四条「宣告已完成动作」需要语义 —— 但它也能用动词表近似。
  rule3  = ①∨②∨③              纯机检，不需要任何语义
  rule4  = ①∨②∨③∨④（动词表）  registry 四条判据的正则近似
  tight  = 数值与政策工具词 ±60 字符内共现（results-phase3-po §1.2 试过的那条）
"""
import os, sys, json, gzip
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ruleproxy as R

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_DONE = R.RE_DONE


def rule3(t):
    return bool(R.RE_NUM.search(t) or R.RE_MON.search(t) or R.RE_EFF.search(t) or R.RE_CO.search(t))


def rule4(t):
    return bool(rule3(t) or RE_DONE.search(t))


def main():
    recs = json.load(gzip.open(f"{BASE}/derived/candidates.json.gz", "rt", encoding="utf-8"))
    out = {}
    for r in recs:
        t = r["text"]
        out[r["cid"]] = dict(rule3=rule3(t), rule4=rule4(t), tight=R.rule_tight(t), mid=R.rule_mid(t),
                             intent=bool(R.RE_INTENT.search(t)))
    with gzip.open(f"{BASE}/derived/ruleproxy.json.gz", "wt", encoding="utf-8") as f:
        json.dump(out, f)
    for k in ("rule3", "rule4", "mid", "tight"):
        p = np.mean([v[k] for v in out.values()])
        print(f"{k:6} 判为 factual 的比例（全部 {len(out)} 条候选）  {p:.1%}")
    # 分层
    from collections import defaultdict
    g = defaultdict(list)
    for r in recs:
        lay = r["layer"]
        path = "M17" if r["h17"] else "M24only"
        g[(lay, path)].append(out[r["cid"]])
    print()
    for k in sorted(g):
        v = g[k]
        print(f"  {k[0]:8} {k[1]:8} n={len(v):>5}  rule3 {np.mean([x['rule3'] for x in v]):>6.1%}"
              f"  rule4 {np.mean([x['rule4'] for x in v]):>6.1%}  mid {np.mean([x['mid'] for x in v]):>6.1%}"
              f"  tight {np.mean([x['tight'] for x in v]):>6.1%}")


if __name__ == "__main__":
    main()
