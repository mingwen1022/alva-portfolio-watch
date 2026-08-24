"""① 采集 → ② M17/M24 粗筛 → ③ M19 L1+L2 浅层去重 → 候选集落盘。

窗口 2026-01-01 → 2026-08-20（coverage-report §一：2026-01 起 88–100% 账号达参照密度；
2025 年缺失非随机，会把市场确认率推高，不掺）。
"""
import os, sys, json, gzip
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pocorpus as P

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "derived")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 20, tzinfo=timezone.utc)


def main():
    rows = P.load()
    print(f"全语料 {len(rows)} 条")
    # L1 去重在全语料上做 —— 这样转推能回溯到语料内最早出现的时刻（近似原帖时间）
    r1 = P.dedup_l1(rows)
    print(f"M19 L1 后 {len(r1)} 条（消掉 {len(rows)-len(r1)}，{1-len(r1)/len(rows):.1%}）")

    win = [r for r in r1 if T0 <= r["ts"] < T1]
    print(f"窗口 2026-01→08 内 {len(win)} 条")

    for r in win:
        r["h17"] = P.m17_hits(r["text"])
        r["h24"] = P.m24_hits(r["text"])
    cand = [r for r in win if r["h17"] or r["h24"]]
    print(f"② 粗筛通过（M17∪M24）{len(cand)} 条 = {len(cand)/len(win):.1%}")

    kept, killed = P.dedup_l2(cand)
    print(f"M19 L2（Jaccard>0.85 / 7 日）后 {len(kept)} 条（再消 {len(killed)}）")

    def layer(h):
        if h in P.LAYER_MAIN: return "main18"
        if h in P.LAYER_CB: return "cb4"
        return "media7"

    from collections import Counter
    c = Counter(layer(r["handle"]) for r in kept)
    print("\n分层：", dict(c))
    for lay in ("main18", "cb4", "media7"):
        sub = [r for r in kept if layer(r["handle"]) == lay]
        n17 = sum(1 for r in sub if r["h17"]); n24 = sum(1 for r in sub if r["h24"])
        only24 = sum(1 for r in sub if r["h24"] and not r["h17"])
        print(f"  {lay:8} {len(sub):>6}  M17 {n17:>5}  M24 {n24:>5}  仅M24 {only24:>5}  批次 {-(-len(sub)//15):>4}")

    # t0 可信度：L1 保留的这条本身是不是 original
    for r in kept:
        r["t0_trust"] = "original" if r["ctype"] == "original" else (
            "in_corpus_earliest" if r["dupes"] else "secondhand")
    print("\nt0 可信度：", dict(Counter(r["t0_trust"] for r in kept)))

    os.makedirs(OUT, exist_ok=True)
    recs = [dict(cid=f"c{i:05d}", ts=r["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), handle=r["handle"],
                 tier=r["tier"], layer=layer(r["handle"]), ctype=r["ctype"], pid=r["pid"],
                 h17=r["h17"], h24=r["h24"], t0_trust=r["t0_trust"],
                 ndup=len(r["dupes"]), text=r["text"][:1500])
            for i, r in enumerate(kept)]
    with gzip.open(os.path.join(OUT, "candidates.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False)
    print(f"\n落盘 {len(recs)} 条 → derived/candidates.json.gz")


if __name__ == "__main__":
    main()
