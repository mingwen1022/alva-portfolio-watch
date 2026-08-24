"""生成 M18 抽取的 alva 脚本（payload 内联，避免 --args 的命令行长度限制）。

抽样规则先写死再机械执行，不看结果挑样本：
  A1  Tier A（22 账号）M17 路 —— 全量。PO1/PO2 的直接场景
  A2  Tier A 仅 M24 路 —— 固定种子随机抽 N2。PO3 场景 + 宏观路的 fact/rhet 对照
  B1  媒体层 7 账号 M17 路 —— 固定种子随机抽 N3。分层报告的第二层

每个 alva run 跑 BATCHES_PER_RUN 批，每批 15 条（官方蓝图口径）。
"""
import os, sys, json, gzip, random, argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20260819
BATCH = 15
PORTFOLIO = ["NVDA", "AMD", "MSFT"]

JS_TEMPLATE = r"""// M18 specificity 抽取 · 六层校验 · 自动生成，勿手改
const { ask } = require("@alva/alvaask");

const PORTFOLIO = %PORTFOLIO%;
const BATCHES = %BATCHES%;

const SYS = "You are a strict information-extraction engine for a financial alerting pipeline. "
  + "You output JSON only. No prose, no explanation, no markdown commentary.";

const EVENT_TYPES = ["tariff","export-control","regulation","personnel","geopolitical","monetary","other"];
const DIRECTIONS = ["bullish","bearish","mixed","neutral"];
const SPECS = ["factual","rhetorical"];

function buildPrompt(items, errNote) {
  let p = "";
  p += "Task: for EACH post below, extract a structured record. This is a classification task, not a summary.\n\n";
  p += "specificity is the ONLY field that gates the alert. It measures whether the post contains ACTIONABLE CONTENT, ";
  p += "NOT whether the post is important.\n";
  p += "  factual    = satisfies ANY of: (a) contains a concrete number (rate, amount, quota, date, percentage); ";
  p += "(b) states an effective time (effective immediately / starting <date> / as of ...); ";
  p += "(c) names a portfolio company or its specific product (" + PORTFOLIO.join(", ") + ", Nvidia, AMD, Microsoft); ";
  p += "(d) announces a COMPLETED action (signed, approved, revoked, imposed, sanctioned, banned, filed, published).\n";
  p += "  rhetorical = everything else: intent (considering / may / will / plans to), opinion, praise, blame, ";
  p += "vague generalities with no concrete object.\n\n";
  p += "specificity_evidence MUST be a VERBATIM contiguous substring copied character-for-character from that post's text. ";
  p += "Copy punctuation exactly as it appears (curly apostrophes, dashes, ampersands). Do not fix typos, do not translate, ";
  p += "do not shorten with ellipsis, and NEVER join two separate fragments. Keep it under 120 characters. ";
  p += "If specificity is rhetorical, quote the phrase that shows it is rhetorical.\n";
  p += "tickers: ONLY tickers from this portfolio " + JSON.stringify(PORTFOLIO) + ". Use [] if none are named.\n";
  p += "direction is the direction of the EVENT itself, not of any single holding.\n\n";
  p += "Output: a JSON array with EXACTLY one object per input id, ids echoed exactly, same set, no extras:\n";
  p += '[{"id":"<id>","event_type":"tariff|export-control|regulation|personnel|geopolitical|monetary|other",';
  p += '"objects":{"countries":[],"sectors":[],"tickers":[]},';
  p += '"direction":"bullish|bearish|mixed|neutral","specificity":"factual|rhetorical",';
  p += '"specificity_evidence":"<verbatim substring>",';
  p += '"dedup_key":{"topic":"<short-kebab-topic>","direction":"<same as direction>","object":"<short-kebab-object>"}}]\n\n';
  if (errNote) p += "Your previous answer was rejected. Fix exactly this: " + errNote + "\n\n";
  p += "POSTS:\n";
  for (const it of items) {
    p += "id=" + it.id + "\ntext=\"\"\"" + it.text + "\"\"\"\n\n";
  }
  p += "Return the JSON array now.";
  return p;
}

// ---------- L1 剥 markdown 包装 ----------
function stripFence(s) {
  if (!s) return { s: "", stripped: false };
  let t = String(s).trim();
  const m = t.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (m) return { s: m[1].trim(), stripped: true };
  const a = t.indexOf("["), b = t.lastIndexOf("]");
  if (a > 0 && b > a) return { s: t.slice(a, b + 1), stripped: true };
  return { s: t, stripped: false };
}

function fold(x) {
  return String(x)
    .replace(/[\u2018\u2019\u201A\u201B\u2032\u02BC]/g, "'")
    .replace(/[\u201C\u201D\u201E\u2033]/g, '"')
    .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g, "-")
    .replace(/[\u2026]/g, "...")
    .replace(/[\u00A0\u2007\u202F\u200B\u200C\u200D\uFEFF]/g, " ")
    .replace(/&amp;/g, "&");
}
function norm(x) { return fold(x).replace(/\s+/g, " ").trim().toLowerCase(); }

// ---------- L5 谓词（registry M18 的四条判据，纯代码可判） ----------
const RE_NUM = /\d/;
const RE_DATE = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b/i;
const RE_EFF = /\b(effective|effective immediately|starting|begins|beginning|as of|takes effect|deadline|by the end of|no later than)\b/i;
const RE_CO = /\b(NVDA|AMD|MSFT|Nvidia|Microsoft)\b/;
const RE_DONE = /\b(signed|approved|revoked|imposed|sanctioned|banned|enacted|issued|announced|filed|published|passed|ratified|terminated|suspended|lifted|granted|denied|finalized|rescinded)\b/i;
function l5strict(ev) { return RE_NUM.test(ev) || RE_DATE.test(ev) || RE_EFF.test(ev) || RE_CO.test(ev); }
function l5full(ev) { return l5strict(ev) || RE_DONE.test(ev); }

// ---------- L2–L5 校验 ----------
function validate(items, arr) {
  const byId = {}; for (const it of items) byId[it.id] = it;
  const errs = [];
  const bad = {};                       // id -> 第一条错误
  const rawlab = {};
  function fail(id, layer, msg, o) { if (!bad[id]) bad[id] = { layer: layer, msg: msg }; if (o && SPECS.indexOf(o.specificity) >= 0) rawlab[id] = { specificity: o.specificity, ev: String(o.specificity_evidence || "").slice(0, 200), event_type: o.event_type, direction: o.direction }; errs.push(layer + ":" + id + ":" + msg); }

  if (!Array.isArray(arr)) return { fatal: "L2 output is not a JSON array", bad: bad, errs: errs, ok: [], rawlab: rawlab };
  const seen = {};
  const ok = [];
  for (const o of arr) {
    if (!o || typeof o !== "object" || !o.id) { errs.push("L2:?:missing id"); continue; }
    const id = String(o.id);
    if (!byId[id]) { errs.push("L2:" + id + ":unknown id"); continue; }
    if (seen[id]) { fail(id, "L2", "duplicate id", o); continue; }
    seen[id] = 1;
    const src = byId[id].text;
    // L2 schema + 枚举
    if (SPECS.indexOf(o.specificity) < 0) { fail(id, "L2", "specificity must be factual|rhetorical", o); continue; }
    if (EVENT_TYPES.indexOf(o.event_type) < 0) { fail(id, "L2", "event_type out of enum", o); continue; }
    if (DIRECTIONS.indexOf(o.direction) < 0) { fail(id, "L2", "direction out of enum", o); continue; }
    if (!o.objects || typeof o.objects !== "object") { fail(id, "L2", "objects missing", o); continue; }
    if (!o.dedup_key || !o.dedup_key.topic) { fail(id, "L2", "dedup_key.topic missing", o); continue; }
    const ev = o.specificity_evidence == null ? "" : String(o.specificity_evidence);
    if (!ev) { fail(id, "L2", "specificity_evidence empty", o); continue; }
    // L3 引文逐字
    let quoteMode = "exact";
    if (src.indexOf(ev) < 0) {
      if (fold(src).indexOf(fold(ev)) >= 0) { quoteMode = "typographic"; }
      else if (norm(src).indexOf(norm(ev)) >= 0) { quoteMode = "normalized"; }
      else { fail(id, "L3", "specificity_evidence \"" + ev.slice(0, 90) + "\" is not a contiguous substring of that post; copy it character-for-character", o); continue; }
    }
    // L4 持仓约束
    let tk = (o.objects.tickers || []).map(function (x) { return String(x).toUpperCase(); });
    const outside = tk.filter(function (x) { return PORTFOLIO.indexOf(x) < 0; });
    if (outside.length) { fail(id, "L4", "tickers outside portfolio: " + outside.join(","), o); continue; }
    // L5 factual 自洽
    const s5 = l5strict(ev), f5 = l5full(ev);
    if (o.specificity === "factual" && !f5) { fail(id, "L5", "labelled factual but evidence has no number/date/effective-time/portfolio-company/completed-action", o); continue; }
    ok.push({ id: id, event_type: o.event_type, direction: o.direction, specificity: o.specificity,
              specificity_evidence: ev, tickers: tk, countries: o.objects.countries || [],
              sectors: o.objects.sectors || [], dedup_key: o.dedup_key,
              quote_mode: quoteMode, l5_strict: s5, l5_full: f5 });
  }
  for (const it of items) if (!seen[it.id]) fail(it.id, "L2", "id missing from output");
  return { fatal: null, bad: bad, errs: errs, ok: ok, rawlab: rawlab };
}

function runBatch(b) {
  const stat = { bid: b.bid, n: b.items.length, calls: 0, fence1: false, fence2: false,
                 parse_fail1: false, parse_fail2: false, errs1: [], errs2: [],
                 first_pass: 0, retry_pass: 0, downgraded: [], ms: 0 };
  const t0 = Date.now();
  let raw1 = null, arr1 = null, raw2keep = null;
  try {
    const r = ask(buildPrompt(b.items, null), { system: SYS, model: "claude-haiku-4-5", effort: "low" });
    stat.calls++;
    raw1 = r && r.text ? String(r.text) : "";
  } catch (e) { stat.errs1.push("ASK:" + String(e).slice(0, 200)); }
  const s1 = stripFence(raw1); stat.fence1 = s1.stripped;
  try { arr1 = JSON.parse(s1.s); } catch (e) { stat.parse_fail1 = true; }
  let v1 = arr1 ? validate(b.items, arr1) : { fatal: "L2 parse failed", bad: {}, errs: ["L2:*:parse failed"], ok: [], rawlab: {} };
  stat.errs1 = stat.errs1.concat(v1.errs);
  stat.first_pass = v1.ok.length;

  let out = v1.ok.slice();
  const done = {}; for (const o of out) done[o.id] = 1;
  const missing = b.items.filter(function (it) { return !done[it.id]; });

  if (missing.length) {
    // L6 重试一次，把具体错误喂回去
    const note = missing.map(function (it) {
      const e = v1.bad[it.id];
      return "id=" + it.id + " -> " + (e ? e.layer + " " + e.msg : "missing from your output");
    }).join(" | ");
    let raw2 = null, arr2 = null;
    try {
      const r2 = ask(buildPrompt(missing, note), { system: SYS, model: "claude-haiku-4-5", effort: "low" });
      stat.calls++;
      raw2 = r2 && r2.text ? String(r2.text) : ""; raw2keep = raw2.slice(0, 40000);
    } catch (e) { stat.errs2.push("ASK:" + String(e).slice(0, 200)); }
    const s2 = stripFence(raw2); stat.fence2 = s2.stripped;
    try { arr2 = JSON.parse(s2.s); } catch (e) { stat.parse_fail2 = true; }
    const v2 = arr2 ? validate(missing, arr2) : { fatal: "L2 parse failed", bad: {}, errs: ["L2:*:parse failed"], ok: [], rawlab: {} };
    stat.errs2 = stat.errs2.concat(v2.errs);
    stat.retry_pass = v2.ok.length;
    for (const o of v2.ok) { out.push(o); done[o.id] = 1; }
    // 再失败 → 降级 rhetorical（保守方向）
    for (const it of missing) {
      if (!done[it.id]) {
        stat.downgraded.push(it.id);
        const rl = (v2 && v2.rawlab && v2.rawlab[it.id]) || (v1.rawlab && v1.rawlab[it.id]) || null;
        out.push({ id: it.id, event_type: rl ? rl.event_type : "other", direction: rl ? rl.direction : "neutral",
                   specificity: "rhetorical",
                   spec_raw: rl ? rl.specificity : null, raw_evidence: rl ? rl.ev : null,
                   fail_layer: (v1.bad[it.id] ? v1.bad[it.id].layer : "L2"),
                   specificity_evidence: "", tickers: [], countries: [], sectors: [],
                   dedup_key: { topic: "unparsed", direction: "neutral", object: "unparsed" },
                   quote_mode: "downgraded", l5_strict: false, l5_full: false, downgraded: true });
      }
    }
  }
  stat.ms = Date.now() - t0;
  stat.raw1 = raw1 ? raw1.slice(0, 40000) : null;
  stat.raw2 = raw2keep;
  return { stat: stat, out: out };
}

(async () => {
  const results = [], stats = [];
  for (const b of BATCHES) {
    const r = runBatch(b);
    stats.push(r.stat);
    for (const o of r.out) results.push(o);
  }
  return { results: results, stats: stats };
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n2", type=int, default=450, help="Tier A 仅 M24 抽样条数")
    ap.add_argument("--n3", type=int, default=1200, help="媒体层 M17 抽样条数")
    ap.add_argument("--per-run", type=int, default=6, help="每个 alva run 跑几批")
    ap.add_argument("--trial", type=int, default=0, help=">0 时只生成前 N 批做小样试跑")
    a = ap.parse_args()

    recs = json.load(gzip.open(os.path.join(BASE, "derived/candidates.json.gz"), "rt", encoding="utf-8"))
    A = [r for r in recs if r["layer"] in ("main18", "cb4")]
    A1 = [r for r in A if r["h17"]]
    A2p = [r for r in A if r["h24"] and not r["h17"]]
    B1p = [r for r in recs if r["layer"] == "media7" and r["h17"]]
    rng = random.Random(SEED)
    A2 = sorted(rng.sample(A2p, min(a.n2, len(A2p))), key=lambda r: r["ts"])
    rng2 = random.Random(SEED + 1)
    B1 = sorted(rng2.sample(B1p, min(a.n3, len(B1p))), key=lambda r: r["ts"])
    for r in A1: r["stratum"] = "A1_tierA_m17"
    for r in A2: r["stratum"] = "A2_tierA_m24only"
    for r in B1: r["stratum"] = "B1_media_m17"
    sel = A1 + A2 + B1
    print(f"A1 Tier A M17 全量 {len(A1)} / A2 Tier A 仅M24 抽 {len(A2)}/{len(A2p)} / B1 媒体 M17 抽 {len(B1)}/{len(B1p)}")

    batches = []
    for i in range(0, len(sel), BATCH):
        chunk = sel[i:i + BATCH]
        batches.append(dict(bid=f"b{len(batches):04d}",
                            items=[dict(id=r["cid"], text=r["text"]) for r in chunk]))
    if a.trial:
        batches = batches[:a.trial]
    print(f"共 {len(batches)} 批（{BATCH} 条/批）→ {-(-len(batches)//a.per_run)} 次 alva run")

    jobdir = os.path.join(BASE, "llmjobs" if not a.trial else "llmjobs_trial")
    os.makedirs(jobdir, exist_ok=True)
    for f in os.listdir(jobdir):
        os.remove(os.path.join(jobdir, f))
    nrun = 0
    for i in range(0, len(batches), a.per_run):
        grp = batches[i:i + a.per_run]
        js = (JS_TEMPLATE.replace("%PORTFOLIO%", json.dumps(PORTFOLIO))
                         .replace("%BATCHES%", json.dumps(grp, ensure_ascii=False)))
        with open(os.path.join(jobdir, f"run_{nrun:03d}.js"), "w", encoding="utf-8") as f:
            f.write(js)
        nrun += 1
    meta = {r["cid"]: dict(stratum=r["stratum"], layer=r["layer"], handle=r["handle"],
                           ts=r["ts"], m17=bool(r["h17"]), m24=bool(r["h24"]),
                           ctype=r["ctype"], t0_trust=r["t0_trust"]) for r in sel}
    with gzip.open(os.path.join(BASE, "derived/llm_meta.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"生成 {nrun} 个 run 文件 → {jobdir}")


if __name__ == "__main__":
    main()
