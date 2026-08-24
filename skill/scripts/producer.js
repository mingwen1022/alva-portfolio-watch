/* 每轮跑一次：取当日行情 → 算 M 层 / S 层 → 覆盖 data/ 下的运行时文件。
 *
 * 基线（阈值 · 投递上限 · 分布 · ρ）在初始化时算一次，写进 data/baselines.json，
 * 本脚本只读不写它 —— 决策 #9「阈值用固定值」要求 θ 不随每轮漂动。
 *
 * ⚠️ 口径全部走 lib.js，本文件不自己实现任何统计。两份实现就是两套规则。
 */
const { Feed, feedPath, makeDoc, alertOutput, str, num, messagePresentationField } = require("@alva/feed");
const http  = require("net/http");
const secret= require("secret-manager");
const alfs  = require("alfs");
const env   = require("env");
const L     = require("./lib.js");
const ATTR  = require("./attribution.js");

const B = "https://data-tools.prd.arrays.org";
const LOOKBACK_DAYS = 200;          // 90 根基线 + 富余，够任何一只补齐窗口
/* 推送里带上页面链接 —— 收到一条「NVDA 越线了」之后，下一步一定是想看细节。 */
/* ⚠️ 从 args 读，不要写死。告警正文末尾的回链指向它 ——
   写死就等于把每个用户的告警都深链到作者那一个 playbook。
   由 `alva deploy create --args '{"root":"…","playbookUrl":"…"}'` 注入。 */
let PLAYBOOK_URL = "";

const feed = new Feed({ path: feedPath("portfolio-watch-daily") });

/* ⚠️ 必须**声明** alert output —— cronjob 的 `--push-notify` 投递的是声明过的输出。
   不声明的话：append 成功、run completed、投递记录一条没有，**全程零报错**。
   两条约束是平台强制的，错了会在 def() 当场抛：
     · `notify/message` 是保留组，不能拿来声明，要用自己的组名
     · TypeDoc 必须有一个根级 `body` 字符串字段 —— 那是推送正文
   还有一条不报错的：**运行必须来自 feed 绑定的那个 cronjob**。
   在别的 cronjob 上跑同一个脚本，一切正常而什么都不会送出去。 */
