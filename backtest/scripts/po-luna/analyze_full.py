"""全量 M18 标签的主分析。

  §一 标注产出与 specificity 分布（原标签 vs 流水线标签）
  §二 P_fact vs P_rhet —— 全量 10,757 条，逐层逐路径，两种标签口径
  §三 规则代理 vs LLM —— 全量参照
  §四 模型一致性 —— Luna vs Sonnet 5 在 225 条重叠上
  §五 功效 —— 这个样本量能检出多大的差

自助一律**按 session 日分块**：同一天的帖子共用同一段行情，不是独立样本。
"""
import os, sys, json, gzip
import numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

S = os.environ["S"]; ROOT = f"{S}/porun2"
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"
SEED, NBOOT = 20260819, 4000
KEYS = [("NVDA","NVDA"),("AMD","AMD"),("MSFT","MSFT"),
        ("P_semi","半导体组合"),("P_crypto","加密组合"),("P_defensive","防御组合")]
BASERATE = {"NVDA":0.116,"AMD":0.150,"MSFT":0.231,"P_semi":0.128,"P_crypto":0.207,"P_defensive":0.155}


def load():
    cand = {c["cid"]: c for c in json.load(gzip.open(f"{DERIV}/candidates.json.gz","rt",encoding="utf-8"))}
    lab  = {o["id"]: o for o in json.load(gzip.open(f"{ROOT}/out/m18_luna_full.json.gz","rt",encoding="utf-8"))}
    raw  = json.load(open(f"{ROOT}/out/rawlabels.json"))
    conf = {r["cid"]: r for r in json.load(gzip.open(f"{DERIV}/confirm.json.gz","rt",encoding="utf-8"))}
    rp   = json.load(gzip.open(f"{DERIV}/ruleproxy.json.gz","rt",encoding="utf-8"))
    return cand, lab, raw, conf, rp


def boot_diff(days, isf, conf01, nboot=NBOOT, seed=SEED):
    """按日分块自助，向量化：每天预聚合 (nf, cf, nr, cr)，一次重抽只是索引求和。"""
    days = np.asarray(days); isf = np.asarray(isf, bool); y = np.asarray(conf01, float)
    if len(days) == 0: return None
    ud, inv = np.unique(days, return_inverse=True); D = len(ud)
    nf = np.bincount(inv[isf], minlength=D).astype(float)
    cf = np.bincount(inv[isf], weights=y[isf], minlength=D)
    nr = np.bincount(inv[~isf], minlength=D).astype(float)
    cr = np.bincount(inv[~isf], weights=y[~isf], minlength=D)
    NF, NR = nf.sum(), nr.sum()
    if NF < 5 or NR < 5: return None
    pf, pr = cf.sum()/NF, cr.sum()/NR
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, D, size=(nboot, D))
    Nf = nf[idx].sum(1); Cf = cf[idx].sum(1); Nr = nr[idx].sum(1); Cr = cr[idx].sum(1)
    ok = (Nf >= 5) & (Nr >= 5)
    d = Cf[ok]/Nf[ok] - Cr[ok]/Nr[ok]
    if len(d) < 200:
        return dict(pf=pf, pr=pr, diff=pf-pr, lo=np.nan, hi=np.nan, p=np.nan,
                    nf=int(NF), nr=int(NR), D=D)
    ds = np.sort(d)
    p = 2*min((ds <= 0).mean(), (ds >= 0).mean())
    return dict(pf=float(pf), pr=float(pr), diff=float(pf-pr),
                lo=float(ds[int(.025*len(ds))]), hi=float(ds[int(.975*len(ds))]),
                p=float(min(p,1.0)), nf=int(NF), nr=int(NR), D=D)


def rows(cids, factfn, conf, key):
    d,f,c = [],[],[]
    for cid in cids:
        cc = conf.get(cid,{}).get(key)
        if not cc: continue
        v = factfn(cid)
        if v is None: continue
        d.append(cc["day"]); f.append(bool(v)); c.append(1.0 if cc["c"] else 0.0)
    return d,f,c


def kappa(x, y):
    x = np.asarray(x,bool); y = np.asarray(y,bool); n = len(x)
    tp=int((x&y).sum()); fp=int((x&~y).sum()); fn=int((~x&y).sum()); tn=int((~x&~y).sum())
    acc=(tp+tn)/n
    pe=((tp+fp)*(tp+fn)+(fn+tn)*(fp+tn))/n**2
    prec=tp/max(tp+fp,1); rec=tp/max(tp+fn,1)
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,acc=acc,kappa=(acc-pe)/max(1-pe,1e-9),
                prec=prec,rec=rec,f1=2*prec*rec/max(prec+rec,1e-9))


