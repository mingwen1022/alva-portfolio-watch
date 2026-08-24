"""功效分析 —— 这个样本量能检出多大的确认率差。

不用教科书的两比例公式：帖子按 session 日成簇（同一天的帖子共用同一段行情），
独立样本量远小于条数。因此直接**用实际的日簇结构做模拟**：
  ① 取实际拿到窗口的那批帖子的 (day, 类别) 结构
  ② 在零假设 p_f = p_r = p0 与备择 p_f = p0 + δ 下重生成确认与否
  ③ 同一天的帖子共享一个「当日冲击」，用 logit 随机效应把簇内相关做进去
  ④ 用与正式分析同一套按日分块自助判显著
输出：在 80% 功效下能检出的最小 δ。
"""
import os, sys, json, gzip
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def logit(p): return np.log(p / (1 - p))
def expit(x): return 1 / (1 + np.exp(-x))


def sim_power(days, isfact, p0, delta, tau, nsim=400, nboot=800, seed=7):
    """days: 每条帖子的日簇 id；isfact: 是否 factual；tau: 日随机效应的 logit 标准差"""
    rng = np.random.default_rng(seed)
    ud, inv = np.unique(days, return_inverse=True)
    D = len(ud)
    a0, a1 = logit(p0), logit(min(0.97, p0 + delta))
    sig = 0
    for _ in range(nsim):
        u = rng.normal(0, tau, D)[inv]
        p = expit(np.where(isfact, a1, a0) + u)
        y = (rng.random(len(p)) < p).astype(int)
        # 按日分块自助
        idx_by_day = [np.flatnonzero(inv == i) for i in range(D)]
        diffs = np.empty(nboot)
        ok = 0
        for b in range(nboot):
            pick = rng.integers(0, D, D)
            ii = np.concatenate([idx_by_day[i] for i in pick])
            f = y[ii][isfact[ii]]; r = y[ii][~isfact[ii]]
            if len(f) >= 5 and len(r) >= 5:
                diffs[ok] = f.mean() - r.mean(); ok += 1
        if ok < 100:
            continue
        d = np.sort(diffs[:ok])
        lo, hi = d[int(0.025 * ok)], d[int(0.975 * ok)]
        if lo > 0 or hi < 0:
            sig += 1
    return sig / nsim


def observed_structure(key="P_crypto"):
    lab = json.load(gzip.open(f"{BASE}/derived/m18_full.json.gz", "rt", encoding="utf-8"))
    meta = json.load(gzip.open(f"{BASE}/derived/llm_meta.json.gz", "rt", encoding="utf-8"))
    conf = {r["cid"]: r for r in json.load(gzip.open(f"{BASE}/derived/confirm.json.gz", "rt", encoding="utf-8"))}
    days, isf = [], []
    for o in lab:
        cid = o["id"]
        if cid not in meta or cid not in conf:
            continue
        c = conf[cid].get(key)
        if not c:
            continue
        days.append(c["day"]); isf.append(o["spec_llm"] == "factual")
    return np.array(days), np.array(isf, bool)


def main():
    for key, p0 in (("P_crypto", 0.27), ("P_semi", 0.15), ("NVDA", 0.14)):
        try:
            days, isf = observed_structure(key)
        except FileNotFoundError:
            print("先跑 collect_llm.py"); return
        if len(days) < 20:
            print(f"{key}: 有窗口样本 {len(days)}，太少，跳过"); continue
        D = len(np.unique(days))
        print(f"\n{key}: n={len(days)}（factual {isf.sum()} · rhetorical {(~isf).sum()}）· 日簇 {D} · 底数 p0={p0:.0%}")
        for tau in (0.0, 0.6):
            row = []
            for delta in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
                pw = sim_power(days, isf, p0, delta, tau, nsim=300, nboot=600)
                row.append((delta, pw))
            s = "  ".join(f"δ={d:.0%}:{p:.0%}" for d, p in row)
            print(f"  日内相关 τ={tau}:  {s}")


if __name__ == "__main__":
    main()
