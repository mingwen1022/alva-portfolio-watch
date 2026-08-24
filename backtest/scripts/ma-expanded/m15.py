"""M15 意外度替代。registry 定义：
   z_sur = (a_t - median(a_{t-12..t-1})) / (1.4826 * MAD(a_{t-12..t-1}))

两个口径：
  literal  a_t = 发布的原始值（CPI 是指数点位、NFP 是就业总人数）
  delta    a_t = 该次首发值相对上一次首发值的变化（CPI/GDP 取对数变化×100，NFP 取差分）
"""
import statistics as st
from macro_calendar import first_release

def med(xs): return st.median(xs)

def zsur(seq, k=12):
    """seq: [(release_date, obs_date, a)]，返回 [(rd, od, a, z or None)]"""
    out=[]
    for i,(rd,od,a) in enumerate(seq):
        if i<k: out.append((rd,od,a,None)); continue
        w=[seq[j][2] for j in range(i-k,i)]
        m=med(w); mad=med([abs(x-m) for x in w]); s=1.4826*mad
        out.append((rd,od,a, (a-m)/s if s>0 else None))
    return out

def series(ind, mode):
    cal=first_release(ind)
    if mode=="literal":
        return zsur(cal)
    vals=[]
    import math
    for i in range(1,len(cal)):
        rd,od,a = cal[i]; a0 = cal[i-1][2]
        if ind in ("TOTAL_NONFARM_PAYROLL","UNEMPLOYMENT_RATE","FEDERAL_FUNDS"):
            dv = a-a0
        else:
            dv = math.log(a/a0)*100 if a>0 and a0>0 else None
        if dv is None: continue
        vals.append((rd,od,dv))
    return zsur(vals)

if __name__=="__main__":
    for ind in ["CPI","CORE_CPI","TOTAL_NONFARM_PAYROLL","GDP","REAL_GDP","UNEMPLOYMENT_RATE"]:
        for mode in ["literal","delta"]:
            s=series(ind,mode)
            zs=[abs(z) for *_,z in s if z is not None]
            if not zs: print(ind,mode,"无"); continue
            hit=sum(1 for z in zs if z>=1.5)
            print(f"{ind:22s} {mode:8s} 有效 {len(zs):3d}  |z|≥1.5 命中 {hit:3d} ({hit/len(zs)*100:5.1f}%)  "
                  f"|z| 中位 {med(zs):6.2f}  P90 {sorted(zs)[int(.9*len(zs))]:7.2f}  max {max(zs):8.1f}")
