"""模型一致性：gpt-5.6-luna（本地 codex）vs Sonnet 5（平台 ask）在 225 条重叠上。

回答「M18 的结论依不依赖模型」。两个口径分开比：
  原标签   两模型首轮各自给出的 specificity（不经 L5）
  流水线   六层校验之后的标签
"""
import os, sys, json, gzip
import numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

S = os.environ["S"]; ROOT = f"{S}/porun2"
DERIV = "/Users/ming/project/alva/backtest/data/po-derived"


def kap(x, y):
    x=np.asarray(x,bool); y=np.asarray(y,bool); n=len(x)
    tp=int((x&y).sum()); fp=int((x&~y).sum()); fn=int((~x&y).sum()); tn=int((~x&~y).sum())
    acc=(tp+tn)/n; pe=((tp+fp)*(tp+fn)+(fn+tn)*(fp+tn))/n**2
    return acc, (acc-pe)/max(1-pe,1e-9), (tp,fp,fn,tn)


def cat_kappa(a, b):
    """多类 Cohen κ"""
    cats = sorted(set(a)|set(b)); n=len(a)
    idx={c:i for i,c in enumerate(cats)}
    M=np.zeros((len(cats),len(cats)))
    for x,y in zip(a,b): M[idx[x],idx[y]]+=1
    po=np.trace(M)/n
    pe=float((M.sum(0)*M.sum(1)).sum())/n**2
    return po,(po-pe)/max(1-pe,1e-9),M,cats


def main():
    son = {o["id"]: o for o in json.load(gzip.open(f"{DERIV}/m18_full.json.gz","rt",encoding="utf-8"))}
    lun = {o["id"]: o for o in json.load(gzip.open(f"{ROOT}/out/m18_luna_full.json.gz","rt",encoding="utf-8"))}
    raw = json.load(open(f"{ROOT}/out/rawlabels.json"))
    ids = [i for i in son if i in lun and i in raw]
    print(f"两模型都标过的重叠 {len(ids)} 条（Sonnet 主跑 {len(son)} · Luna 全量 {len(lun)}）\n")

    print("specificity 分布")
    print(f"  {'口径':22}{'Sonnet 5':>26}{'gpt-5.6-luna':>26}")
    a=[son[i]["spec_llm"] for i in ids]; b=[raw[i]["spec_raw"] for i in ids]
    print(f"  {'原标签':22}{str(dict(Counter(a))):>26}{str(dict(Counter(b))):>26}")
    a2=[son[i]["spec_pipe"] for i in ids]; b2=[lun[i]["specificity"] for i in ids]
    print(f"  {'流水线标签':20}{str(dict(Counter(a2))):>26}{str(dict(Counter(b2))):>26}")

    print("\nspecificity 一致率")
    for nm,x,y in (("原标签 vs 原标签",[v=="factual" for v in a],[v=="factual" for v in b]),
                   ("流水线 vs 流水线",[v=="factual" for v in a2],[v=="factual" for v in b2])):
        acc,k,(tp,fp,fn,tn)=kap(x,y)
        print(f"  {nm:22} 一致 {acc:.1%}  κ {k:.2f}   两者都 factual {tp} · 都 rhetorical {tn} · "
              f"仅 Sonnet {fp} · 仅 Luna {fn}")

    print("\n其余字段（原标签口径）")
    for fld, sk, lk in (("event_type","event_type","event_type_raw"),
                        ("direction","direction","direction_raw")):
        x=[son[i][sk] for i in ids]; y=[raw[i][lk] or "?" for i in ids]
        po,k,M,cats=cat_kappa(x,y)
        print(f"  {fld:12} 一致 {po:.1%}  κ {k:.2f}")
        top=Counter((p,q) for p,q in zip(x,y) if p!=q).most_common(5)
        print(f"    最常见分歧 {top}")

    print("\nL5 复核（判 factual 时证据是否含数值/日期/生效时点/持仓公司/已完成动作）")
    for nm, ok in (("Sonnet 5", [bool(son[i]["l5_ok"]) for i in ids if son[i]["spec_llm"]=="factual"]),
                   ("gpt-5.6-luna", [bool(raw[i]["l5_ok_raw"]) for i in ids if raw[i]["spec_raw"]=="factual"])):
        if ok: print(f"  {nm:14} 判 factual {len(ok)} 条，其中引文过 L5 {sum(ok)} = {np.mean(ok):.1%}")

    # 结论是否随模型改变：把 Sonnet 标签换成 Luna 标签，重跑 P_fact vs P_rhet（同 225 条）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analyze_full import boot_diff
    conf = {r["cid"]: r for r in json.load(gzip.open(f"{DERIV}/confirm.json.gz","rt",encoding="utf-8"))}
    print("\n同一批 225 条上，换模型后 P_fact vs P_rhet 会不会变")
    print(f"  {'模型/口径':26}{'标的':12}{'P_fact':>16}{'P_rhet':>16}{'差':>9}{'95% 区间':>21}")
    for nm, fn in (("Sonnet 5 · 原标签", lambda i: son[i]["spec_llm"]=="factual"),
                   ("Luna · 原标签", lambda i: raw[i]["spec_raw"]=="factual"),
                   ("Sonnet 5 · 流水线", lambda i: son[i]["spec_pipe"]=="factual"),
                   ("Luna · 流水线", lambda i: lun[i]["specificity"]=="factual")):
        for key,label in (("P_semi","半导体组合"),("P_crypto","加密组合")):
            d,f,c=[],[],[]
            for i in ids:
                cc=conf.get(i,{}).get(key)
                if not cc: continue
                d.append(cc["day"]); f.append(fn(i)); c.append(1.0 if cc["c"] else 0.0)
            r=boot_diff(d,f,c)
            if not r: continue
            ci = "[{:+.1%}, {:+.1%}]".format(r["lo"], r["hi"])
            print(f"  {nm:26}{label:12}{r['pf']:>9.1%} (n={r['nf']:>3}){r['pr']:>9.1%} (n={r['nr']:>3})"
                  f"{r['diff']:>+9.1%}{ci:>21}")


if __name__ == "__main__":
    main()
