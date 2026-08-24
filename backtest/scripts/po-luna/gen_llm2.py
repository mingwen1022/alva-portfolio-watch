"""M18 抽取 · 预算重设版（硬上限 25 次调用，含重试）。

规则先写死再机械执行，不看结果挑样本：
  分层   ① M17 命中（Tier A 22 账号）   ② 仅 M24 命中（Tier A 22 账号）   各一半
  层内   按时间排序后**等距系统抽样**（起点 = 固定种子取的 0..step-1 之一），不随机挑、不按内容挑
  规模   9 批 × 25 条 = 225 条  → 首轮 9 次调用
  重试   失败项**跨批合并**成 1 个批次，最多 1 次调用（原设计的逐批重试要 2× 调用，预算不允许）
  合计   ≤ 10 次调用

与原设计的差异（预算所迫，必须记录）：
  · 每批 25 条而不是官方蓝图的 15 条 —— 单次调用装更多条目，是把「条/调用」拉满
  · 媒体快讯层 7 个账号**不打 M18 标签**。它们只走 0 credits 的通路（市场确认 · 规则代理）
  · L6 从「逐批重试一次」改为「全局合并重试一次」，再失败不降级而是**标为未标注**并排除，
    降级成 rhetorical 会把失败率直接灌进被测的那个比例里
"""
import os, sys, json, gzip, argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_llm import JS_TEMPLATE                     # noqa: E402  复用六层校验实现

SEED = 20260819
PORTFOLIO = ["NVDA", "AMD", "MSFT"]


def systematic(rows, n, seed):
    """等距系统抽样：按时间排序，步长 = len/n，起点由种子定。"""
    rows = sorted(rows, key=lambda r: r["ts"])
    if len(rows) <= n:
        return rows
    step = len(rows) / n
    import random
    off = random.Random(seed).random()
    idx = sorted({min(len(rows) - 1, int((i + off) * step)) for i in range(n)})
    return [rows[i] for i in idx]


def make_jobs(sel, batch, jobdir, tag="run"):
    os.makedirs(jobdir, exist_ok=True)
    for f in os.listdir(jobdir):
        os.remove(os.path.join(jobdir, f))
    batches = []
    for i in range(0, len(sel), batch):
        chunk = sel[i:i + batch]
        batches.append(dict(bid=f"{tag}b{len(batches):03d}",
                            items=[dict(id=r["cid"], text=r["text"]) for r in chunk]))
    for i, b in enumerate(batches):
        js = (JS_TEMPLATE.replace("%PORTFOLIO%", json.dumps(PORTFOLIO))
                         .replace("%BATCHES%", json.dumps([b], ensure_ascii=False)))
        # 预算版：关掉逐批内部重试（改为全局合并重试）
        js = js.replace("  if (missing.length) {", "  if (false && missing.length) {")
        with open(os.path.join(jobdir, f"{tag}_{i:03d}.js"), "w", encoding="utf-8") as f:
            f.write(js)
    return batches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=225)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--mode", default="main", choices=["main", "retry"])
    a = ap.parse_args()

    recs = json.load(gzip.open(f"{BASE}/derived/candidates.json.gz", "rt", encoding="utf-8"))
    byid = {r["cid"]: r for r in recs}

    if a.mode == "main":
        A = [r for r in recs if r["layer"] in ("main18", "cb4")]
        s1 = [r for r in A if r["h17"]]
        s2 = [r for r in A if r["h24"] and not r["h17"]]
        half = a.n // 2
        p1 = systematic(s1, half, SEED)
        p2 = systematic(s2, a.n - half, SEED + 1)
        for r in p1: r["stratum"] = "S1_m17"
        for r in p2: r["stratum"] = "S2_m24only"
        sel = sorted(p1 + p2, key=lambda r: r["ts"])
        print(f"S1 M17 命中 抽 {len(p1)}/{len(s1)} · S2 仅M24 抽 {len(p2)}/{len(s2)} · 合计 {len(sel)}")
        from collections import Counter
        print("按月：", dict(sorted(Counter(r['ts'][:7] for r in sel).items())))
        print("按账号 top8：", Counter(r['handle'] for r in sel).most_common(8))
        print("按层：", dict(Counter(r['layer'] for r in sel)))
        b = make_jobs(sel, a.batch, f"{BASE}/llmjobs2", "run")
        print(f"→ {len(b)} 批 × {a.batch} 条 = {len(sel)} 条，{len(b)} 次首轮调用")
        meta = {r["cid"]: dict(stratum=r["stratum"], layer=r["layer"], handle=r["handle"],
                               ts=r["ts"], m17=bool(r["h17"]), m24=bool(r["h24"]),
                               ctype=r["ctype"], t0_trust=r["t0_trust"]) for r in sel}
        with gzip.open(f"{BASE}/derived/llm_meta.json.gz", "wt", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    else:
        # 从 rawmain/ 收集失败项，合并成一批
        import glob
        done, need = set(), []
        for f in sorted(glob.glob(f"{BASE}/rawmain/run_*.json")):
            d = json.load(open(f))
            if d.get("status") != "completed":
                continue
            r = json.loads(d["result"])
            for o in r["results"]:
                if not o.get("downgraded"):
                    done.add(o["id"])
        meta = json.load(gzip.open(f"{BASE}/derived/llm_meta.json.gz", "rt", encoding="utf-8"))
        need = [byid[c] for c in meta if c not in done and c in byid]
        print(f"待重试 {len(need)} 条")
        if not need:
            return
        b = make_jobs(need, max(len(need), 1), f"{BASE}/llmjobs2_retry", "rt")
        print(f"→ {len(b)} 批（合并），{len(b)} 次调用")


if __name__ == "__main__":
    main()
