import math, statistics as st, glob, os
def load(p):
    rows=[l.split(',') for l in open(p).read().strip().split('\n')]
    return [(r[0], float(r[1]), float(r[2])) for r in rows]
def prep(d):
    n=len(d); out=[]
    r=[None]+[math.log(d[i][1]/d[i-1][1]) for i in range(1,n)]
    for i in range(n):
        if i<91: continue
        win=r[i-90:i]; med=st.median(win)
        mad=st.median([abs(x-med) for x in win]); sig=1.4826*mad
        if sig<=0: continue
        z=(r[i]-med)/sig
        vmed=st.median([d[j][2] for j in range(i-90,i)])
        out.append((d[i][0], z, d[i][2]/vmed if vmed>0 else 0))
    return out

GRID=[1.5,2.0,2.5,3.0,3.5,4.0]
BANDS=[(1.5,2.5),(2.5,4.0),(4.0,99)]
tot={b:0 for b in BANDS}
cov={g:{b:0 for b in BANDS} for g in GRID}
alldays=0
for f in sorted(glob.glob('cry/*.csv')):
    p=prep(load(f)); alldays+=len(p)
    for _,z,rv in p:
        a=abs(z)
        for b in BANDS:
            if b[0]<=a<b[1]:
                tot[b]+=1
                for g in GRID:
                    if rv>=g: cov[g][b]+=1
print("价格腿已过（|z|≥1.5）的日子里，量能腿也过的比例\n")
print(f"{'θv':>5}", end="")
for b in BANDS: print(f"{'|z| '+str(b[0])+'–'+(str(b[1]) if b[1]<90 else '∞'):>14}", end="")
print(f"{'合计':>10}")
print("─"*62)
for g in GRID:
    print(f"{g:>5}", end="")
    for b in BANDS:
        print(f"{cov[g][b]/tot[b]*100:>13.1f}%", end="")
    s=sum(cov[g].values())/sum(tot.values())*100
    print(f"{s:>9.1f}%")
print()
for b in BANDS:
    lab='|z| '+str(b[0])+'–'+(str(b[1]) if b[1]<90 else '∞')
    print(f"  {lab:<12} 共 {tot[b]:>5} 个交易日")
print(f"\n可评估交易日合计 {alldays}")
