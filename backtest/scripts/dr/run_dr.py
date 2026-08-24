import json, datetime, statistics as st, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dr_engine import *

OUT = {}


def dstr(d):
    return d.isoformat()


def to_dates(ss):
    return sorted(datetime.date.fromisoformat(x) for x in ss)


def run_sym(sym):
    bars = load_bars(sym)
    S = build(sym, bars)
    f00, fmax, brk = load_funding(sym)
    oi = load_oi(sym)
    # 00:00 时刻价格 ≈ 前一日收盘（该日 K 线的 open）。用当日收盘会引入前视。
    px = {S["dates"][i]: S["close"][i - 1] for i in range(1, S["n"])}

    # 只在三套数据都覆盖、且 V 可算的日子上做统计
    Vmap = {}
    for i, d in enumerate(S["dates"]):
        if S["V"][i] is not None:
            Vmap[d] = S["V"][i]
    dates = sorted(Vmap)
    # 数据可用区间：资金费率与 OI 都有
    lo_f, hi_f = min(f00), max(f00)
    lo_o, hi_o = min(oi), max(oi)
    lo = max(lo_f, lo_o, dates[0]); hi = min(hi_f, hi_o, dates[-1])
    dates = [d for d in dates if lo <= d <= hi]
    years = len(dates) / 365.0

    res = dict(sym=sym, span=[lo, hi], days=len(dates), years=round(years, 2),
               fr_break=brk, signals={}, overlap={})

    sigs = {
        "DR1": sig_dr1(f00, dates),
        "DR2": sig_dr2(f00, dates),
        "DR2_nodebounce": sig_dr2(f00, dates, debounce=False),
        "DR3": sig_dr3(oi, dates, px=None),
        "DR3_coin": sig_dr3(oi, dates, px=px),
    }
    # 2026 起 3 次/日：用当日 max|f| 的变体（只作对照，口径不一致）
    sigs["DR1_maxday"] = sig_dr1(fmax, dates)

    dset = set(dates)
    for k, v in sigs.items():
        sigs[k] = v & dset

    base_by = {}
    for k, trig in sigs.items():
        base_vals = [Vmap[d] for d in dates if d not in trig]
        td = [datetime.date.fromisoformat(d) for d in sorted(trig)]
        Vd = {datetime.date.fromisoformat(d): Vmap[d] for d in trig}
        r = ratio_ci(td, Vd, base_vals) if td else None
        res["signals"][k] = dict(n_trig=len(trig), F=round(len(trig) / years, 1) if years else None,
                                 stat=r)
        base_by[k] = base_vals

    # 重叠：先给计数
    A, Bv, C, Cc = sigs["DR1"], sigs["DR2"], sigs["DR3"], sigs["DR3_coin"]
    AB = A | Bv
    res["overlap"] = dict(
        n_DR1=len(A), n_DR2=len(Bv), n_DR3=len(C), n_DR3coin=len(Cc),
        DR1_DR2=dict(both=len(A & Bv), jac=jac(A, Bv)),
        DR1_DR3=dict(both=len(A & C), jac=jac(A, C),
                     p_DR3_given_DR1=round(len(A & C) / len(A), 3) if A else None,
                     p_DR1_given_DR3=round(len(A & C) / len(C), 3) if C else None),
        DR2_DR3=dict(both=len(Bv & C), jac=jac(Bv, C),
                     p_DR3_given_DR2=round(len(Bv & C) / len(Bv), 3) if Bv else None),
        DR12_DR3=dict(both=len(AB & C), jac=jac(AB, C),
                      p_DR3_given_DR12=round(len(AB & C) / len(AB), 3) if AB else None,
                      p_DR12_given_DR3=round(len(AB & C) / len(C), 3) if C else None),
        DR1_DR3coin=dict(both=len(A & Cc), jac=jac(A, Cc)),
        base_rate_DR3=round(len(C) / len(dates), 3),
        base_rate_DR3coin=round(len(Cc) / len(dates), 3),
        lift_DR3_given_DR1=round((len(A & C) / len(A)) / (len(C) / len(dates)), 2) if A and C else None,
        lift_DR3_given_DR12=round((len(AB & C) / len(AB)) / (len(C) / len(dates)), 2) if AB and C else None,
    )
    # 合并信号「杠杆异动」= DR1 ∪ DR2 ∪ DR3
    merged = A | Bv | C
    tdm = to_dates(merged)
    Vdm = {datetime.date.fromisoformat(d): Vmap[d] for d in merged}
    res["merged_DR123"] = dict(n=len(merged), F=round(len(merged) / years, 1),
                               stat=ratio_ci(tdm, Vdm, [Vmap[d] for d in dates if d not in merged]) if tdm else None)

    # 费率分位 —— 阈值合理性的描述统计
    fa = sorted(abs(f00[d]) for d in dates if d in f00)
    res["funding_abs_pct"] = {q: round(fa[int(q / 100 * (len(fa) - 1))], 4) for q in [50, 75, 90, 95, 99, 99.9]} if fa else None
    res["funding_abs_max"] = round(max(fa), 4) if fa else None
    oc = sorted(abs(oi[d] / oi[p] - 1) for d, p in zip(dates[1:], dates[:-1]) if d in oi and p in oi and oi[p] > 0)
    res["oi_chg_pct"] = {q: round(oc[int(q / 100 * (len(oc) - 1))], 4) for q in [50, 75, 90, 95, 99]} if oc else None
    return res, sigs, Vmap, dates


if __name__ == "__main__":
    allres = {}
    for sym in SYMS:
        r, sigs, Vmap, dates = run_sym(sym)
        allres[sym] = r
    print(json.dumps(allres, ensure_ascii=False, indent=1))