feed.def("alerts", {
  events: alertOutput(makeDoc("Portfolio Watch alert",
    "Holdings that crossed both of their lines", [
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
  const base = await rd("data/baselines.json");
  /* ⚠️ **开关面板标题是「可以关掉的信号」，而这些开关此前只有 US1–3 真的接线。**
     PV1 / PV5 / EV4 三个在面板上照样显示 on/off，关掉它们什么也不会发生 ——
     面板对读者承诺了一件管线不兑现的事。
     关掉的含义是「别再为它告警」，**不是「别算了」**:持仓表那一行的读数照旧要出，
     它是引擎跑过的唯一证据。所以只拦 finding，不拦计算。 */
  const alertCfg = (await rd("config/alerts.json").catch(() => ({}))).enabled || {};
  const sigOn = id => alertCfg[id] !== false;
  const meta = await rd("data/meta.json");

  const now = new Date();
  const sec = s => Math.floor(new Date(s).getTime() / 1000);
  const t0  = Math.floor(now.getTime() / 1000) - LOOKBACK_DAYS * 86400;
  const t1  = Math.floor(now.getTime() / 1000) + 86400;

  /* 取数。⚠️ 端点返回按时间**倒序**，字段名两类资产不同。
     分段失败要单独记 —— "ERR 400" 不是「取到 1 根」。 */
  async function daily(sym, cls) {
    const url = cls === "crypto"
      ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}&interval=1d&start_time=${t0}&end_time=${t1}&limit=400`
      : `${B}/api/v1/stocks/kline?symbol=${sym}&interval=1d&start_time=${t0}&end_time=${t1}&limit=400`;
    const r = await http.fetch(url, { headers: H });
    if (!r.ok) return { err: `HTTP ${r.status}` };
    const d = (await r.json()).data || [];
    if (!d.length) return { err: "empty" };
    const rows = d.map(x => cls === "crypto"
      ? [String(x.time_open).slice(0, 10),   +x.price_close, +x.volume,
         +x.price_open, +x.price_high, +x.price_low]
      : [String(x.time_period_start).slice(0, 10), +x.price_close, +x.volume_traded,
         +x.price_open, +x.price_high, +x.price_low]);
    rows.sort((a, b) => a[0] < b[0] ? -1 : 1);          // 排正
    /* ⚠️ `bars` 是整根，不是字段白名单。写成 `{d,c,v}` 会把此后新增的每个字段
       静默丢掉，而丢法是「值变成 undefined」→ 页面渲染成破折号 → 看起来像上游没给。 */
    return { d: rows.map(r => r[0]), c: rows.map(r => r[1]), v: rows.map(r => r[2]),
             bars: rows };
  }

  const findings = [], scan = [], gaps = [...(meta.gaps || [])];

  /* ⚠️ 混合账本在周末有**两个**「最近收盘」：美股停在周五，加密每天都有。
     一个 asOf 说不了这两件事 —— 把周五的 −0.98% 摆在「周六 20:00」的时间戳下面，
     读者会以为那是周六发生的。每一行记下它自己那根 bar 的日期，
     并在跨日时如实写进 gaps，让页面能说出来，而不是替它圆过去。 */
  const barDates = {};
  /* ⚠️ 必须在 deliveryOf 第一次被调用之前读。它是 const，而 deliveryOf 在扫描循环里
     就会用到 —— 声明在循环之后就是暂时性死区，运行时抛 ReferenceError，
     而 feed.run 把它吞成 completed、日志为空、什么都不写。 */
  const SIGDEF = (await rd("data/signals.json").catch(() => ({}))).signals || {};
  const errs = [];
  let asOfDate = null;

  /* ⚠️ 富化块 1「是大盘还是它自己」此前恒为 applicable:false —— 而规格给它 100% 覆盖，
     PV1 的文案模板结尾就是「同期 NVDA −5.6% / SPY −0.3%」，SPY 端点还是免费的。
     加密没有市场基准（BTC 占全加密市值一半以上，市场模型分解对它失效），
     所以只对美股与 other 适用，加密如实置 applicable:false。 */
  let spyMove = null;
  try {
    const t1s = Math.floor(now.getTime() / 1000), t0s = t1s - 10 * 86400;
    const rr = await http.fetch(
      `${B}/api/v1/stocks/kline?symbol=SPY&interval=1d&start_time=${t0s}&end_time=${t1s}&limit=10`,
      { headers: H });
    if (rr.ok) {
      const rows = ((await rr.json()).data || [])
        .map(x => [String(x.time_period_start).slice(0, 10), +x.price_close])
        .sort((a, b2) => a[0] < b2[0] ? -1 : 1);
      if (rows.length >= 2) spyMove = +(rows[rows.length - 1][1] / rows[rows.length - 2][1] - 1).toFixed(5);
    }
  } catch (e) { errs.push("SPY benchmark: " + e.message); }

  for (const h of port.holdings) {
    const cls = h.assetClass;
    const b = base[h.symbol] || {};
    const th = b.thresholds || {};
    const px = await daily(h.symbol, cls);
    if (px.err) {
      errs.push(`${h.symbol}: ${px.err}`);
      scan.push({ symbol: h.symbol, state: "insufficient_baseline", unit: "session",
                  price: null, volume: null });
      continue;
    }
    const barDate = px.d[px.d.length - 1];
    if (!asOfDate || barDate > asOfDate) asOfDate = barDate;
    barDates[h.symbol] = barDate;

    const rdg = L.reading(px.c, px.v, 90);
    /* 基线不足是**停用**，不是降级 —— 算不出的量在任何层级都不该显示。 */
    if (!rdg || (b.baselineDays != null && b.baselineDays < 60)) {
      scan.push({ symbol: h.symbol, state: "insufficient_baseline", unit: "session",
                  price: null, volume: null, baselineDays: b.baselineDays ?? px.c.length });
      h.last = px.c[px.c.length - 1];
      continue;
    }

    const fired = L.firedPV1(rdg, th.theta_z, th.theta_v);
    scan.push({
      symbol: h.symbol,
      state: fired ? "triggered" : "quiet",
      unit: "session",
      asOf: barDate,          // 这一行的读数来自哪一根 bar
      price:  { today: +rdg.move.toFixed(5), line: +(th.theta_z * rdg.sigma).toFixed(5),
                usual: +rdg.sigma.toFixed(5) },
      volume: { rvol: +rdg.rvol.toFixed(3), line: th.theta_v, partial: false },
    });

    h.last = px.c[px.c.length - 1];
    h.todayPct = +rdg.move.toFixed(5);
    /* 行内迷你走势图。init 建库那天填过一次，此后**必须每天续** ——
       不续的话它冻在建库日，而冻住的走势图和真实的横盘长得一模一样。 */
    h.spark = px.c.slice(-30);

    /* 蜡烛图同理。读改写，不整份重建 —— 这个文件还装着 context producer 写的
       财报与内部人、盘中 producer 写的分钟线，整份重建会把它们抹掉。
       合并按日期去重：这一轮取的 400 根与已有的 502 根重叠，直接拼会出现重复的 x 轴。 */
    try {
      const sp = `data/symbols/${h.symbol}.json`;
      const doc = await rd(sp);
      const byDate = new Map((doc.kline || []).map(k => [k.d, k]));
      for (const r of px.bars) byDate.set(r[0], { d: r[0], o: r[3], h: r[4], l: r[5], c: r[1], v: r[2] });
      doc.kline = [...byDate.values()].sort((a, b) => a.d < b.d ? -1 : 1).slice(-502);
      const lows = doc.kline.slice(-252).map(k => k.l).filter(x => x != null);
      const highs = doc.kline.slice(-252).map(k => k.h).filter(x => x != null);
      doc.range52w = { low: lows.length ? Math.min(...lows) : null,
                       high: highs.length ? Math.max(...highs) : null,
                       asOf: doc.kline.length ? doc.kline[doc.kline.length - 1].d : null };
      await wr(sp, doc);
    } catch (e) { errs.push(`${h.symbol} kline merge: ${e.message}`); }

    if (fired && sigOn("PV1")) {
      /* 加密日线按 UTC 切，D 那根收在 D+1 00:00Z —— 夏令时下是 D 20:00 ET。
         把所有标的一律写成 16:00 ET，会让这一轮报出四小时之后才知道的收盘价。 */
      const at = closeInstant(cls, px.d[px.d.length - 1]);
      findings.push({
        id: `${px.d[px.d.length - 1]}:${h.symbol}:PV1`,
        symbol: h.symbol, assetClass: cls, signalId: "PV1", unit: "session",
        severity: "critical", triggeredAt: at, knownAt: at,
        episodeId: `${px.d[px.d.length - 1]}:${h.symbol}`,
        novelty: null, priority: null,
        measured: { z: +rdg.z.toFixed(3), rvol: +rdg.rvol.toFixed(3), move: +rdg.move.toFixed(5) },
        trigger: { unit: "session", moveAt: at, thresholdSource: th.source,
                   barSlot: null, barClose: null },
        delivery: deliveryOf(b, "PV1"),
        context: {
          benchmark: (cls === "crypto" || spyMove == null)
            ? { symbol: null, benchmarkMove: null, symbolMove: null, applicable: false }
            : { symbol: "SPY", benchmarkMove: spyMove, symbolMove: +rdg.move.toFixed(5), applicable: true },
          /* ⚠️ 日线档也有名次。此前写死 null，而模板注释说的正好相反
             （「契约只对日线给 sizeRank」）—— 两边同时错，方向相反。 */
          sizeRank: dayRank(b, rdg.move),
          /* ⚠️ 契约的 context 是四个键，此前三个 producer 都漏了 pnl ——
             模板自检 CONTEXT_KEYS 要求齐全，于是每张卡都报缺键。
             未绑定账户时字段在、值为 null：「不适用」与「漏了」是两件事。 */
          pnl: (h.shares == null || h.avgCost == null) ? null : {
            today: +(h.shares * (b._last || 0) * rdg.move).toFixed(2),
            shares: h.shares,
            lifetime: h.lifetimePnl == null ? null : h.lifetimePnl },
          attribution: { timing: "none", summary: null, sources: [], model: null, generatedAt: null },
        },
      });
    }
  }

  if (errs.length) gaps.push("fetch_errors:" + errs.join("|"));
  const spread = [...new Set(Object.values(barDates))].sort();
  if (spread.length > 1) gaps.push("holdings_span_multiple_sessions:" + spread.join(","));

  /* ⚠️ 全部取数失败时 asOfDate 是 null，拿它构造时刻会当场抛（crypto 分支
     `new Date(null + "T00:00:00Z")` 是 Invalid Date，toISOString 直接 RangeError）。
     一天里每只标的都取不到是**可能发生的常态**（端点故障、限流），
     不该让整轮死掉 —— 如实记 gap，不写任何派生时刻，让上一轮的数据留在原地。 */
  if (!asOfDate) {
    const meta0 = await rd("data/meta.json").catch(() => ({}));
    meta0.gaps = [...new Set([...(meta0.gaps || []),
      "fetch_errors:" + (errs.slice(0, 8).join("|") || "all symbols")])];
    await wr("data/meta.json", meta0);
    /* ⚠️ 这里不能用 num()/str() —— 本文件后面有个同名的局部守卫函数遮蔽了 import，
       在它声明之前引用就是暂时性死区。返回原始值。 */
    return { symbols: 0, note: "no market data this run" };
  }

  const asOfTs = closeInstant(
    port.holdings.some(h => h.assetClass === "crypto") ? "crypto" : "us_equity", asOfDate);

  /* 组合层。股数与成本来自已有的 portfolio.json —— 本脚本只更新价格与由它派生的数。 */
  /* ⚠️ 字段名是 `avgCost`，不是 `cost` —— 契约 §四 写着。
     我按印象写成了 `h.cost`，于是 `h.shares * undefined = NaN`，
     `JSON.stringify` 把 NaN 写成 **null**，页面上 Total P/L 一列全是 +$0、
     KPI 整块空着。**看起来像上游没给，实际是我们算出了垃圾。**
     所以下面这个 num() 不只是修字段名 —— 算不出来就当场报错，
     绝不把 null 写进一个该是数字的位置。 */
  const num = (v, what) => {
    if (!Number.isFinite(v)) throw new Error(`${what} 算出了 ${v} —— 拒绝写盘`);
    return +v.toFixed(2);
  };
  /* ⚠️ 未绑定账户时 shares / avgCost 是 null（契约：linked:false 下金额相关的全部为 null）。
     无分支地算 `shares * last`：null 会当成 0，于是全书市值为零、权重 0/0 变 NaN，
     而 num() 遇 NaN 抛错 → feed.run 吞掉 → cronjob completed、什么都没写。
     「明确报了标的」写的就是 linked:false，也就是最常见的入口。
     盘中 producer 已经有这个分支，日线这份没有 —— 同一件事两份实现只修了一份。 */
  const LINKED = port.linked !== false;
  let total = port.cash || 0, cost = 0;
  for (const h of port.holdings) {
    if (!LINKED || h.shares == null || h.avgCost == null) {
      h.value = null; h.lifetimePnl = null; continue;
    }
    h.value = num(h.shares * h.last, `${h.symbol}.value`);
    total += h.value; cost += h.shares * h.avgCost;
    h.lifetimePnl = num(h.value - h.shares * h.avgCost, `${h.symbol}.lifetimePnl`);
  }
  /* 无仓位时权重走等权，并标出来源 —— 页面据此说明这是占位而不是真实权重 */
  if (!LINKED || !total) {
    const eq = +(1 / (port.holdings.length || 1)).toFixed(4);
    for (const h of port.holdings) h.weight = eq;
    port.weightSource = "equal";
  } else {
    for (const h of port.holdings) h.weight = +(h.value / total).toFixed(4);
    port.weightSource = "value";
  }
  port.asOf = asOfTs;
  if (!LINKED) {
    /* 契约：linked:false 时 kpi 只保留 fromHigh */
    port.kpi = { fromHigh: (port.kpi || {}).fromHigh || null,
                 totalValue: null, totalPnl: null, todayPnl: null };
  } else {
  port.kpi.totalValue = num(total, 'kpi.totalValue');
  const pnl = total - (port.cash || 0) - cost;
  port.kpi.totalPnl = { abs: num(pnl, 'kpi.totalPnl.abs'),
                        pctOnCost: +(pnl / cost).toFixed(4) };
  }

  /* ── 把今天这一点接到净值序列上 ────────────────────────────────────────
     ⚠️ init 回推出一条曲线之后就没人管了 —— 不接的话它**冻在建库那天**，
        而冻住的曲线和「这几天净值没动」在图上是同一根线。
     按日期去重:同一天重跑要覆盖那一点，不是追加第二个。 */
  if (LINKED && total) {
    try {
      const se = await rd("data/series.json");
      const pts = (se.points || []).filter(p2 => p2.d !== asOfDate);
      const prev = pts.length ? pts[pts.length - 1] : null;
      const base = pts.length ? pts[0].value : total;
      pts.push({ d: asOfDate, value: +total.toFixed(2),
                 dayPnl: prev ? +(total - prev.value).toFixed(2) : 0,
                 cumReturn: base ? +(total / base - 1).toFixed(4) : 0 });
      pts.sort((a, b) => a.d < b.d ? -1 : 1);
      se.points = pts;
      const hi = pts.reduce((a, b) => b.value > a.value ? b : a, pts[0]);
      se.high = { d: hi.d, value: hi.value };
      await wr("data/series.json", se);
      /* `fromHigh` 是从这条曲线读的，不另算一份 —— 两份必然对不上。
         ⚠️ 第三个键是 `sessionsAgo`（**交易日个数**，不是日历天）——
            契约与 mock 都是它。写成 `at` 页面读不到，那一格显示破折号。 */
      /* `todayPnl` 也从这条曲线读 —— 它此前从建库起就一直是 null，
         而 KPI 那一格是「今天」，一直空着最像「今天没动」。 */
      port.kpi.todayPnl = prev
        ? { abs: +(total - prev.value).toFixed(2),
            pct: prev.value ? +((total / prev.value) - 1).toFixed(4) : null }
        : null;
      const agoIdx = pts.findIndex(p2 => p2.d === hi.d);
      port.kpi.fromHigh = hi.value
        ? { pct: +(total / hi.value - 1).toFixed(4), high: hi.value,
            sessionsAgo: agoIdx < 0 ? null : pts.length - 1 - agoIdx }
        : null;
    } catch (e) { errs.push(`series: ${e.message}`); }
  }

  /* ⚠️ 只换掉自己那条信号的行。日线与盘中是两个 cronjob，各写各的 ——
     整体覆盖会把盘中 producer 刚写的 PV5 冲掉，而冲掉的表现是
     「今天没有盘中告警」，看起来像市场安静，实际是我们删了它。 */
  const prevFj = await rd("data/findings.json").catch(() => ({ findings: [] }));

  /* ⚠️ 归因跑在写盘**之前**。原顺序是 写 findings.json → 写 meta.json → 归因循环，
     于是每次约 208 credits 算出来的东西，在它产生之前就已经落盘，算完直接丢。
     同一个顺序还让 `attrLog` 先被引用、后被 const 声明 —— 同块作用域下这是暂时性死区，
     运行时抛 ReferenceError，而 feed.run 把异常吞成 `completed`、日志为空。
     两处叠起来的表现是「日线卡从来没有解释」，看起来像模型没返回，
     实际是这段代码从未执行过。 */
  /* ── AI 归因额度 ──
     ⚠️ 按**卡**计（共现合并后一张卡一次），按 **UTC 日**重置 ——
        与 cron 同一个时区，否则会出现「额度重置了但当天的 cron 还没跑」的错位。
     ⚠️ 先到先得。告警是一整天陆续来的，等收盘再挑最重要的十条会让推送迟一天。
        代价说清楚：波动大的日子里早盘那批吃掉额度，晚来的显示「已到上限」。
     ⚠️ 用完之后写 `notRun:"daily_cap"`，**不能**写成 `timing:"none"` ——
        后者的意思是「找过了，今天没有相关报道」，那是另一件事。 */
  const cfg = await rd("config/alerts.json").catch(() => ({}));
  /* 信号目录 —— 第三道投递上限从这里取 */
  const CAP = ((cfg.attribution || {}).dailyCap) || 10;
  const st = await rd("data/state.json").catch(() => ({}));
  const utcDay = new Date().toISOString().slice(0, 10);
  const q = (st.attributionQuota && st.attributionQuota.day === utcDay)
    ? st.attributionQuota : { day: utcDay, used: 0 };

  /* 只给进告警流的卡调 —— 用户线与 L3 及以下都不调（signal-spec §7.1）。
     ⚠️ 上一轮的结果要搬过来，并用 KV 去重，和盘中同一套。
        日线一天只跑一次，看起来不需要 —— 但手工重跑一次就把额度再花一遍，
        每次约 208 credits。判据是 generatedAt（问过没有），不是有没有内容 ——
        「问过了，什么都没找到」同样要搬，否则下一轮它会退回成「压根没问」。 */
  const prevAttr = Object.fromEntries((prevFj.findings || [])
    .filter(f => f.context && f.context.attribution && f.context.attribution.generatedAt)
    .map(f => [f.id, f.context.attribution]));
  /* ⚠️ **KV 的键必须按 playbook 分。**
     `feedPath("portfolio-watch-…")` 是写死的常量 —— 同一个 skill 建出来的**每一个**
     playbook 都用同一条 feed 路径，也就共用同一份 KV。而 finding 的 id 是
     `日期:标的:信号:时段`，同样不含 playbook。

     两者相乘的后果是静默的:2026-08-23 同一天建的两个加密 playbook 产出了**同样的三个 id**，
     第一个归因过并写进 KV，第二个读到「归因过了」就 `continue` ——
     **连 `notRun` 都不会写**（那一行在设 notRun 之前），于是产物上看是
     `generatedAt: null · notRun: null · quota.used: 0`，跟「从来没到过这一步」一模一样。

     `pushedBars` 同一个坑:第二个 playbook 的告警会被当成「推过了」而不推。

     ROOT 形如 `/alva/home/<user>/playbooks/<name>`，取最后一段作后缀。 */
  const kvKey = k => `${k}:${String(ROOT).split("/").filter(Boolean).pop()}`;
  const done = JSON.parse((await ctx.kv.load(kvKey("attributed"))) || "{}");
  const attrLog = [];
  for (const f of findings) {
    if ((f.delivery || {}).level !== "L1" || f.signalId.startsWith("US")) continue;
    if (prevAttr[f.id]) { f.context.attribution = prevAttr[f.id]; continue; }
    if (done[f.id]) continue;
    if (q.used >= CAP) { f.context.attribution.notRun = "daily_cap"; continue; }
    done[f.id] = 1;
    q.used += 1;
    const h2 = port.holdings.find(x => x.symbol === f.symbol) || {};
    try {
      const out = await ATTR.attribute({ finding: f, symbol: f.symbol,
        name: h2.name || f.symbol, assetClass: f.assetClass, headers: H });
      f.context.attribution = out.attribution;
      attrLog.push({ sym: f.symbol, ...out.checks });
    } catch (e) {
      /* 失败不拦告警：没有解释，材料照常展示，卡照发。 */
      f.context.attribution.notRun = null;
      attrLog.push({ sym: f.symbol, outcome: "call_failed", err: String(e.message).slice(0, 120) });
    }
  }
  /* ⚠️ 用户线只由**盘中** producer 评。两边各评一遍会产出两条同 id 不同 unit 的 finding，
     页面上同一条线出现两次。盘中价格最新、每 15 分钟一轮，止损线本来就该在盘中抓到，
     而不是等收盘。见 producer-intraday.js。 */

  st.attributionQuota = q;
  await wr("data/state.json", st);
  await ctx.kv.put(kvKey("attributed"), JSON.stringify(done));

  /* ⚠️ 按 (signalId, unit) 过滤 —— 只按 ID 会删掉盘中刚写的 bar 档用户线 */
  /* 日线只换自己那条信号的行。用户线由盘中 producer 维护，这里原样留着 —— 
     按 signalId 删会把盘中刚写的那批一并删掉。 */
  const keepOther = (prevFj.findings || []).filter(f => f.signalId !== "PV1");
  const all = [...keepOther, ...findings].sort(
    (a, b2) => a.triggeredAt < b2.triggeredAt ? -1 : 1);
  /* ⚠️ 新闻的两个计数**不是这个 producer 知道的** —— 是 context producer 取完新闻才知道。
     此前这里无条件写 0，于是每晚把它们抹平一次:页面一边从 news.json 读出 12 条、
     一边从这里读到「扫描 0 条」，两个数互相矛盾。
     （2026-08-23 平台机器人报的就是这条:「12 stories passed the filter out of zero scanned」。）
     ⚠️ 与 earningsWeek 完全同形:**一个 producer 拿常量覆盖另一个 producer 的真实值**。
     自己不知道的量就搬上一轮的，不要写 0 —— 0 是一个主张，「不知道」不是。
     ⚠️ `gaps: []` 同理:这里整体清空会抹掉别的 producer 记下的缺口。 */
  /* ⚠️ **`findings.json` 被三个 producer 写，而此前没有任何地方规定谁拥有哪几个键。**
     实测后果:D-crypto 那一轮 `scan` 落盘时是空数组，而 `asOf` 还是 init.js 的时间戳 ——
     日线写进去的那份被覆盖回了建库时的空值。
     页面上的样子是:持仓表「告警依据」六列**全部空白**（它们全从 scan 取数），
     读者看到一张只有价格、没有任何判断依据的表。

     归属从此写在这里，其余 producer 只做读改写、不重建这几个键:

         asOf · scan · scanned.holdings      日线 producer（本文件）拥有
         findings                            三家各管自己那几族，见各处 kept 过滤
         scanned.newsItems / newsPassed      context producer 拥有
         gaps                                谁发现谁追加，没有人整体清空 */
  const prevScan = prevFj.scanned || {};
  if (!scan.length && port.holdings.length) {
    /* 有持仓却一行读数都没算出来 —— 这不该发生。说出来，别让它变成一张空表。 */
    /* ⚠️ 原来写成 `scan_empty_with_3_holdings` —— 页面按第一个 `:` 之前查表，
       这串里没有冒号，整串当键，永远查不到，于是把裸 id 印给用户。
       参数一律放在 `:` 之后、逗号分段。 */
    gaps.push(`scan_empty_with_holdings:${port.holdings.length}`);
  }
  /* ⚠️ 整份覆盖会抹掉窗口里别人写进来的 finding —— `prevFj` 是这一轮开头读的。
     重读之后只替换自己那一族（PV1），顶层字段里 asOf / scan / scanned 归日线管。 */
  await L.commitFindings(rd, wr, {
    owns: f => f.signalId === "PV1",
    mine: findings,
    patch: { asOf: asOfTs, scan,
             scanned: { holdings: port.holdings.length,
                        newsItems: prevScan.newsItems ?? null,
                        newsPassed: prevScan.newsPassed ?? null },
             gaps: [...new Set([...(prevFj.gaps || []), ...gaps])] },
  });
  await wr("data/portfolio.json", port);

  /* ⚠️ `generatedAt` 是**这一轮跑完的时刻**，不是最后一根 bar 的收盘 + 5 分钟。
     契约原话:「No finding may be timestamped after generatedAt」——
     写成收盘 +5 分的话，此后每 15 分钟盘中加进来的卡都比它晚，
     页头「行情更新于 20:05」下面挂着 01:00 的告警，而两个数都是真的。
     ⚠️ 「行情什么时候的」是另一件事，那是 `freshness.prices` 与 `findings.asOf`，
        它们该停在收盘 —— 不要为了让这一条自洽而去改那两个。 */
  const gen = new Date().toISOString();
  /* ⚠️ 各 producer 只声明**自己**产出的那几条，并进去而不是整体覆盖 ——
     盘中 producer 每 15 分钟也会写它自己那条，整体覆盖会互相抹掉。
     没人声明的信号，页面显示「尚未启用」而不是「on」。 */
  /* ⚠️ 三种结局分开记，并且要**落盘**。
     实测：summary 为空，而 outcome 只活在返回值里（feed.run 吞掉了它）——
     只能再花一次 credits 重跑才查得出是解析失败、调用失败还是被硬门拦。 */
  meta.attributionRuns = [...(meta.attributionRuns || []).slice(-20), ...attrLog];
  meta.producedSignals = [...new Set([...(meta.producedSignals || []), "PV1", "US1", "US2", "US3"])];
  meta.generatedAt = gen;
  /* ⚠️ `prices` 是「**最后一次刷新价格的时刻**」，不是「最后一根 bar 的收盘时刻」。
     这一轮确实刷了价格（上面重取了日线、写了 h.last），所以盖当前时刻。

     此前这里写 `asOfTs`（收盘），于是三家互相覆盖:
       init 写当前 → 日线一跑改回收盘 → 盘中再改回当前 → 日线又改回去…
     页头那句「行情更新于」因此在「刚刚」和「昨晚 20:00」之间来回跳，
     而两个数都是真的，只是回答的不是同一个问题。

     ⚠️「这一行读数用的是哪根 bar」是另一件事 —— 它在 `findings.asOf` 与
        `scan[].asOf`，那两个该停在收盘，不要为了让这一条自洽去动它们。 */
  meta.freshness = Object.assign({}, meta.freshness, { prices: new Date().toISOString() });
  meta.gaps = [...new Set(gaps)];
  /* ⚠️ 日线读 meta 读得早（第 57 行），写得晚（这里）—— 中间隔着全部日线取数。
     这份文件四个 producer 都在改，整体写回会把窗口里别人写的键抹掉。
     日线认领的 gap 前缀比较多，因为它同时在算基线可用性与账本形状。 */
  await L.commitMeta(rd, wr, meta, {
    signals: ["PV1", "US1", "US2", "US3"],
    freshness: ["prices"],
    gapPrefixes: ["fetch_errors", "scan_empty_with_holdings", "insufficient_baseline",
                  "holdings_span_multiple_sessions", "short_positions_unsupported",
                  "multi_currency_unsupported", "holdings_missing_fields",
                  "unvalidated_asset_class", "pv1_highvol_downgrade_undecided",
                  "m23_not_run", "pv5_not_computed", "no_intraday_for_this_book",
                  "nav_series_backcast", "logos_unavailable"],
  });

  /* ── 推送 ──
     ⚠️ 只推真的会响手机的那些。`delivery.level !== "L1"` 的卡留在页面上 ——
        那是逐标的投递上限的全部意义，在这里绕过去等于前面白做。
     ⚠️ 一条也没有就不推。「今天没有异动」不值得打断谁；页面上有扫描摘要。 */

  /* ⚠️ `novelty === 0` 的不推。状态型信号可以连续成立几个月 —— 实测一条回撤线
     踩了九个多月。它每轮照常出现在 findings 里（条件确实成立），但只在
     false→true 那一次推。少了这道过滤，用户每天收到同一条。 */
  const pushable = findings.filter(f =>
    (f.delivery || {}).level === "L1" && f.novelty !== 0);
  let pushed = false;
  if (pushable.length) {
    /* ⚠️ 按信号类型分支。用户线的 measured.rvol 是 null，
       原来无条件 `.toFixed(1)` 会当场抛 —— 而 feed.run 吞异常，
       表现是 cronjob completed、日志空、推送没出去。 */
    const line = f => {
      const ul = (f.trigger || {}).userLine;
      if (ul) {
        const v = ul.kind === "US3" ? `${(ul.value * 100).toFixed(1)}%` : ul.value;
        const a = ul.kind === "US3" ? `${(ul.actual * 100).toFixed(1)}%` : ul.actual;
        const name = { US1: "stop line", US2: "take-profit line", US3: "drawdown line" }[ul.kind];
        return `${f.symbol} ${name} ${v} reached — now ${a}`;
      }
      const m = f.measured.move, sign = m > 0 ? "+" : "";
      const vol = f.measured.rvol == null ? "" : `  vol ${f.measured.rvol.toFixed(1)}x`;
      return `${f.symbol} ${sign}${(m * 100).toFixed(1)}%${vol}`;
    };
    const anyUL = pushable.some(f => (f.trigger || {}).userLine);
    const head = pushable.length === 1
      ? (anyUL ? `${pushable[0].symbol} reached a line you set`
               : `${pushable[0].symbol} crossed both lines`)
      : `${pushable.length} alerts`;
    const held = findings.length - pushable.length;
    await ctx.self.ts("alerts", "events").append([{
      date: Date.parse(asOfTs),                 // epoch ms —— feed 的时间戳一律用它
      title: `Portfolio Watch · ${asOfDate}`,
      body: [head, "", ...pushable.map(line), "",
             held ? `${held} more stayed on the page.` : "",
             PLAYBOOK_URL].filter(Boolean).join("\n"),
    }]);
    pushed = true;
  }

  return { asOf: asOfTs, holdings: port.holdings.length,
           triggered: findings.map(f => `${f.symbol} ${f.measured.move > 0 ? "+" : ""}${(f.measured.move * 100).toFixed(1)}%`),
           pushed, pushedCount: pushable.length, errors: errs,
           attribution: attrLog, quota: q };

  /* ── helpers ── */

  /** 该类资产在自然日 d 的收盘时刻。加密按 UTC 切，收在 D+1 00:00Z。 */
  function closeInstant(cls, d) {
    if (cls === "crypto") {
      const t = new Date(d + "T00:00:00Z"); t.setUTCDate(t.getUTCDate() + 1);
      return t.toISOString();
    }
    /* ⚠️ 签名是 (dateStr, "HH:MM:SS")。此前本文件另有一份 etStamp，参数是 (d, hour, min)
       且用 toLocaleString 走 Intl 时区库 —— 而 lib.js 开头就写着那个库不保证存在。
       两份实现、两个签名，正是 lib.js 存在的理由。 */
    return L.etStamp(d, "16:00:00");
  }
  /** 三处上限取最严。⚠️ US 从不降级；degraded 上限是 L2。 */
  /* 这一天的幅度在这只标的的历史里排第几。
     ⚠️ 用总体里的原值算，不能用 measured.move —— 那是四舍五入过的。
        掉出前 20 就返回 null，界面据此说「不在前 20」，而不是编一个名次。 */
  function dayRank(b, move) {
    const top = ((b.distribution || {}).top) || null;
    const n = b.baselineDays || 0;
    if (!Array.isArray(top) || !top.length || !n) return null;
    const a = Math.abs(move);
    const k = top.filter(x => x > a).length;
    if (k >= top.length) return null;
    return { rank: k + 1, of: n, unit: "sessions" };
  }

  function deliveryOf(b, sid) {
    const ORD = { L1: 1, L2: 2, L3: 3, L4: 4 };
    const gr  = (b.signalGrades || {})[sid];
    /* ⚠️ 失败关闭。算不出逐标的上限 = 这只标的还没评估过 → 封 L2。
       原来 `caps` 为空就 return L1，失败方向朝外，且不报错。 */
    const isUS = sid.indexOf("US") === 0;
    const g   = gr ? gr.maxDelivery : (isUS ? null : "L2");
    const deg = (b.degraded && !isUS) ? "L2" : null;
    /* ⚠️ 第三道上限：信号自身的证据等级。此前只算了两道 ——
       而这一道正是原则二「证据等级是投递上限，不是标注」的执行体。
       缺了它，一条 🟠 的信号照样能推手机，而界面上还挂着我们的证据标记。
       US 族豁免（用户自己划的线），并且 fallback_solved 的标的不得按 🟢 投递。 */
    const sigMax = isUS ? null : (SIGDEF[sid] || {}).maxDelivery || null;
    const src = (b.thresholds || {}).source;
    const fb = (!isUS && src === "fallback_solved" && (sigMax === "L1" || sigMax == null)) ? "L2" : null;
    const caps = [["symbol_grade", g], ["degraded", deg],
                  ["signal_evidence", sigMax === "L1" ? null : sigMax],
                  ["signal_evidence", fb]].filter(x => x[1]);
    if (!caps.length) return { level: "L1", cappedBy: null };
    const worst = caps.reduce((w, x) => ORD[x[1]] > ORD[w[1]] ? x : w);
    return { level: worst[1], cappedBy: worst[1] === "L1" ? null : worst[0] };
  }
});
})();
