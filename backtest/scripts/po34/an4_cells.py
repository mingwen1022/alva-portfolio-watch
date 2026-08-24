"""逐单元检验：registry PO4 表里那四格，加位置匹配安慰剂、平移安慰剂、多重比较门槛。"""
import sys, json, collections
import numpy as np
from scipy import stats
sys.path.insert(0, "/private/tmp/claude-501/-Users-ming-project-alva/f5d399ea-f89c-4132-a4bf-c526d9b8ad65/scratchpad/po34")
import polib, confgrid
from an1_theme import to_ep, blockboot

SHIFTS = [-7 * k for k in range(1, 26)]
ETS = ["export-control", "monetary", "tariff", "geopolitical", "regulation", "personnel", "other"]

recs, cp = polib.load()
ev = polib.dedup_events(recs)
G = confgrid.Grid()
eps0 = np.array([to_ep(r["ts"]) for r in ev])
et = np.array([r["etype"] for r in ev])
days = np.array([r["day"] for r in ev])
lay = np.array([r["layer"] for r in ev])
half = np.array([polib.half(r) for r in ev])


def cellstat(port, mask_arm, mask_pool, eps, boot=True, nb=2000):
    v, c = G.query(port, eps)
    vv = v & mask_pool
    if vv.sum() < 40:
        return None
    y = c[vv].astype(float); a = mask_arm[vv]; d = days[vv]
    if a.sum() < 10 or (~a).sum() < 10:
        return None
    dd = float(y[a].mean() - y[~a].mean())
    out = dict(n=int(vv.sum()), n1=int(a.sum()), r1=float(y[a].mean()), r0=float(y[~a].mean()),
               d=dd, days1=int(len(set(d[a]))))
    if boot:
        bb = blockboot(d, y, a, nboot=nb)
        out["lo"] = float(np.percentile(bb, 2.5)); out["hi"] = float(np.percentile(bb, 97.5))
        out["p_boot"] = float(2 * min((bb <= 0).mean(), (bb >= 0).mean()))
        out["pass"] = bool(out["lo"] > 0)
    return out


CRY = ["B:加密", "H:HC1", "H:HC2", "H:HC3", "H:HC4"]
SEMI = ["B:科技"]
print("=" * 78)
print("① registry PO4 表四格 —— 逐半段复核（层：全部）")
print("=" * 78)
cells = [("export-control", "B:科技"), ("export-control", "B:加密"),
         ("monetary", "B:科技"), ("monetary", "B:加密"),
         ("tariff", "B:科技"), ("tariff", "B:加密"),
         ("geopolitical", "B:科技"), ("geopolitical", "B:加密")]
tbl = {}
for e, p in cells:
    row = []
    for hn in ("H1", "H2", "全期"):
        pool = np.ones(len(ev), bool) if hn == "全期" else (half == hn)
        r = cellstat(p, et == e, pool, eps0)
        row.append(r)
    tbl[f"{e}|{p}"] = row
    s = f"{e:16} {p:8}"
    for hn, r in zip(("H1", "H2", "全期"), row):
        s += f" | {hn} " + (f"Δ={r['d']*100:+5.1f}pp n={r['n1']:>4} CI[{r['lo']*100:+5.1f},{r['hi']*100:+5.1f}] p={r['p_boot']:.4f}" if r else "--")
    print(s)

print()
print("=" * 78)
print("② monetary → 加密：跨 5 个不同加密组合的可转移性（H1 / H2 分开）")
print("=" * 78)
for p in CRY:
    s = f"  {p:8}"
    for hn in ("H1", "H2"):
        r = cellstat(p, et == "monetary", half == hn, eps0)
        s += f" | {hn} Δ={r['d']*100:+5.2f}pp CI[{r['lo']*100:+5.2f},{r['hi']*100:+5.2f}] {'✅' if r['pass'] else '  '}" if r else " | --"
    print(s)

print()
print("=" * 78)
print("③ 平移安慰剂：monetary → 加密（B:加密）在 25 个位移日历上的 Δ 分布")
print("=" * 78)
obs = cellstat("B:加密", et == "monetary", np.ones(len(ev), bool), eps0)
nul = []
for sh in SHIFTS:
    r = cellstat("B:加密", et == "monetary", np.ones(len(ev), bool), eps0 + sh * 86400, boot=False)
    if r:
        nul.append(r["d"])
nul = np.array(nul)
print(f"  实测 Δ = {obs['d']*100:+.2f}pp   安慰剂 Δ 均值 {nul.mean()*100:+.2f}pp  标准差 {nul.std()*100:.2f}pp  "
      f"范围 [{nul.min()*100:+.2f},{nul.max()*100:+.2f}]")
print(f"  安慰剂中 ≥ 实测 的比例 {np.mean(nul >= obs['d']):.1%}  （n={len(nul)}）")

print()
print("=" * 78)
print("④ 位置匹配安慰剂：零信息的日历位置规则能拿到多少「通过」")
print("=" * 78)
import datetime as dt
dts = [dt.datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ") for r in ev]
dom = np.array([d.day for d in dts]); wd = np.array([d.weekday() for d in dts])
hr = np.array([d.hour for d in dts])
mlen = np.array([[31,28,31,30,31,30,31,31,30,31,30,31][d.month-1] for d in dts])
pos = dom / mlen
rules = {}
rules["月内前三分之一"] = pos <= 1/3
rules["月内中三分之一"] = (pos > 1/3) & (pos <= 2/3)
rules["月内后三分之一"] = pos > 2/3
rules["月末最后5日"] = (mlen - dom) < 5
rules["月初前5日"] = dom <= 5
for i, nmm in enumerate(["周一", "周二", "周三", "周四", "周五"]):
    rules[nmm] = wd == i
rules["盘前时段(UTC<14)"] = hr < 14
rules["午后(UTC>=18)"] = hr >= 18
basis = [p for p in G.names() if p.startswith("B:")]
tot = 0; pas = 0
print(f"  {'规则':16} {'通过/组合数':>12}  Δ 中位")
for nm, m in rules.items():
    rs = [cellstat(p, m, np.ones(len(ev), bool), eps0, nb=800) for p in basis]
    rs = [r for r in rs if r]
    k = sum(1 for r in rs if r["pass"])
    tot += len(rs); pas += k
    print(f"  {nm:16} {k:>5}/{len(rs):<6}  {np.median([r['d'] for r in rs])*100:+6.2f}pp")
print(f"  合计 零信息位置规则通过率 {pas}/{tot} = {pas/tot:.1%}   ← 这是「通过比例」的位置类经验零")

print()
print("=" * 78)
print("⑤ 多重比较门槛")
print("=" * 78)
print(f"  探索性矩阵 7 事件类型 × 12 部门组合 = 84 格；Bonferroni α = 0.05/84 = {0.05/84:.2e}")
print(f"  加上 3 个层 × 2 个半段的读法，实际检验总数 84×3×2 = 504；α = {0.05/504:.2e}")
json.dump({k: [x for x in v] for k, v in tbl.items()}, open("an4_cells.json", "w"), ensure_ascii=False, indent=1)
