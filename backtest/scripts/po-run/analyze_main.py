"""主分析：P_fact vs P_rhet · 规则代理对照 · 全量规则代理外推 · 底数对照。

读法三件套：
  ① 与「随机时刻的确认率」这个底数比 —— |AR_z|≥2 OR RVOL≥2 本身就有 12–27% 的无条件触发率
  ② 差值区间按 session 日分块自助 —— 同一天的帖子共用市场结果，不是独立样本
  ③ 分层报 —— LLM 标签只买得起 Tier A 22 账号；媒体层只走规则代理
"""
import os, sys, json, gzip
import numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED, NBOOT = 20260819, 4000
KEYS = [("NVDA", "NVDA"), ("AMD", "AMD"), ("MSFT", "MSFT"),
        ("P_semi", "半导体组合"), ("P_crypto", "加密组合"), ("P_defensive", "防御组合")]
# selfcheck_market.py 量出的无条件底数（2026-01→08 全部窗口）
BASERATE = {"NVDA": 0.116, "AMD": 0.150, "MSFT": 0.231, "P_semi": 0.128,
            "P_crypto": 0.207, "P_defensive": 0.155}


def load():
    lab = {o["id"]: o for o in json.load(gzip.open(f"{BASE}/derived/m18_full.json.gz", "rt", encoding="utf-8"))}
    meta = json.load(gzip.open(f"{BASE}/derived/llm_meta.json.gz", "rt", encoding="utf-8"))
    conf = {r["cid"]: r for r in json.load(gzip.open(f"{BASE}/derived/confirm.json.gz", "rt", encoding="utf-8"))}
    rp = json.load(gzip.open(f"{BASE}/derived/ruleproxy.json.gz", "rt", encoding="utf-8"))
    return lab, meta, conf, rp


def boot_diff(items, key, seed=SEED, nboot=NBOOT):
    """items: [(day, is_fact, confirmed)]；按日分块自助"""
    if not items:
        return None
    days = sorted({d for d, _, _ in items})
    byday = {d: [] for d in days}
    for d, f, c in items:
        byday[d].append((f, c))
    nf = sum(f for _, f, _ in items); nr = len(items) - nf
    if nf == 0 or nr == 0:
        return None
    pf = np.mean([c for _, f, c in items if f]); pr = np.mean([c for _, f, c in items if not f])
    rng = np.random.default_rng(seed)
    D = len(days); diffs = []
    for _ in range(nboot):
        pick = rng.integers(0, D, D)
        F, R = [], []
        for i in pick:
            for f, c in byday[days[i]]:
                (F if f else R).append(c)
        if len(F) >= 5 and len(R) >= 5:
            diffs.append(np.mean(F) - np.mean(R))
    diffs = np.sort(np.array(diffs))
    if len(diffs) < 200:
        return dict(pf=float(pf), pr=float(pr), diff=float(pf - pr), lo=np.nan, hi=np.nan,
                    nf=int(nf), nr=int(nr), D=D)
    return dict(pf=float(pf), pr=float(pr), diff=float(pf - pr),
                lo=float(diffs[int(0.025 * len(diffs))]), hi=float(diffs[int(0.975 * len(diffs))]),
                nf=int(nf), nr=int(nr), D=D)


def rows_for(cids, labelfn, conf, key):
    out = []
    for cid in cids:
        c = conf.get(cid, {}).get(key)
        if not c:
            continue
        lb = labelfn(cid)
        if lb is None:
            continue
        out.append((c["day"], bool(lb), bool(c["c"])))
    return out


