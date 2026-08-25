/* 日频上下文：财报日历（EV4）· 内部人申报（EV1）。
 *
 * 两条都是**一次调用一只标的**，日频，仅美股。
 * ⚠️ 内部人端点计费 1 credit/次/标的 —— 7 只美股就是 7 credits/天。
 *    日线 · 财报日历免费。
 */
const { Feed, feedPath, makeDoc, alertOutput, str, num, messagePresentationField } = require("@alva/feed");
const http   = require("net/http");
const secret = require("secret-manager");
const L     = require("./lib.js");
const alfs   = require("alfs");
const env    = require("env");

const B = "https://data-tools.prd.arrays.org";
/* ⚠️ 从 args 读，不要写死。告警正文末尾的回链指向它 ——
   写死就等于把每个用户的告警都深链到作者那一个 playbook。
   由 `alva deploy create --args '{"root":"…","playbookUrl":"…"}'` 注入。 */
let PLAYBOOK_URL = "";
const WIN = 30;                    // 内部人窗口，天

const feed = new Feed({ path: feedPath("portfolio-watch-context") });
feed.def("alerts", {
  events: alertOutput(makeDoc("Portfolio Watch calendar alert",
    "Holdings reporting earnings within one session", [
      num("date"), str("title"), str("body"), messagePresentationField(),
    ])),
});

