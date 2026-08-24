# -*- coding: utf-8 -*-
"""L5 · 收三个判官的票，合成判决。

⚠️ **合票规则是这一层最容易做错的地方。**

三个判官各判一个角度（来源支撑 · 措辞越界 · 与数据一致），
所以它们**不是在回答同一个问题**——不能按「三票取多数」合。

    ❌ 多数决   三个里两个说 pass 就算过
                → 一条无源解释只要措辞干净、数字对得上，就 2:1 过了。
                  而无源正是这条产品线一开始要解决的问题
    ✅ 全票制   任一角度 fail 即 fail，并且**记下是哪个角度**
                角度不重叠，所以每一票都是一个独立的否决权

多数决只在**同角度重复投票**时才成立。这里三票各判各的，
把它们当成对同一个问题的三次采样，是把「角度」误当成「重复」。

⚠️ `confidence: low` 的票**不参与否决，但要报出来**。
   「判不了」和「判了通过」是两件事——前者是覆盖缺口，后者是结论。

用法:
    python3 eval/l5_collect.py <judge-A.json> <judge-B.json> <judge-C.json> --out <collected 目录>
"""
import json, sys, pathlib, collections

# ⚠️ `--out` 后面那个值是**目录**，不是判官文件。第一版按「不以 -- 开头」筛，
#    于是把它也当成一票，解析失败后记为「缺席」—— 一个凭空多出来的缺席判官。
#    报出来了所以没酿成错，但那正好说明为什么缺席要报而不是静默跳过。
argv = sys.argv[1:]
OUT = None
if "--out" in argv:
    i = argv.index("--out")
    OUT = pathlib.Path(argv[i + 1]) if i + 1 < len(argv) else None
    argv = argv[:i] + argv[i + 2:]
files = [a for a in argv if not a.startswith("--")]
if not files:
    sys.exit("用法: python3 eval/l5_collect.py <judge-*.json> [--out <collected 目录>]")

votes = []
for f in files:
    p = pathlib.Path(f)
    if not p.exists():
        print(f"⚠️ {f} 不存在 —— 这一票**缺席**，不是通过")
        votes.append({"judge": p.stem, "missing": True, "verdicts": []})
        continue
    try:
        votes.append(json.load(open(p)))
    except Exception as e:
        print(f"⚠️ {f} 解析不了({e}) —— 同样记为缺席")
        votes.append({"judge": p.stem, "missing": True, "verdicts": []})

by_item = collections.defaultdict(list)
for v in votes:
    for r in v.get("verdicts", []):
        by_item[r["id"]].append({"judge": v.get("judge", "?"), **r})

absent = [v.get("judge", "?") for v in votes if v.get("missing")]

items, n_fail = [], 0
for iid, rs in by_item.items():
    # 全票制：任一角度 fail 即 fail
    fails = [r for r in rs if r.get("pass") is False]
    lows = [r for r in rs if r.get("confidence") == "low"]
    detail = []
    for r in fails:
        for k in ("unsupported", "violations", "mismatches"):
            for x in (r.get(k) or []):
                detail.append({"judge": r["judge"], "kind": k,
                               "text": x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)})
        if not any(r.get(k) for k in ("unsupported", "violations", "mismatches")):
            detail.append({"judge": r["judge"], "kind": "reason", "text": r.get("reason", "")})
    verdict = "fail" if fails else ("pass" if rs else "notrun")
    if verdict == "fail":
        n_fail += 1
    items.append({"id": iid, "verdict": verdict,
                  "failedLenses": [r["judge"] for r in fails],
                  "lowConfidence": [r["judge"] for r in lows],
                  "detail": detail, "voters": len(rs)})

out = {"lenses": [v.get("judge") for v in votes], "absentLenses": absent,
       "items": sorted(items, key=lambda x: (x["verdict"] != "fail", x["id"]))}

if OUT:
    (OUT / "l5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"✅ {OUT / 'l5.json'}")

print(f"\nL5 · {len(items)} 道题 · {n_fail} 道不过 · 角度 {len(votes)} 个"
      + (f" · ⚠️ 缺席 {absent}" if absent else ""))
for it in out["items"]:
    mark = {"fail": "❌", "pass": "✅", "notrun": "—"}[it["verdict"]]
    lens = ("  ← " + " / ".join(it["failedLenses"])) if it["failedLenses"] else ""
    low = ("  ⚠️ 判不了: " + " / ".join(it["lowConfidence"])) if it["lowConfidence"] else ""
    print(f"  {mark} {it['id']}{lens}{low}")
    for d in it["detail"][:6]:
        print(f"       [{d['judge'].split('·')[0].strip()}] {d['text'][:110]}")