def main():
    lab, meta, conf, rp = load()
    cids = [c for c in meta if c in lab]
    real = cids
    print(f"抽样 {len(meta)} 条 · 拿到标签 {len(cids)}")
    print("stratum：", dict(Counter(meta[c]["stratum"] for c in real)))
    print("LLM 原标签 spec_llm：", dict(Counter(lab[c]["spec_llm"] for c in real)))
    print("流水线标签 spec_pipe（过不了 L5 的 factual 降级）：", dict(Counter(lab[c]["spec_pipe"] for c in real)))
    for st in ("S1_m17", "S2_m24only"):
        sub = [c for c in real if meta[c]["stratum"] == st]
        f1 = sum(1 for c in sub if lab[c]["spec_llm"] == "factual")
        f2 = sum(1 for c in sub if lab[c]["spec_pipe"] == "factual")
        print(f"  {st:12} n={len(sub):>4}  LLM factual {f1} = {f1/max(len(sub),1):>5.1%}   流水线 factual {f2} = {f2/max(len(sub),1):>5.1%}")
    print("event_type：", dict(Counter(lab[c]["event_type"] for c in real).most_common()))
    print("direction：", dict(Counter(lab[c]["direction"] for c in real).most_common()))

    print("\n" + "=" * 92)
    print("一、P_fact vs P_rhet（LLM 标签 · Tier A 22 账号 · 2026-01→08）")
    print("=" * 92)
    for LK, LN in (("spec_llm", "LLM 原标签"), ("spec_pipe", "流水线标签（L5 降级后）")):
      print(f"\n@@@ 标签口径 = {LN}")
      for st, name in (("all", "全部（M17 + 仅M24）"), ("S1_m17", "S1 · M17 路（PO1/PO2 的场景）"),
                     ("S2_m24only", "S2 · 仅 M24 路（PO3 的场景）")):
        sub = [c for c in real if st == "all" or meta[c]["stratum"] == st]
        print(f"\n### {name}   n={len(sub)}")
        print(f"  {'口径':12}{'P_fact':>16}{'P_rhet':>16}{'差':>9}{'95% 区间':>20}{'底数':>8}{'日簇':>6}")
        for key, label in KEYS:
            it = rows_for(sub, (lambda k: (lambda c: lab[c][k] == "factual"))(LK), conf, key)
            d = boot_diff(it, key)
            if not d:
                continue
            ci = f"[{d['lo']:+.1%}, {d['hi']:+.1%}]" if not np.isnan(d["lo"]) else "样本不足"
            print(f"  {label:12}{d['pf']:>9.1%} (n={d['nf']:>3}){d['pr']:>9.1%} (n={d['nr']:>3})"
                  f"{d['diff']:>+9.1%}{ci:>20}{BASERATE.get(key,float('nan')):>8.1%}{d['D']:>6}")

    print("\n" + "=" * 92)
    print("二、规则代理 vs LLM 标签（能不能不调 LLM）")
    print("=" * 92)
    y = np.array([lab[c]["spec_llm"] == "factual" for c in real])
    y2 = np.array([lab[c]["spec_pipe"] == "factual" for c in real])
    print("  参照 = LLM 原标签")
    print(f"  {'代理':8}{'判 factual':>12}{'精确率':>10}{'召回率':>10}{'F1':>8}{'一致率':>10}{'Cohen κ':>10}")
    for v in ("rule3", "rule4", "mid", "tight", "L5regex"):
        x = (np.array([bool(lab[c]["l5_ok"]) for c in real]) if v == "L5regex"
             else np.array([bool(rp[c][v]) for c in real]))
        tp = int((x & y).sum()); fp = int((x & ~y).sum()); fn = int((~x & y).sum()); tn = int((~x & ~y).sum())
        prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9)
        acc = (tp + tn) / len(y)
        pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / len(y) ** 2
        kap = (acc - pe) / max(1 - pe, 1e-9)
        print(f"  {v:8}{x.mean():>12.1%}{prec:>10.1%}{rec:>10.1%}{f1:>8.2f}{acc:>10.1%}{kap:>10.2f}")
    print("  参照 = 流水线标签（L5 降级后）")
    print(f"  {'代理':8}{'判 factual':>12}{'精确率':>10}{'召回率':>10}{'F1':>8}{'一致率':>10}{'Cohen κ':>10}")
    for v in ("rule3", "rule4", "mid", "tight"):
        x = np.array([bool(rp[c][v]) for c in real])
        tp = int((x & y2).sum()); fp = int((x & ~y2).sum()); fn = int((~x & y2).sum()); tn = int((~x & ~y2).sum())
        prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9); acc = (tp + tn) / len(y2)
        pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / len(y2) ** 2
        kap = (acc - pe) / max(1 - pe, 1e-9)
        print(f"  {v:8}{x.mean():>12.1%}{prec:>10.1%}{rec:>10.1%}{f1:>8.2f}{acc:>10.1%}{kap:>10.2f}")

    print("\n" + "=" * 92)
    print("三、规则代理外推到全部 10,757 条候选（0 credits，含媒体层）")
    print("=" * 92)
    allc = list(conf.keys())
    for v in ("mid", "rule4"):
        print(f"\n  代理 = {v}")
        print(f"  {'层':10}{'口径':12}{'P_fact':>16}{'P_rhet':>16}{'差':>9}{'95% 区间':>20}")
        for lay, laysel in (("Tier A 22", lambda c: conf[c]["layer"] in ("main18", "cb4")),
                            ("媒体 7", lambda c: conf[c]["layer"] == "media7"),
                            ("全部", lambda c: True)):
            sub = [c for c in allc if laysel(c)]
            for key, label in (("P_semi", "半导体组合"), ("P_crypto", "加密组合")):
                it = rows_for(sub, lambda c: rp[c][v], conf, key)
                d = boot_diff(it, key, nboot=1500)
                if not d:
                    continue
                ci = f"[{d['lo']:+.1%}, {d['hi']:+.1%}]" if not np.isnan(d["lo"]) else "—"
                print(f"  {lay:10}{label:12}{d['pf']:>9.1%} (n={d['nf']:>4}){d['pr']:>9.1%} (n={d['nr']:>4})"
                      f"{d['diff']:>+9.1%}{ci:>20}")


if __name__ == "__main__":
    main()
