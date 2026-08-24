"""M16 持仓敏感度映射的独立复核。

M16 断言：CPI/FOMC 类事件对「beta>1.2 或加密占比>20%」的组合更重要。
单名组合下退化为：beta>1.2 的股票 + 全部加密 = 高敏感；其余 = 低敏感。

两个检验：
  ① 逐标的倍数按组分（n=16 个标的），置换检验
  ② 逐日配对（n=78 个发布日，功效更高）：每日 高敏感组均值 − 低敏感组均值，整块自助
"""
import statistics as st, random
from ma_engine import *
from macro_calendar import first_release
from run_ma import universe, window, trig_from_dates, ANN

LO,HI="2020-01-14","2026-08-12"
SEED2=20260819

def norm_V(s, T, lo, hi):
    """归一化 V：除以该标的自己的非触发日中位数"""
    Tset=set(T)
    N=[s["V"][i] for i in range(lo,hi+1) if i not in Tset and s["V"][i] is not None]
    base=st.median(N)
    return base

def run(indname, rds, shift=0):
    U=universe()
    per={}; norm={}
    for sym,s in U.items():
        if sym=="SPY": continue
        lo,hi=window(s,LO,HI)
        T=[i for i in trig_from_dates(s,rds,shift) if lo<=i<=hi]
        base=norm_V(s,T,lo,hi)
        vs=[s["V"][i] for i in T if s["V"][i] is not None]
        if len(vs)<8: continue
        per[sym]=st.median(vs)/base
        norm[sym]=(s,base,dict(zip([s["dates"][i] for i in T],[s["V"][i] for i in T])))
    hi_g=[k for k in per if U[k]["cls"]=="加密" or (U[k]["beta"] or 0)>1.2]
    lo_g=[k for k in per if k not in hi_g]
    mh=st.mean([per[k] for k in hi_g]); ml=st.mean([per[k] for k in lo_g])
    print(f"\n=== M16 检验 · {indname} ===")
    print(f"高敏感组 ({len(hi_g)}): {', '.join(sorted(hi_g))}")
    print(f"低敏感组 ({len(lo_g)}): {', '.join(sorted(lo_g))}")
    print(f"逐标的倍数 高敏感均值 {mh:.4f} · 低敏感均值 {ml:.4f} · 差 {mh-ml:+.4f} ({(mh/ml-1)*100:+.1f}%)")
    # ① 置换检验（标的层）
    keys=list(per); rng=random.Random(SEED2); obs=mh-ml; cnt=0; NP=20000
    for _ in range(NP):
        rng.shuffle(keys)
        a=keys[:len(hi_g)]; b=keys[len(hi_g):]
        if abs(st.mean([per[k] for k in a])-st.mean([per[k] for k in b]))>=abs(obs): cnt+=1
    print(f"① 标的层置换检验 p = {cnt/NP:.3f}  (n={len(keys)} 个标的)")
    # ② 逐日配对
    days=sorted(set().union(*[set(v[2]) for v in norm.values()]))
    diffs=[]
    for d in days:
        a=[norm[k][2][d]/norm[k][1] for k in hi_g if d in norm[k][2]]
        b=[norm[k][2][d]/norm[k][1] for k in lo_g if d in norm[k][2]]
        if len(a)>=4 and len(b)>=2: diffs.append(st.mean(a)-st.mean(b))
    if diffs:
        rng2=random.Random(SEED2); reps=[]
        for _ in range(4000):
            samp=[diffs[rng2.randrange(len(diffs))] for _ in diffs]
            reps.append(st.median(samp))
        reps.sort()
        print(f"② 逐日配对差（高−低，各自已按自身基准归一）中位 {st.median(diffs):+.4f} "
              f"95% [{reps[100]:+.4f}, {reps[3900]:+.4f}]  n={len(diffs)} 日")
    # 相关性
    bs=[(U[k]["beta"],per[k]) for k in per if U[k]["cls"]=="股票" and U[k]["beta"] is not None]
    bs.sort()
    def rank(xs):
        o=sorted(range(len(xs)), key=lambda i:xs[i]); r=[0]*len(xs)
        for p,i in enumerate(o): r[i]=p
        return r
    rb=rank([x[0] for x in bs]); rm=rank([x[1] for x in bs])
    n=len(bs); dsum=sum((rb[i]-rm[i])**2 for i in range(n))
    rho=1-6*dsum/(n*(n*n-1))
    print(f"③ 股票内 beta 与倍数的 Spearman 相关 {rho:+.3f} (n={n})")
    print("   逐标的：", " ".join(f"{k}(β{U[k]['beta']:.2f}){per[k]:.2f}" if U[k]['beta'] else f"{k}(币){per[k]:.2f}" for k in sorted(per, key=lambda x:-(U[x]['beta'] or 0))))

if __name__=="__main__":
    run("CPI 发布当日", [rd for rd,_,_ in first_release("CPI")], 0)
    run("CPI 发布前 1 日 (MA1)", [rd for rd,_,_ in first_release("CPI")], -1)
    run("NFP 发布当日", [rd for rd,_,_ in first_release("TOTAL_NONFARM_PAYROLL")], 0)
