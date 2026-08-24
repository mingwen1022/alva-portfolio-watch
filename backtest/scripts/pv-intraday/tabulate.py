"""汇总所有派生量，输出 results-draft.md 用的表格文本 + derived/summary.json"""
import sys, json, numpy as np, collections
BASE = "/private/tmp/claude-501/-Users-ming-project-alva/e875280a-7715-4406-bcc8-b0acf1d65a2c/scratchpad/intraday-run"

def J(n):
    try: return json.load(open(f"{BASE}/derived/{n}.json"))
    except Exception: return None

def q(v, p): return float(np.percentile(v, p)) if len(v) else None

def win_tab(rows, key):
    o = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in rows if x["asset"] == a and x.get(key)]
        if not rr: continue
        ms = [x[key]["mult"] for x in rr]
        o[a] = dict(n=len(rr), passed=sum(x[key]["passed"] for x in rr),
                    pass_rate=round(sum(x[key]["passed"] for x in rr) / len(rr), 3),
                    mult_med=round(float(np.median(ms)), 3),
                    mult_p25=round(q(ms, 25), 3), mult_p75=round(q(ms, 75), 3),
                    blocks_med=round(float(np.median([x[key]["blocks"] for x in rr])), 1),
                    n_trig_med=round(float(np.median([x[key]["n"] for x in rr])), 1))
    return o

S = {}
for tag, f in (("parity", "main_parity"), ("naive", "main_naive")):
    rows = J(f)
    if not rows: continue
    S[tag] = {k: win_tab(rows, k) for k in ("A", "AX", "B", "C")}
    S[tag]["desc"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in rows if x["asset"] == a]
        if not rr: continue
        S[tag]["desc"][a] = dict(
            n=len(rr), thz=rr[0]["thz"], thv=rr[0]["thv"],
            trig_med=float(np.median([x["n_trig_A"] for x in rr])),
            days_trig_med=float(np.median([x["n_days_trig"] for x in rr])),
            days_valid_med=float(np.median([x["n_days_valid"] for x in rr])),
            per_day=round(float(np.median([x["n_trig_A"] / max(x["n_days_valid"], 1) for x in rr])), 3),
            day_rate=round(float(np.median([x["n_days_trig"] / max(x["n_days_valid"], 1) for x in rr])), 4),
            absr_med=round(float(np.median([x["absr_med_at_trig"] for x in rr if x["absr_med_at_trig"]])) * 100, 3),
            rho_med=round(float(np.median([x["rho"] for x in rr if x["rho"] is not None])), 5))
    # 分层
    S[tag]["strata"] = {}
    for field in ("vol_tier", "size_tier", "sector"):
        d = collections.defaultdict(list)
        for x in rows:
            if x["asset"] != "us_equity" or not x.get("A"): continue
            d[x[field]].append(x)
        S[tag]["strata"][field] = {k: dict(n=len(v),
                                           passed=sum(y["A"]["passed"] for y in v),
                                           mult_med=round(float(np.median([y["A"]["mult"] for y in v])), 3))
                                   for k, v in sorted(d.items())}

# 经验零
for f, name in (("null_pt", "null_adopted"), ("null2", "null_grid")):
    n = J(f)
    if not n: continue
    o = collections.defaultdict(list)
    for x in n:
        k = (x.get("thz", "adopted"), x["window"], x["mode"], x["asset"])
        o[k].append(x)
    S[name] = {"|".join(str(y) for y in k): dict(
        n=len(v), fp=round(sum(z["passed"] for z in v) / len(v), 4),
        mult_med=round(float(np.median([z["mult"] for z in v])), 3)) for k, v in sorted(o.items(), key=lambda t: str(t[0]))}

# 安慰剂
p = J("placebo")
if p:
    S["placebo"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in p if x["asset"] == a]
        if not rr: continue
        S["placebo"][a] = {}
        for w in ("A", "B", "C"):
            keys = [k for k in rr[0][w].keys()]
            S["placebo"][a][w] = {}
            for k in keys:
                v = [x[w].get(k) for x in rr if x[w].get(k) is not None]
                if not v: continue
                base = [x[w].get("0") for x in rr if x[w].get(k) is not None and x[w].get("0") is not None]
                S["placebo"][a][w][k] = dict(med=round(float(np.median(v)), 3), n=len(v),
                                             frac_k0_higher=round(float(np.mean([b > y for b, y in zip(base, v)])), 3))

# 日线关系
for f, tag in (("daily_link_parity", "link_parity"), ("daily_link_naive", "link_naive")):
    rows = J(f)
    if not rows: continue
    S[tag] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in rows if x["asset"] == a and x["recall"] is not None]
        if not rr: continue
        rec = [x["recall"] for x in rr]; io = [x["intraday_only"] for x in rr if x["intraday_only"] is not None]
        ld = [x["lead_med_min"] for x in rr if x["lead_med_min"] is not None]
        S[tag][a] = dict(n=len(rr),
                         daily_days_med=float(np.median([x["n_daily"] for x in rr])),
                         intra_days_med=float(np.median([x["n_intra"] for x in rr])),
                         recall_med=round(float(np.median(rec)), 3), recall_p25=round(q(rec, 25), 3), recall_p75=round(q(rec, 75), 3),
                         only_med=round(float(np.median(io)), 3), only_p25=round(q(io, 25), 3), only_p75=round(q(io, 75), 3),
                         lead_med=round(float(np.median(ld)), 0), lead_p25=round(q(ld, 25), 0), lead_p75=round(q(ld, 75), 0))

