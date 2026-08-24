"""把所有汇总表导出到 out/tables.txt 与 out/summary.csv（供复核）。"""
import json, sys, os, statistics as st
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","out")
M=json.load(open(f"{D}/main.json")); O=json.load(open(f"{D}/overlap.json"))
P=json.load(open(f"{D}/placebo.json")); S=json.load(open(f"{D}/split.json"))
out=[]
def w(x=""): out.append(str(x))
TH1=["0.05","0.075","0.1","0.15","0.2","0.25","0.3","0.4","0.5","0.75","1.0"]
TH3=["0.05","0.1","0.15","0.2","0.3"]
f=lambda x: "%6.3f[%6.3f,%6.3f]%s%5d/%-4d"%(x['mult'],x['lo'],x['hi'],"P" if x['pass_'] else " ",x['n'],x['blocks']) if x else "        -          "
w("### 覆盖 · PV1 自检")
w("%-7s %-11s %-11s %6s %6s %6s | PV1 fwd | PV1 same"%("sym","start","end","fdays","odays","yrs"))
for s,v in M.items():
    m=v['meta']; w("%-7s %-11s %-11s %6d %6d %6.2f | %s | %s"%(s,m['span'][0],m['span'][1],m['fund_days'],m['oi_days'],m['yrs_f'],f(v['PV1']['fwd']),f(v['PV1']['same'])))
for tag,al in (("DR1 fwd","fwd"),("DR1 same","same"),("DR1 nopurge fwd","nopurge_fwd")):
    w(); w("### %s（每格 倍数[区间] P=通过 触发/块）"%tag)
    w("%-7s"%"sym"+"".join("%-21s"%("th="+t) for t in TH1))
    for s,v in M.items():
        w("%-7s"%s+"".join("%-21s"%f(v['DR1'][t].get(al)) for t in TH1))
w(); w("### DR2")
w("%-7s %-21s %-21s %-21s %-21s"%("sym","deb30 fwd","deb30 same","nodeb fwd","nodeb same"))
for s,v in M.items():
    w("%-7s %-21s %-21s %-21s %-21s"%(s,f(v['DR2']['debounce30']['fwd']),f(v['DR2']['debounce30']['same']),f(v['DR2']['nodebounce']['fwd']),f(v['DR2']['nodebounce']['same'])))
for den in ("usd","coin"):
    for al in ("fwd","same","nopurge_fwd","nopurge_same"):
        w(); w("### DR3 %s %s"%(den,al))
        w("%-7s"%"sym"+"".join("%-21s"%("th="+t) for t in TH3))
        for s,v in M.items():
            w("%-7s"%s+"".join("%-21s"%f(v['DR3'][den][t].get(al)) for t in TH3))
w(); w("### 安慰剂平移（倍数）")
KS=["-12","-10","-8","-6","0","6","8","10","12"]
for sig in ["DR1@0.05","DR3usd@0.10","DR3coin@0.10"]:
    w("-- %s"%sig); w("%-7s"%"sym"+"".join("%8s"%k for k in KS))
    for s in P:
        w("%-7s"%s+"".join("%8s"%(("%.3f"%P[s][sig][k]['mult']) if P[s][sig].get(k) else "-") for k in KS))
w(); w("### 半样本（切点 2023-06-01）")
KEYS=["DR1@0.05","DR1@0.075","DR1@0.1","DR1@0.15","DR1@0.2","DR3@0.1"]
w("%-7s"%"sym"+"".join("%-24s"%k for k in KEYS))
for s in S:
    row=""
    for k in KEYS:
        a=S[s]['H1'].get(k); b=S[s]['H2'].get(k)
        g=lambda x: ("%.2f%s"%(x['mult'],"P" if x['pass_'] else "")) if x else "-"
        row+="%-24s"%("H1 %s / H2 %s"%(g(a),g(b)))
    w("%-7s"%s+row)
w(); w("### 重叠（th_DR1=0.05）")
w("%-7s %6s %5s %5s %6s %6s %8s %8s %8s %10s %8s"%("sym","eval","DR1","DR2","DR3","PV1","J13","J12","J23","P3|1U2","lift"))
for s,v in O.items():
    t=v['th0.05']
    w("%-7s %6d %5d %5d %6d %6d %8s %8s %8s %10s %8s"%(s,v['n_eval'],t['DR1'],v['DR2'],v['DR3'],v['PV1'],
        t['DR1_DR3']['jac'],t['DR1_DR2']['jac'],t['DR2_DR3']['jac'],t['U12_DR3']['p_b_given_a'],t['U12_DR3']['lift']))
open(f"{D}/tables.txt","w").write("\n".join(out))
# CSV 主表
import csv
with open(f"{D}/summary.csv","w",newline="") as fh:
    wr=csv.writer(fh)
    wr.writerow(["symbol","yrs","signal","caliber","align","n","blocks","mult","lo","hi","pass"])
    for s,v in M.items():
        y=v['meta']['yrs_f']
        for t in TH1:
            for al in ("fwd","same","nopurge_fwd"):
                r=v['DR1'][t].get(al)
                if r: wr.writerow([s,y,"DR1@%s"%t,"purge" if "nopurge" not in al else "nopurge", al.replace("nopurge_",""),r['n'],r['blocks'],r['mult'],r['lo'],r['hi'],int(r['pass_'])])
        for tag in ("debounce30","nodebounce"):
            for al in ("fwd","same"):
                r=v['DR2'][tag].get(al)
                if r: wr.writerow([s,y,"DR2/%s"%tag,"purge",al,r['n'],r['blocks'],r['mult'],r['lo'],r['hi'],int(r['pass_'])])
        for den in ("usd","coin"):
            for t in TH3:
                for al in ("fwd","same","nopurge_fwd","nopurge_same"):
                    r=v['DR3'][den][t].get(al)
                    if r: wr.writerow([s,y,"DR3%s@%s"%(den,t),"purge" if "nopurge" not in al else "nopurge",al.replace("nopurge_",""),r['n'],r['blocks'],r['mult'],r['lo'],r['hi'],int(r['pass_'])])
print("tables.txt + summary.csv written")
