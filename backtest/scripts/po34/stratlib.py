"""时段分层口径 —— 与「整池对比」并列的第二套口径。

理由：B:科技 的确认率随 slot 从 43.3%（开盘首根）掉到 2.0%（尾盘），跨度 20 倍。
零信息规则「盘前 UTC<14」因此拿到 11/12 通过、Δ +23.9pp。
任何不控制 slot 的事件类型对比都可能只是在测「这类消息几点发」。

分层差 = Σ_k w_k [率(arm,k) − 率(¬arm,k)]，w_k = arm 在 slot k 的占比（MH 型）
"""
import numpy as np
import json

RNG = np.random.default_rng(20260821)
_meta = None


def meta():
    global _meta
    if _meta is None:
        _meta = json.load(open("/private/tmp/claude-501/-Users-ming-project-alva/"
                              "f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34/grid_meta.json"))
    return _meta


def locate(G, port, eps):
    g = G.g[port]; K = meta()[port]["K"]
    pos = np.searchsorted(g["sorted"], eps, side="left")
    inr = pos < len(g["ok"])
    j = np.where(inr, g["ok"][np.clip(pos, 0, len(g["ok"]) - 1)], 0)
    v = g["valid"][j] & inr
    c = g["conf"][j] & v
    k = j % K
    if K > 40:                      # 加密 96 槽 → 并成 8 个 3 小时桶
        k = k // 12
    return v, c, k


def strat_diff(y, a, k):
    """分层差。只用两侧都有样本的层。"""
    num = 0.0; wsum = 0.0
    for kk in np.unique(k):
        m = k == kk
        aa = a[m]
        if aa.sum() == 0 or (~aa).sum() == 0:
            continue
        w = aa.sum()
        num += w * (y[m][aa].mean() - y[m][~aa].mean())
        wsum += w
    return np.nan if wsum == 0 else num / wsum


def strat_cell(G, port, arm, pool, eps, days, boot=True, nboot=1000):
    v, c, k = locate(G, port, eps)
    vv = v & pool
    if vv.sum() < 40:
        return None
    y = c[vv].astype(float); a = arm[vv]; kk = k[vv]; d = days[vv]
    if a.sum() < 10 or (~a).sum() < 10:
        return None
    d0 = strat_diff(y, a, kk)
    if np.isnan(d0):
        return None
    out = dict(n=int(vv.sum()), n1=int(a.sum()), d=float(d0),
               days1=int(len(set(d[a]))), nk=int(len(np.unique(kk))))
    if boot:
        ud, inv = np.unique(d, return_inverse=True)
        idx = [np.flatnonzero(inv == i) for i in range(len(ud))]
        bb = []
        for _ in range(nboot):
            pick = RNG.integers(0, len(ud), len(ud))
            sel = np.concatenate([idx[i] for i in pick])
            x = strat_diff(y[sel], a[sel], kk[sel])
            if not np.isnan(x):
                bb.append(x)
        bb = np.array(bb)
        out["lo"] = float(np.percentile(bb, 2.5)); out["hi"] = float(np.percentile(bb, 97.5))
        out["p_boot"] = float(2 * min((bb <= 0).mean(), (bb >= 0).mean()))
        out["pass"] = bool(out["lo"] > 0)
    return out