# 对照
c = J("controls")
if c:
    S["ctrl_eqcount"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in c if x["asset"] == a and x["ctrl"] and all(x["ctrl"][k] for k in ("and", "price", "vol"))]
        if not rr: continue
        S["ctrl_eqcount"][a] = {k: dict(mult_med=round(float(np.median([x["ctrl"][k]["mult"] for x in rr])), 3),
                                        passed=sum(x["ctrl"][k]["passed"] for x in rr), n=len(rr))
                                for k in ("and", "price", "vol")}
        d1 = [x["ctrl"]["and"]["mult"] - x["ctrl"]["price"]["mult"] for x in rr]
        d2 = [x["ctrl"]["and"]["mult"] - x["ctrl"]["vol"]["mult"] for x in rr]
        S["ctrl_eqcount"][a]["paired"] = dict(and_minus_price=round(float(np.median(d1)), 3),
                                              and_gt_price=f"{sum(1 for x in d1 if x>0)}/{len(d1)}",
                                              and_minus_vol=round(float(np.median(d2)), 3),
                                              and_gt_vol=f"{sum(1 for x in d2 if x>0)}/{len(d2)}")
        S["ctrl_eqcount"][a]["p_vol_given_price"] = round(float(np.median([x["ctrl"]["p_vol_given_price"] for x in rr])), 3)
    S["split"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in c if x["asset"] == a and x.get("split")]
        if not rr: continue
        same = sum(1 for x in rr if x["split"]["前半"]["thz"] == x["split"]["后半"]["thz"])
        S["split"][a] = dict(n=len(rr), same=same, same_rate=round(same / len(rr), 3),
                             first_med=float(np.median([x["split"]["前半"]["thz"] for x in rr])),
                             second_med=float(np.median([x["split"]["后半"]["thz"] for x in rr])),
                             absdiff_med=float(np.median([abs(x["split"]["后半"]["thz"] - x["split"]["前半"]["thz"]) for x in rr])),
                             first_dist=dict(sorted(collections.Counter(x["split"]["前半"]["thz"] for x in rr).items())),
                             second_dist=dict(sorted(collections.Counter(x["split"]["后半"]["thz"] for x in rr).items())))
    S["rvol_bar"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in c if x["asset"] == a and x.get("rvol_bar") and x["ctrl"]]
        if not rr: continue
        S["rvol_bar"][a] = dict(n=len(rr), mult_med=round(float(np.median([x["rvol_bar"]["mult"] for x in rr])), 3),
                                passed=sum(x["rvol_bar"]["passed"] for x in rr),
                                n_med=float(np.median([x["rvol_bar"]["n"] for x in rr])),
                                n_cum_med=float(np.median([x["ctrl"]["and"]["n"] for x in rr])))

cs = J("ctrl_samethr")
if cs:
    S["ctrl_samethr"] = {}
    for a in ("us_equity", "crypto"):
        rr = [x for x in cs if x["asset"] == a and all(x["r"][k] for k in ("and", "price", "vol"))]
        if not rr: continue
        S["ctrl_samethr"][a] = {k: dict(n_med=float(np.median([x["r"][k]["n"] for x in rr])),
                                        mult_med=round(float(np.median([x["r"][k]["mult"] for x in rr])), 3),
                                        passed=sum(x["r"][k]["passed"] for x in rr), n=len(rr))
                                for k in ("and", "price", "vol")}
        d1 = [x["r"]["and"]["mult"] - x["r"]["price"]["mult"] for x in rr]
        S["ctrl_samethr"][a]["and_gt_price"] = f"{sum(1 for x in d1 if x>0)}/{len(d1)}"
        S["ctrl_samethr"][a]["and_minus_price"] = round(float(np.median(d1)), 3)

e = J("eth_vs_rth")
if e:
    S["eth_vs_rth"] = {}
    for gk in ("ETH", "RTH"):
        rr = [x[gk] for x in e if gk in x]
        S["eth_vs_rth"][gk] = dict(n=len(rr), K=rr[0]["K"],
                                   present=round(float(np.median([x["present"] for x in rr])), 3),
                                   fill=round(float(np.median([x["fill"] for x in rr])), 3),
                                   sigma_def=round(float(np.median([x["sigma_def"] for x in rr])), 3),
                                   slots_usable=float(np.median([x["slots_usable"] for x in rr])),
                                   n_trig=float(np.median([x["n"] for x in rr])),
                                   mult=round(float(np.median([x["mult"] for x in rr if x["mult"]])), 3),
                                   passed=sum(x["passed"] for x in rr))

r = J("rhythm")
if r: S["rhythm"] = {k: {kk: v[kk] for kk in ("K", "n_sym", "present_rate", "fill_rate",
                                              "vol_ratio_max_min", "absr_ratio_max_min", "vol_share", "absr_rel", "coverage")}
                     for k, v in r.items()}
g = J("grid_A")
if g: S["grid"] = [{k: v for k, v in x.items() if k != "per_sym"} for x in g]
sd = J("slotdist")
if sd: S["slotdist"] = dict(slot_us=sd["slot_us"], slot_cr=sd["slot_cr"])

json.dump(S, open(f"{BASE}/derived/summary.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: (list(v.keys()) if isinstance(v, dict) else f"list[{len(v)}]") for k, v in S.items()}, ensure_ascii=False, indent=1))
