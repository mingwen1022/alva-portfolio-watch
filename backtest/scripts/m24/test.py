import re,os,sys,importlib.util
from collections import Counter
spec=importlib.util.spec_from_file_location("wl", os.path.join(os.path.dirname(__file__),"wordlist.py"))
wl=importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
def compile_group(g): return [(re.compile(r"\b"+p+r"\b" if not p.startswith(r"\b") else p, 0 if cs else re.I), p) for p,cs in g]
C={k:compile_group(v) for k,v in wl.GROUPS.items()}
ALL=[x for v in C.values() for x in v]
def m24(t): return [p for rx,p in ALL if rx.search(t)]

M17=["AI","artificial intelligence","chip","chips","semiconductor","semiconductors","data center","datacenter",
     "export control","export controls","tariff","tariffs","China","GPU","Nvidia","AMD","Microsoft","cloud","foundry","TSMC","wafer"]
P17=[re.compile(r"\b"+re.escape(w)+r"\b", 0 if (w.isupper() and len(w)<=4) else re.I) for w in M17]
def m17(t): return any(r.search(t) for r in P17)

D="/Users/ming/project/alva/backtest/data/social"
rows=[]
for fn in os.listdir(D):
    if not fn.endswith(".tsv"): continue
    for line in open(os.path.join(D,fn),encoding="utf-8"):
        p=line.rstrip("\n").split("\t")
        if len(p)>=3: rows.append(p[2])
n=len(rows)
h24=[t for t in rows if m24(t)]; h17=[t for t in rows if m17(t)]
both=[t for t in rows if m24(t) and m17(t)]
only24=[t for t in rows if m24(t) and not m17(t)]
print(f"语料 {n} 条（⚠️ 按 tariff/nvidia/semiconductor/export-control 检索所得，有循环偏差）\n")
print(f"M17 命中          {len(h17):>6}  {len(h17)/n:>6.1%}")
print(f"M24 命中          {len(h24):>6}  {len(h24)/n:>6.1%}")
print(f"两者都命中        {len(both):>6}  {len(both)/n:>6.1%}   → 走 M17 路（相关性已确定）")
print(f"仅 M24 命中       {len(only24):>6}  {len(only24)/n:>6.1%}   → 走 M24 路（待市场证实）⭐ 这是新增的覆盖")
print(f"两者都不中        {n-len(h24)-len(h17)+len(both):>6}  {(n-len(h24)-len(h17)+len(both))/n:>6.1%}   → 丢弃\n")
print("用户举的五个例子，M24 能否接住：")
EX={"关税":r"\btariffs?\b","战争":r"\bwar\b|\binvasion\b","加息":r"rate hikes?|raise rates?|hiking rates?",
    "降息":r"rate cuts?|cut rates?|lower rates?","霍尔木兹海峡":r"\bhormuz\b"}
print(f"  {'主题':14}{'语料内':>8}{'M17 保留':>10}{'M24 保留':>10}{'合计覆盖':>10}")
for k,pat in EX.items():
    rx=re.compile(pat,re.I); hit=[t for t in rows if rx.search(t)]
    a=sum(1 for t in hit if m17(t)); b=sum(1 for t in hit if m24(t))
    u=sum(1 for t in hit if m17(t) or m24(t))
    print(f"  {k:14}{len(hit):>8}{a/len(hit) if hit else 0:>9.0%}{b/len(hit) if hit else 0:>10.0%}{u/len(hit) if hit else 0:>10.0%}")
print("\n触发最频繁的 M24 词（看是否有噪声词）：")
c=Counter(p for t in h24 for p in m24(t))
for p,k in c.most_common(14): print(f"  {k:>6}  {p}")
print("\n仅 M24 命中的样例（M17 接不住、M24 接住的）：")
for t in only24[:5]: print(f"  · {t[:130]}")