(async () => {
await feed.run(async (ctx, args = {}) => {
  const A = Object.assign({}, (env.args || {}), args);
  const ROOT = A.root;
  if (!ROOT) throw new Error(
    "missing args.root — pass the playbook's absolute ALFS path via "
    + "alva deploy create --args '{\"root\":\"/alva/home/<user>/playbooks/<name>\"}'");
  PLAYBOOK_URL = A.playbookUrl || "";
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const H = { Authorization: "Bearer " + jwt };
  const rd = async p => JSON.parse(await alfs.readFile(`${ROOT}/${p}`));
  const wr = (p, o) => alfs.writeFile(`${ROOT}/${p}`, JSON.stringify(o));

  const port = await rd("data/portfolio.json");
  /* 面板上 EV4 那个开关此前不接线 —— 见 producer.js 同处注释。
     日历照查（`symbols/<SYM>.earnings` 照写），只是不再产 finding。 */
  const alertCfg = (await rd("config/alerts.json").catch(() => ({}))).enabled || {};
  const sigOn = id => alertCfg[id] !== false;
  const fj   = await rd("data/findings.json");
  const asOf = String(fj.asOf || "").slice(0, 10);
  const nowS = Math.floor(Date.now() / 1000);
  const errs = [], log = {};

  const us = port.holdings.filter(h => h.assetClass === "us_equity");
  const cr = port.holdings.filter(h => h.assetClass === "crypto");
  const ev4 = [], dr1 = [];

  /* ⚠️ 端点给的 sentiment 是**标签串**，契约要数值。在这里转 ——
     交给界面的话它会拿 Math.abs("Somewhat-Bullish") 去比 0.35，结果是 NaN，
     而 NaN 的所有比较都是 false：着色规则不会报错，它只是静默地永不生效。 */
  const SENT = { "Bearish": -0.7, "Somewhat-Bearish": -0.35, "Neutral": 0,
                 "Somewhat-Bullish": 0.35, "Bullish": 0.7 };
  const MINREL = 0.80;
  const newsSeen = {};             // URL → 条目，宽链去重用
  let newsRaw = 0;

  /* 端点给 "2026-08-21 21:07:12-00" —— 空格分隔、两位偏移量，不是合法 ISO 8601。
     照原样落盘的话 new Date() 在部分浏览器上返回 Invalid Date，页面印出破折号，
     看起来像端点没给时间。 */
  const isoTime = t => {
    if (!t) return null;
    let x = String(t).trim().replace(" ", "T");
    if (x.length >= 3 && "+-".includes(x[x.length - 3])
        && /^\d+$/.test(x.slice(-2))) x += ":00";
    return x;
  };


  /* ⚠️ **美股和加密都取。** 我第一版只循环美股 —— 而 CLAUDE.md 明写着
     「`market-news` 能用加密符号查（2026-08-20 实测）：symbol=BTC 返回 100 条」，
     并且专门标注了「此前记的『端点只覆盖美股』**作废**」。
     我把那条作废的记载又实现了一遍。
     ⚠️ 这与 EV6「US only」不冲突：EV6 说的是**归因**这条信号的适用范围，
        `symbols[].news` 是数据，两回事。 */
  const fetchNews = async (h, doc) => {
    /* ── 该标的近期新闻（Tab 2）────────────────────────────────────────
         ⚠️ **计费 1 credit/次/只。** 此前整条链路只存在于 `pipeline/build_enrich.py`
            （mock 用的 Python 管线），没被搬进 Skill —— 于是 mock 里有 12 条新闻，
            真 playbook 里一条都没有，而两边的断言都过。
         ⚠️ 归因（attribution.js）也打这个端点，**但那是另一条链,不要复用**:

            宽链（这里）  近 3 天 · 相关度 ≥ 0.80 · 取 12 条 · 回答「这只票最近有什么事」
            严链（归因）  触发时刻 ±120 分钟 · 相关度最高的 3 条 · 回答「那一下是什么引起的」

            让归因读这里的结果，等于用「相关度 ≥ 0.80 且进了前 12」去筛它 ——
            而触发当口那条最相关的报道完全可能相关度 0.6、或排在第 13 位。
            筛掉之后归因会说「没找到」，那是一句**因为筛错而说出的实话**，
            比错的答案更难查。两条链各打各的:触发日的标的当天 2 credits，不触发的 1。 */
      try {
        const nr = await http.fetch(`${B}/api/v1/stocks/market-news?symbol=${h.symbol}`
          + `&start_time=${nowS - 3 * 86400}&end_time=${nowS}&limit=100`, { headers: H });
        if (!nr.ok) { errs.push(`${h.symbol} news: HTTP ${nr.status}`); }
        else {
          const raw = (await nr.json()).data || [];
          newsRaw += raw.length;
          const rows = raw.map(x => ({
            title: x.title, url: x.url, publishedAt: isoTime(x.time_published),
            source: x.source, summary: String(x.summary || "").slice(0, 300),
            sentiment: SENT[x.overall_sentiment_label] ?? null,
            sentimentLabel: x.overall_sentiment_label || null,
            /* ⚠️ 加密的 ticker 是 `CRYPTO:BTC`，不是 `BTC`。
               CLAUDE.md 那条实测原话就是「`symbol=BTC` 返回 100 条，**`CRYPTO:BTC`**
               相关度最高 0.9999」—— 我读了那一行，还是拿裸符号去比。
               后果是相关度恒为 0，全部被 ≥0.80 的门槛筛掉：D-crypto 真跑取回 61 条、
               过筛后 **0 条**，而 `news` 键是有的 —— 于是它看起来像
               「找过了，今天没有相关新闻」，**一句因为筛错而说出的实话**，
               比空着更难查。两边都剥掉前缀再比，不在任何一边写死格式。 */
            relevance: Number(((x.tickers || []).find(k =>
              String(k.ticker || "").replace(/^[A-Z]+:/, "") === h.symbol) || {})
              .relevance_score) || 0,
          })).filter(r => r.relevance >= MINREL).slice(0, 12);
          /* 空数组是「找过，今天没有」；缺键是「没找过」。两者不能合并 —— 契约 §symbols */
          doc.news = rows;
          for (const r of rows) {
            /* 按 URL 去重:端点对同一篇稿件按每个提及的标的各返回一次，
               不去重的话读者会在列表里看到同一条头条四遍。 */
            if (newsSeen[r.url]) { newsSeen[r.url].symbols.push(h.symbol); continue; }
            newsSeen[r.url] = Object.assign({}, r, { symbol: h.symbol, symbols: [h.symbol] });
          }
        }
      } catch (e) { errs.push(`${h.symbol} news: ${e.message}`); }

  };

  for (const h of us) {
    const doc = await rd(`data/symbols/${h.symbol}.json`).catch(() => null);
    if (!doc) { errs.push(`${h.symbol}: no symbol file`); continue; }

    /* ── 财报日历（免费）──
       ⚠️ 没有未来日期就写 null，不要拿最近一次已发布的顶上 ——
          页面会把它印成「下次财报」，而那是三个月前的日子。
          「日历没覆盖到」和「下次在某天」是两句话。 */
    const er = await http.fetch(
      `${B}/api/v1/stocks/earnings-calendar?symbol=${h.symbol}` +
      `&start_time=${nowS - 400 * 86400}&end_time=${nowS + 400 * 86400}&limit=50`, { headers: H });
    if (!er.ok) errs.push(`${h.symbol} earnings: HTTP ${er.status}`);
    else {
      const rows = ((await er.json()).data || [])
        .map(x => [String(x.date).slice(0, 10), x.time || null])
        .filter(r => r[0]).sort((a, b) => a[0] < b[0] ? -1 : 1);
      const fut = rows.filter(r => r[0] > asOf), past = rows.filter(r => r[0] <= asOf);
      const nxt = fut[0] || null;
      doc.earnings = {
        next: nxt ? nxt[0] : null, time: nxt ? nxt[1] : null,
        lastReported: past.length ? past[past.length - 1][0] : null,
        past: past.slice(-8).map(r => ({ d: r[0], time: r[1] })),
      };
      /* EV4 触发：距下次财报 ≤ 1 个交易日（signal-spec §EV4）。 */
      if (nxt) {
        const days = Math.round((Date.parse(nxt[0]) - Date.parse(asOf)) / 86400000);
        if (days <= 1 && days >= 0 && sigOn("EV4")) ev4.push({ sym: h.symbol, name: h.name, date: nxt[0], time: nxt[1], weight: h.weight });
      }
    }

    /* ── 内部人申报（1 credit/次）──
       ⚠️ 股数字段是 `amount`（带符号，负 = 处置），不是 `securities_transacted` ——
          后者这个端点根本不返回。写错字段名不会报错，只会让每一行股数变成空，
          页面照实印「—」，看起来像上游没给。 */
    const cut = new Date(Date.parse(asOf) - WIN * 86400000).toISOString().slice(0, 10);
    const ir = await http.fetch(
      `${B}/api/v1/stocks/insider/transactions?symbol=${h.symbol}` +
      `&start_time=${Math.floor(Date.parse(cut) / 1000)}&end_time=${nowS}` +
      `&time_type=FILING_DATE&limit=300`, { headers: H });
    if (!ir.ok) errs.push(`${h.symbol} insider: HTTP ${ir.status}`);
    else {
      const rows = ((await ir.json()).data || [])
        .map(x => ({ d: String(x.filing_date).slice(0, 10), code: x.transaction_code,
                     owner: x.owner_name, amt: x.amount == null ? null : +x.amount,
                     px: x.price == null ? null : +x.price }))
        .filter(x => x.d >= cut);
      const mk = r => ({ filingDate: r.d, owner: r.owner, code: r.code,
                         shares: r.amt == null ? null : Math.abs(Math.round(r.amt)),
                         price: r.px,
                         value: (r.amt != null && r.px) ? +(Math.abs(r.amt) * r.px).toFixed(2) : null });
      const buys = rows.filter(r => r.code === "P").map(mk)
                       .sort((a, b) => a.filingDate < b.filingDate ? 1 : -1).slice(0, 12);
      const sells = rows.filter(r => r.code === "S").map(mk)
                        .sort((a, b) => a.filingDate < b.filingDate ? 1 : -1).slice(0, 12);
      /* ⚠️ 空列表也要返回。「这个资产类别没有内部人这回事」（加密，键缺省）
         与「这只票本期没有公开市场买入」（美股，键在但 items 为空）是两件事。 */
      doc.insider = {
        windowDays: WIN,
        /* ⚠️ EV1 的触发是「30 日历日内 ≥2 名不同申报人」。此前无条件盖 signalId，
         于是单人一笔也被标成簇 —— 那是把没触发的东西说成触发了。 */
        buys:  (() => { const people = new Set(buys.map(i => i.owner)).size;
                        return { people, filings: buys.length, items: buys,
                                 signalId: people >= 2 ? "EV1" : null }; })(),
        sells: { people: new Set(sells.map(i => i.owner)).size, filings: sells.length, items: sells, signalId: null },
        filedInWindow: rows.length, codeFilter: ["P", "S"],
      };
      log[h.symbol] = { earnings: doc.earnings.next, filings: rows.length,
                        buys: buys.length, sells: sells.length };
    }
    await fetchNews(h, doc);
    await wr(`data/symbols/${h.symbol}.json`, doc);
  }

  /* ── 资金费率（Tab 2 · DR1 的输入）───────────────────────────────────
     ⚠️ 与新闻同源:这一步也只存在于 Python 管线里，没被搬进 Skill。
        后果比新闻严重 —— **DR1 是已定案 13 条之一、L2 层，输入拿不到
        就等于它被静默停用**，而目录里它还在，页面上还给它留着一张卡。
     ⚠️ `/crypto/funding-rate` 是**免费**端点。不取没有任何成本上的理由。
     ⚠️ 股票要**整个省掉这个键**，不要写 null —— 契约靠键存不存在区分
        「不适用」与「暂时没有」，写 null 就把两者合成了一个。 */
  const DR1_THRESHOLD = 0.0005;          // |费率| ≥ 0.05% / 8h
  for (const h of cr) {
    const doc = await rd(`data/symbols/${h.symbol}.json`).catch(() => null);
    if (!doc) { errs.push(`${h.symbol}: no symbol file`); continue; }
    try {
      const fr = await http.fetch(`${B}/api/v1/crypto/funding-rate?symbol=${h.symbol}`
        + `&start_time=${nowS - 60 * 86400}&end_time=${nowS}&limit=500`, { headers: H });
      /* ⚠️ 这里不能 continue —— 后面还有新闻要取。
         资金费率挂了就把这只标的的新闻一起跳过，是让两件不相干的事共用一个出口。 */
      if (!fr.ok) throw new Error(`HTTP ${fr.status}`);
      const pts = ((await fr.json()).data || [])
        .map(x => ({ t: x.time || x.timestamp, rate: Number(x.funding_rate ?? x.rate) }))
        .filter(x => x.t && Number.isFinite(x.rate))
        .sort((a, b) => a.t < b.t ? -1 : 1);
      const days = [...new Set(pts.filter(x => Math.abs(x.rate) >= DR1_THRESHOLD)
        .map(x => String(x.t).slice(0, 10)))].sort();
      doc.funding = {
        asOf: pts.length ? pts[pts.length - 1].t : null,
        unit: "8h", threshold: DR1_THRESHOLD, normalized: false,
        points: pts, extremeDays: days,
      };
      if (days.length) dr1.push({ sym: h.symbol, days });
    } catch (e) { errs.push(`${h.symbol} funding: ${e.message}`); }
    await fetchNews(h, doc);
    await wr(`data/symbols/${h.symbol}.json`, doc);
  }

  /* ── data/news.json · Tab 1 底部的今日相关新闻（宽链）── */
  const flat = Object.values(newsSeen)
    .sort((a, b) => String(a.publishedAt) < String(b.publishedAt) ? 1 : -1);
  await wr("data/news.json", { asOf: new Date().toISOString(), chain: "wide",
                               minRelevance: MINREL, items: flat.slice(0, 12) });

  /* EV4 进 findings。⚠️ 它是**日历不是信号** —— 不检测任何东西，
     只把一个已排定的日期提前告知，所以不走告警判据。 */
  const at = L.etStamp(asOf, "16:00:00");
  /* ⚠️ 用 `L.commitFindings` 重读后再合并，**不要**改这个 200 行之前读到的 `fj`。
     实测把日线同一分钟写进去的 `scan` 与 `asOf` 整个抹掉了。 */
  const ev4Findings = [...ev4.map(e => ({
    id: `${asOf}:${e.sym}:EV4`, symbol: e.sym, assetClass: "us_equity", signalId: "EV4",
    unit: "session", severity: "informational", triggeredAt: at, knownAt: at,
    episodeId: `${asOf}:${e.sym}:EV4`, novelty: null, priority: null,
    measured: { z: null, rvol: null, move: null },
    trigger: { unit: "session", moveAt: at, thresholdSource: "user_set",
               barSlot: null, barClose: null },
    delivery: { level: "L1", cappedBy: null },
    context: {
      benchmark: { symbol: null, benchmarkMove: null, symbolMove: null, applicable: false },
      sizeRank: null,
      /* ⚠️ 日历不调模型 —— 它没有可解释的移动。 */
      /* EV4 自带原因，从不做归因 —— 整个键缺省，见 userlines.js 同处注释 */
    },
    on: e.date,
  }))];
  await L.commitFindings(rd, wr, {
    owns: f => f.signalId === "EV4",
    mine: ev4Findings,
  });

  const meta = await rd("data/meta.json");
  meta.producedSignals = [...new Set([...(meta.producedSignals || []), "EV1", "EV4",
    ...(dr1.length ? ["DR1"] : [])])];
  /* 三个数各有各的含义，不能互相顶替:取回多少 · 过筛留下多少 · 扫了几只持仓。
     只报一个的话，「没取到」和「取到了但都没过筛」会长得一样。 */
  meta.scanned = Object.assign({}, meta.scanned,
    { newsItems: newsRaw, newsPassed: flat.length });
  /* ⚠️ 谁往这份产物里加东西，谁就把 `generatedAt` 推到现在。
     契约:「No finding may be timestamped after generatedAt」——
     只让日线写它，此后每一轮加进来的卡都比它晚。 */
  meta.generatedAt = new Date().toISOString();
  /* ⚠️ 「日历窗口里没有」和「我们没查过」在页面上都是一格空的。
     端点只向前看约 30 天，美股账本里一家都不在窗口内是**常态**，不是故障 ——
     说出来，否则读者会以为财报这一路坏了。
     没有美股就不发这条（那是另一种空:这本账根本没有财报可言）。 */
  {
    const _us = port.holdings.filter(h => h.assetClass === "us_equity");
    const _any = _us.some(h => ((log[h.symbol] || {}).earnings) != null);
    const _g2 = new Set(meta.gaps || []);
    _g2.delete("earnings_next_out_of_calendar_window");
    if (_us.length && !_any) _g2.add("earnings_next_out_of_calendar_window");
    meta.gaps = [..._g2];
  }
  meta.freshness = Object.assign({}, meta.freshness, { news: new Date().toISOString() });
  meta.freshness = Object.assign({}, meta.freshness,
    { earningsCalendar: new Date().toISOString() });
  if (errs.length) meta.gaps = [...new Set([...(meta.gaps || []), "context_fetch_errors:" + errs.join("|")])];
  await L.commitMeta(rd, wr, meta, {
    freshness: ["news", "earningsCalendar"],
    signals: ["EV1", "EV4", ...(dr1.length ? ["DR1"] : [])],
    gapPrefixes: ["context_fetch_errors", "earnings_next_out_of_calendar_window"],
  });

  /* 推送：只有财报**明天**发布才值得打断 —— 内部人申报是记录，不推。
     ⚠️ EV4 必须盘前跑。它的文案是「明天盘后发布」，收盘后才跑当天根本推不出来。 */
  if (ev4.length) {
    await ctx.self.ts("alerts", "events").append([{
      date: Date.now(),
      title: `Portfolio Watch · earnings`,
      body: [ev4.length === 1 ? `${ev4[0].sym} reports within one session`
                              : `${ev4.length} holdings report within one session`, "",
             /* ⚠️ 端点给的是 `bmo` / `amc`，那是它的内部码，不是给人看的字。
                页面早就有对应文案（earnBmo「before open」/ earnAmc「after close」），
                而推送这一路把原始值直接拼了进去 —— 手机上印出来就是
                「NVDA 2026-08-26 amc」。CLAUDE.md 的写作约定第 2 条写着
                「不裸用字母代号」，这里正是漏掉的那处：**同一个事实在页面上有名字、
                在推送里没有**，而推送恰恰是唯一会打断用户的那个出口。
                认不出的值原样带出去，不吞掉 —— 未知的码也比没有强。 */
             ...ev4.map(e => {
               const WHEN = { bmo: "before open", amc: "after close" };
               const when = e.time ? (WHEN[String(e.time).toLowerCase()] || e.time) : "";
               return `${e.sym}  ${e.date}${when ? "  " + when : ""}`;
             }),
             "", PLAYBOOK_URL].join("\n"),
    }]);
  }
});
})();
