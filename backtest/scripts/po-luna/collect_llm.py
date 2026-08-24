"""收集 alva run 的 M18 输出 → derived/m18_labels.json.gz + derived/m18_raw.json.gz
并统计六层校验各抓到多少、首轮/重试通过率、实际调用次数。"""
import os, sys, json, gzip, glob
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
OUT = os.path.join(BASE, "out")


def read(dirs):
    labels, raws, stats = {}, [], []
    for d in dirs:
        for f in sorted(glob.glob(f"{BASE}/{d}/run_*.json") + glob.glob(f"{BASE}/{d}/rt_*.json")):
            try:
                j = json.load(open(f))
            except Exception:
                continue
            if j.get("status") != "completed" or not j.get("result"):
                continue
            r = json.loads(j["result"])
            for s in r["stats"]:
                s["src"] = os.path.basename(f)
                s["duration_ms"] = j["stats"].get("duration_ms")
                raws.append(dict(bid=s["bid"], src=s["src"], raw1=s.pop("raw1", None), raw2=s.pop("raw2", None)))
                stats.append(s)
            for o in r["results"]:
                labels[o["id"]] = o          # 后来的覆盖先前的（重试批次在后）
    return labels, raws, stats


def main():
    dirs = sys.argv[1:] or ["rawmain", "rawmain_retry"]
    labels, raws, stats = read(dirs)
    calls = sum(s["calls"] for s in stats)
    n = sum(s["n"] for s in stats)
    fp = sum(s["first_pass"] for s in stats)
    rp = sum(s["retry_pass"] for s in stats)
    dg = sum(len(s["downgraded"]) for s in stats)
    lay1 = Counter(); lay2 = Counter()
    for s in stats:
        for e in s["errs1"]:
            lay1[e.split(":")[0]] += 1
        for e in s["errs2"]:
            lay2[e.split(":")[0]] += 1
    print(f"批次 {len(stats)} · 实际调用 {calls} · 条目 {n}")
    print(f"首轮通过 {fp}/{n} = {fp/max(n,1):.1%} · 重试再通过 {rp} · 仍失败 {dg}")
    print("首轮各层拦下：", dict(lay1))
    print("重试轮各层拦下：", dict(lay2))
    print("markdown fence 命中：", sum(1 for s in stats if s["fence1"]), "/", len(stats))
    print("引文模式：", dict(Counter(o.get("quote_mode") for o in labels.values())))
    print("specificity：", dict(Counter(o["specificity"] for o in labels.values())))
    with gzip.open(f"{DERIV}/m18_labels.json.gz", "wt", encoding="utf-8") as f:
        json.dump(list(labels.values()), f, ensure_ascii=False)
    with gzip.open(f"{DERIV}/m18_raw.json.gz", "wt", encoding="utf-8") as f:
        json.dump(raws, f, ensure_ascii=False)
    with open(f"{DERIV}/m18_stats.json", "w") as f:
        json.dump(stats, f, indent=1, ensure_ascii=False)
    print(f"→ {len(labels)} 条标签落盘")


if __name__ == "__main__":
    main()