def main():
    cand, lab, raw, conf, rp = load()
    allc = [c for c in cand if c in lab]
    print(f"候选 {len(cand)} · 拿到 M18 标签 {len(allc)} · 首轮原标签 {len(raw)}")

    def path(c):
        r = cand[c]
        return "S1_m17" if r["h17"] else ("S2_m24only" if r["h24"] else "none")
    def tier(c):
        return "TierA" if cand[c]["layer"] in ("main18","cb4") else "media7"

    def sp_raw(c):
        v = raw.get(c)
        return None if v is None else (v["spec_raw"] == "factual")
    def sp_pipe(c):
        return lab[c]["specificity"] == "factual"

    print("\n" + "="*100)
    print("一、标注产出")
    print("="*100)
    print("首轮 LLM 原标签  ", dict(Counter(raw[c]["spec_raw"] for c in allc if c in raw)))
    print("流水线标签（六层校验后）", dict(Counter(lab[c]["specificity"] for c in allc)))
    print("降级条数", sum(1 for c in allc if lab[c].get("downgraded")))
    print("引文模式", dict(Counter(lab[c]["quote_mode"] for c in allc)))
    print("event_type", dict(Counter(lab[c]["event_type"] for c in allc).most_common()))
    print("direction ", dict(Counter(lab[c]["direction"] for c in allc).most_common()))
    print(f"\n{'子集':22}{'n':>7}{'原标签 factual':>18}{'流水线 factual':>18}")
    for nm, sel in (("全部", lambda c: True),
                    ("TierA 22 账号", lambda c: tier(c)=="TierA"),
                    ("媒体 7 账号", lambda c: tier(c)=="media7"),
                    ("S1 · M17 路", lambda c: path(c)=="S1_m17"),
                    ("S2 · 仅 M24 路", lambda c: path(c)=="S2_m24only"),
                    ("TierA · S1", lambda c: tier(c)=="TierA" and path(c)=="S1_m17"),
                    ("TierA · S2", lambda c: tier(c)=="TierA" and path(c)=="S2_m24only")):
        sub=[c for c in allc if sel(c)]
        r1=[c for c in sub if c in raw]
        a=sum(1 for c in r1 if raw[c]["spec_raw"]=="factual")
        b=sum(1 for c in sub if lab[c]["specificity"]=="factual")
        print(f"{nm:22}{len(sub):>7}{a/max(len(r1),1):>17.1%}{b/max(len(sub),1):>17.1%}")

    print("\n" + "="*100)
    print("二、P_fact vs P_rhet（全量 · 两种标签口径 · 按 session 日分块自助 4000 次）")
    print("="*100)
    tab = {}
    for LK, LN, fn in (("raw","LLM 原标签",sp_raw), ("pipe","流水线标签（L5 复核后）",sp_pipe)):
        print(f"\n@@@ 标签口径 = {LN}")
        for nm, sel in (("全部", lambda c: True),
                        ("TierA 22 账号", lambda c: tier(c)=="TierA"),
                        ("媒体 7 账号", lambda c: tier(c)=="media7"),
                        ("TierA · S1 M17 路", lambda c: tier(c)=="TierA" and path(c)=="S1_m17"),
                        ("TierA · S2 仅M24 路", lambda c: tier(c)=="TierA" and path(c)=="S2_m24only")):
            sub=[c for c in allc if sel(c)]
            print(f"\n### {nm}   n={len(sub)}")
            print(f"  {'标的':12}{'P_fact':>17}{'P_rhet':>17}{'差':>9}{'95% 区间':>21}{'p':>8}{'底数':>8}{'日簇':>6}")
            for key,label in KEYS:
                d,f,c = rows(sub, fn, conf, key)
                r = boot_diff(d,f,c)
                if not r: continue
                ci = f"[{r['lo']:+.1%}, {r['hi']:+.1%}]" if not np.isnan(r["lo"]) else "样本不足"
                print(f"  {label:12}{r['pf']:>10.1%} (n={r['nf']:>4}){r['pr']:>10.1%} (n={r['nr']:>4})"
                      f"{r['diff']:>+9.1%}{ci:>21}{r['p']:>8.3f}{BASERATE.get(key,np.nan):>8.1%}{r['D']:>6}")
                tab[(LK,nm,key)] = r

    print("\n" + "="*100)
    print("三、规则代理 vs LLM（全量 10,757 条 —— 上一轮只有 225 条）")
    print("="*100)
    for ref, refname, fn in (("raw","LLM 原标签",sp_raw), ("pipe","流水线标签",sp_pipe)):
        sub=[c for c in allc if fn(c) is not None]
        y=np.array([fn(c) for c in sub],bool)
        print(f"\n  参照 = {refname}   n={len(sub)}   参照判 factual {y.mean():.1%}")
        print(f"  {'代理':10}{'判 factual':>12}{'精确率':>10}{'召回率':>10}{'F1':>8}{'一致率':>10}{'Cohen κ':>10}")
        for v in ("rule3","rule4","mid","tight"):
            x=np.array([bool(rp[c][v]) for c in sub],bool)
            k=kappa(x,y)
            print(f"  {v:10}{x.mean():>12.1%}{k['prec']:>10.1%}{k['rec']:>10.1%}{k['f1']:>8.2f}{k['acc']:>10.1%}{k['kappa']:>10.2f}")
        if ref=="raw":
            x=np.array([bool(raw[c]["l5_ok_raw"]) for c in sub],bool)
            k=kappa(x,y)
            print(f"  {'L5regex':10}{x.mean():>12.1%}{k['prec']:>10.1%}{k['rec']:>10.1%}{k['f1']:>8.2f}{k['acc']:>10.1%}{k['kappa']:>10.2f}")

    print("\n  规则代理换掉 LLM 后，P_fact vs P_rhet 会不会变（同一批候选，同一套自助）")
    print(f"  {'代理':10}{'标的':12}{'P_fact':>17}{'P_rhet':>17}{'差':>9}{'95% 区间':>21}{'p':>8}")
    for v in ("rule3","rule4","mid","tight"):
        for key,label in (("P_semi","半导体组合"),("P_crypto","加密组合")):
            d,f,c = rows(allc, lambda cid: bool(rp[cid][v]), conf, key)
            r = boot_diff(d,f,c)
            if not r: continue
            ci=f"[{r['lo']:+.1%}, {r['hi']:+.1%}]"
            print(f"  {v:10}{label:12}{r['pf']:>10.1%} (n={r['nf']:>4}){r['pr']:>10.1%} (n={r['nr']:>4})"
                  f"{r['diff']:>+9.1%}{ci:>21}{r['p']:>8.3f}")

    json.dump({f"{a}|{b}|{c}": v for (a,b,c),v in tab.items()},
              open(f"{ROOT}/out/pfact_table.json","w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
