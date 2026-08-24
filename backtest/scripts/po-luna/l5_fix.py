"""L5 词表修正 + 全量重校验。纯本地，不调用任何模型。
修三个已验证的缺陷：RE_DONE 词表不全 · RE_CO 大小写敏感 · RE_EFF 只认短语。"""
import re, json, gzip, glob, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import m18lib as M

# ── 修正后的三条正则 ──
RE_CO2 = re.compile(r"\b(NVDA|AMD|MSFT|NVIDIA|MICROSOFT)\b", re.I)        # 大小写不敏感
RE_EFF2 = re.compile(r"\b(effective|immediately|starting|begins?|beginning|as of|"
                     r"takes? effect|deadline|by the end of|no later than|"
                     r"today|tonight|this week|next week)\b", re.I)
RE_DONE2 = re.compile(r"\b("
    r"signed|approved|revoked|imposed|sanctioned|banned|enacted|issued|announced|filed|"
    r"published|passed|ratified|terminated|suspended|lifted|granted|denied|finalized|rescinded|"
    # 补：物理/军事/司法/交易的已完成动作
    r"shot down|struck|hit|seized|blocked|halted|stopped|closed|opened|reopened|forced|"
    r"launched|fired|attacked|destroyed|captured|detained|arrested|released|freed|"
    r"raised|cut|lowered|hiked|slashed|reached|agreed|rejected|vetoed|overturned|upheld|"
    r"resigned|fired|appointed|nominated|confirmed|removed|ousted|"
    r"delayed|postponed|extended|expired|withdrew|withdrawn|exited|entered"
    r")\b", re.I)

def l5_fixed(ev):
    e = M.fold(str(ev))
    return bool(M.RE_NUM.search(e) or M.RE_DATE.search(e) or RE_EFF2.search(e)
                or RE_CO2.search(e) or RE_DONE2.search(e))

def main():
    P = "/private/tmp/claude-501/-Users-ming-project-alva/0df8725f-0825-44ee-a82f-06d4d5ebba72/scratchpad/porun2"
    cand = json.load(gzip.open("backtest/data/po-derived/candidates.json.gz"))
    tmap = {c["cid"]: c["text"] for c in cand}
    # 取每个 id 的最新 raw 记录（pass2 覆盖 pass1）
    best = {}
    for stage in ("pass1", "pass2"):
        for fp in sorted(glob.glob(f"{P}/raw/{stage}/*.json")):
            d = json.load(open(fp, encoding="utf-8"))
            for r in (d.get("records") or []):
                if isinstance(r, dict) and r.get("id"): best[r["id"]] = r
    out, stats = [], {"total":0,"L2":0,"L3":0,"L5_old":0,"L5_new":0,"pass":0}
    for cid, r in best.items():
        stats["total"] += 1
        txt = tmap.get(cid, "")
        ev  = str(r.get("specificity_evidence") or "")
        rec = {"id": cid,
               "event_type": r.get("event_type"), "direction": r.get("direction"),
               "specificity_llm": r.get("specificity"),
               "specificity_evidence": ev,
               "tickers": (r.get("objects") or {}).get("tickers", []),
               "countries": (r.get("objects") or {}).get("countries", []),
               "sectors": (r.get("objects") or {}).get("sectors", []),
               "dedup_key": r.get("dedup_key")}
        # L2
        if (r.get("event_type") not in M.EVENT_TYPES or r.get("direction") not in M.DIRECTIONS
                or r.get("specificity") not in M.SPECS):
            stats["L2"] += 1; rec["verdict"] = "L2_fail"; rec["specificity"] = "rhetorical"
            out.append(rec); continue
        # L3
        if not ev.strip() or M.norm(ev) not in M.norm(txt):
            stats["L3"] += 1; rec["verdict"] = "L3_fail"; rec["specificity"] = "rhetorical"
            out.append(rec); continue
        # L5 —— 新旧都算，便于对照
        old_ok = M.l5full(M.fold(ev)); new_ok = l5_fixed(ev)
        rec["l5_old"], rec["l5_new"] = old_ok, new_ok
        if r.get("specificity") == "factual":
            if not old_ok: stats["L5_old"] += 1
            if not new_ok: stats["L5_new"] += 1
            rec["specificity"] = "factual" if new_ok else "rhetorical"
            rec["verdict"] = "pass" if new_ok else "L5_fail"
        else:
            rec["specificity"] = "rhetorical"; rec["verdict"] = "pass"
        stats["pass"] += (rec["verdict"] == "pass")
        out.append(rec)
    json.dump(out, gzip.open("backtest/data/po-labels/m18_l5fixed.json.gz", "wt", encoding="utf-8"),
              ensure_ascii=False)
    from collections import Counter
    c = Counter(r["specificity"] for r in out)
    print(f"重校验 {stats['total']} 条")
    print(f"  L2 失败        {stats['L2']:>5}")
    print(f"  L3 失败        {stats['L3']:>5}")
    print(f"  L5 拦截 旧词表  {stats['L5_old']:>5}")
    print(f"  L5 拦截 新词表  {stats['L5_new']:>5}   ← 修正后")
    print(f"  救回           {stats['L5_old']-stats['L5_new']:>5}")
    print(f"\n最终 specificity: factual {c['factual']} ({c['factual']/len(out):.1%}) · rhetorical {c['rhetorical']} ({c['rhetorical']/len(out):.1%})")

if __name__ == "__main__": main()
