"""两个已知陷阱的复核 + 新旧数据一致性。"""
import sys, os, csv, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib as L

rep = {}

# --- 陷阱1：单位切换点 ---
sw = {}
for s in L.CRYPTO:
    rows = L.load_funding_raw(s)
    cut = L.detect_cutover(rows)
    ih = L.funding_interval_hours(rows, cut)
    # 旧规则：首个 >=3 条/日
    from collections import Counter
    cnt = Counter(t[:10] for t, _ in rows)
    days = sorted(cnt)
    old_rule = next((d for d in days if cnt[d] >= 3), None)
    # 该日在新检测下的实际首个新单位时刻
    sw[s] = dict(detected=cut, interval_h=ih, old_rule_day=old_rule,
                 old_rule_wrong=bool(old_rule and cut and old_rule < cut[:10]))
    # 旧规则会把哪些值放大 100 倍
    if old_rule and cut and old_rule < cut[:10]:
        bad = [(t, v) for t, v in rows if t[:10] == old_rule and t < cut]
        sw[s]["mislabeled"] = [(t, v, round(v*100, 4)) for t, v in bad]
rep["cutover"] = sw

# --- 归一后跨切换点连续性 ---
cont = {}
for s in L.CRYPTO:
    f00, fmax, meta = L.load_funding(s)
    cut = meta["cutover"][:10]
    ds = sorted(f00)
    pre = [abs(f00[d]) for d in ds if d < cut][-30:]
    post = [abs(f00[d]) for d in ds if d >= cut][:30]
    cont[s] = dict(interval_h=meta["interval_h"], cutover=meta["cutover"],
                   med_pre=round(float(np.median(pre)), 5) if pre else None,
                   med_post=round(float(np.median(post)), 5) if post else None,
                   ratio=round(float(np.median(post)/np.median(pre)), 3) if pre and post and np.median(pre)>0 else None,
                   mode_pre=round(float(max(set(np.round(pre,4)), key=list(np.round(pre,4)).count)), 5) if pre else None)
rep["continuity_30d"] = cont

# --- 陷阱2：币本位换算的时点。open[d] 应等于 close[d-1] ---
px = {}
for s in ["BTC", "ETH", "SOL", "DOGE", "TRUMP"]:
    b = L.load_bars(s)
    o, c = b["open"], b["close"]
    rel = np.abs(o[1:] - c[:-1]) / c[:-1]
    px[s] = dict(n=len(rel), median_rel_diff=float(np.median(rel)),
                 p99=float(np.quantile(rel, .99)), max=float(rel.max()))
rep["open_vs_prev_close"] = px

# --- 新旧数据一致性（4 只沿用） ---
eq = {}
OLD = "/Users/ming/project/alva/backtest/data/derivatives"
for s in ["BTC", "ETH", "SOL", "DOGE"]:
    old = {}
    for ln in open(f"{OLD}/fr_{s}.csv"):
        t, v = ln.strip().split(","); old[t[:16]] = float(v)
    new = {t: v for t, v in L.load_funding_raw(s)}
    inter = set(old) & set(new)
    diff = [k for k in inter if abs(old[k]-new[k]) > 1e-12]
    oldoi = {}
    for ln in open(f"{OLD}/oi_{s}.csv"):
        t, v = ln.strip().split(","); oldoi[t[:10]] = float(v)
    newoi = L.load_oi(s)
    ioi = set(oldoi) & set(newoi)
    doi = [k for k in ioi if abs(oldoi[k]-newoi[k]) > 1e-6]
    eq[s] = dict(fund_old=len(old), fund_new=len(new), fund_common=len(inter), fund_mismatch=len(diff),
                 only_old=sorted(set(old)-set(new))[:5], only_new=sorted(set(new)-set(old))[:5],
                 oi_old=len(oldoi), oi_new=len(newoi), oi_common=len(ioi), oi_mismatch=len(doi))
rep["old_vs_new_data"] = eq

print(json.dumps(rep, ensure_ascii=False, indent=1))
