/* 盘中 PV5：每 15 分钟一轮。
 *
 * 只取**当天**的 bar，对着初始化时算好的逐槽位基线判 —— `baselines[sym].slotBaselines`。
 * ⚠️ 不要每轮重拉 135 天分钟线去重建基线：基线属于初始化，运行期只该取当天。
 *
 * ⚠️ 盘中的线是「同一时刻」的：09:45 那根的线来自过去 90 天所有 09:45。
 *    全天混排会被开盘和收盘那两根结构性地压制。
 */
const { Feed, feedPath, makeDoc, alertOutput, str, num, messagePresentationField } = require("@alva/feed");
const http   = require("net/http");
const secret = require("secret-manager");
const alfs   = require("alfs");
const env    = require("env");
const L      = require("./lib.js");
const ATTR   = require("./attribution.js");
const UL     = require("./userlines.js");

const B = "https://data-tools.prd.arrays.org";
/* ⚠️ 从 args 读，不要写死。告警正文末尾的回链指向它 ——
   写死就等于把每个用户的告警都深链到作者那一个 playbook。
   由 `alva deploy create --args '{"root":"…","playbookUrl":"…"}'` 注入。 */
let PLAYBOOK_URL = "";
/* RTH 窗口按日期算，见 lib.js —— 写死常量另外半年整体错一小时 */

const feed = new Feed({ path: feedPath("portfolio-watch-intraday") });
feed.def("alerts", {
  events: alertOutput(makeDoc("Portfolio Watch intraday alert",
    "Holdings that crossed both intraday lines", [
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
  /* 开关要在产 finding 之前拿到 —— 原来 `cfg` 在第 280 行才读，
     而 PV5 在 167 行就 push 了。见 producer.js 同处注释。 */
  const alertCfg = (await rd("config/alerts.json").catch(() => ({}))).enabled || {};
  const sigOn = id => alertCfg[id] !== false;
  const fj   = await rd("data/findings.json");
  /* ⚠️ 上一轮的归因要在**任何改写之前**抓下来。
     第一版把它放在 `fj.findings = [...kept, ...pv5]` 之后 ——
     那时数组已经换成本轮新建的空归因，于是「搬运」搬的是一片空白，
     而全程零报错。插入一段读状态的代码时，必须看清楚中间有什么在改它。 */
  /* ⚠️ 判据是「问过没有」（generatedAt），不是「有没有内容」。
     原判据是 `summary || sources.length` —— 于是「问过了，什么都没找到」搬不过来：
     下一轮 generatedAt 回到 null，页面整块消失，而 done 里已记「调过了」不会重问。
     结果是卡片先说「未找到与这次移动相关的报道」，15 分钟后那句话没了，
     看起来像我们从来没查过。**这正是今天花一整轮建起来的那个区分。**
     notRun 故意不搬：额度用完是本轮的状态，用户调大上限后应当能重试。 */
  const prevAttr = Object.fromEntries((fj.findings || [])
    .filter(f => f.signalId === "PV5" && f.context && f.context.attribution
                 && f.context.attribution.generatedAt)
    .map(f => [f.id, f.context.attribution]));

  /* ⚠️ 必须在 deliveryOf 第一次被调用之前读。它是 const，而 deliveryOf 在扫描循环里
     就会用到 —— 声明在循环之后就是暂时性死区，运行时抛 ReferenceError，
     而 feed.run 把它吞成 completed、日志为空、什么都不写。 */
  const SIGDEF = (await rd("data/signals.json").catch(() => ({}))).signals || {};
  const lastBar = {}, evaluated = {};
  const now = Math.floor(Date.now() / 1000);
  const t0  = now - 3 * 86400;             // 三天足够覆盖当天所有 bar 与跨日边界

  async function bars(sym, cls) {
    const url = cls === "crypto"
      ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}&interval=15min&start_time=${t0}&end_time=${now + 900}&limit=1000`
      : `${B}/api/v1/stocks/kline?symbol=${sym}&interval=15min&start_time=${t0}&end_time=${now + 900}&limit=1000`;
    const r = await http.fetch(url, { headers: H });
    if (!r.ok) return { err: `HTTP ${r.status}` };
    const d = (await r.json()).data || [];
    const rows = d.map(x => [String(x.time_period_start || x.time_open).slice(0, 16),
                             +x.price_close,
                             +(x.volume_traded != null ? x.volume_traded : x.volume)]);
    rows.sort((a, b2) => a[0] < b2[0] ? -1 : 1);
    return { rows };
  }

  const pv5 = [], errs = [];
  /* 逐标的当日最强那根 —— `scan[].bar` 用它。
     ⚠️ 它有两个作用，缺了都不行：
       ① 卡上「日常波动」那一格从这里读（线 ÷ θz 反推 σ）——
          没有它整格显示破折号，看起来像上游没给
       ② 它是「盘中引擎在每一只上都跑过」的唯一证据。
          零告警那天，页面上唯一由盘中信号产生的内容就是它。 */
  const strongest = {};
  let latest = null;

  for (const h of port.holdings) {
    const cls = h.assetClass;
    /* ⚠️ ETF 不启用 PV5 —— 盘中阈值没有兜底反解规则。
       它们的 slotBaselines 本来就是空的，这里显式跳过，不靠「碰巧没有数据」。 */
    if (cls === "other") continue;
    const b = base[h.symbol] || {};
    const sb = b.slotBaselines || {};
    const th = b.thresholds || {};
    if (!Object.keys(sb).length || th.theta_z_bar == null) continue;

    const got = await bars(h.symbol, cls);
    if (got.err) { errs.push(`${h.symbol}: ${got.err}`); continue; }
    const rows = cls === "crypto" ? got.rows
      : got.rows.filter(r => {
          const [lo, hi] = L.rthWindowUTC(r[0].slice(0, 10));
          const t = r[0].slice(11);
          return t >= lo && t < hi;
        });
    if (rows.length < 2) continue;

    const day = rows[rows.length - 1][0].slice(0, 10);
    if (!latest || day > latest) latest = day;

    /* ⚠️ 盘中价格必须刷新。此前本 producer 从不改 portfolio.json，
       于是 `h.last` 整天停在日线写的收盘价 —— 拿它每 15 分钟重判一次用户线，
       判的永远是昨天那个数。持仓表上的价格同样是隔夜的。 */
    lastBar[h.symbol] = { price: rows[rows.length - 1][1], at: rows[rows.length - 1][0] + ":00Z" };

    /* ⚠️ 图画的是 `symbols/<SYM>.json` 里的分钟线，不是 findings。
       只写 findings 不刷新它，卡上的读数与图上的标记就来自两份不同的数据 ——
       实测 SOL：卡说 00:30（量 207,459，邻居的 7–20 倍），
       而图里最新一根还停在两天前，标记落到 19:45 一根平平的 bar 上。
       两个数字都"对"，指的却不是同一根。 */
    try {
      const sp = `data/symbols/${h.symbol}.json`;
      const doc = await rd(sp);
      const days = [...new Set(rows.map(r => r[0].slice(0, 10)))].slice(-3);
      doc.intraday = {
        unit: "15min", tz: "UTC", sessions: days.length,
        scope: cls === "crypto" ? "24h" : "rth",
        bars: rows.filter(r => days.includes(r[0].slice(0, 10)))
                  .map(r => ({ t: r[0], c: r[1], v: r[2] })),
      };
      await wr(sp, doc);
    } catch (e) { errs.push(`${h.symbol} intraday write: ${e.message}`); }

    /* 当天每一根都判。⚠️ 日内累积不替换 —— 只留最强那根会丢掉方向相反的早盘根。 */
    for (let i = 1; i < rows.length; i++) {
      if (rows[i][0].slice(0, 10) !== day) continue;
      if (cls !== "crypto" && rows[i - 1][0].slice(0, 10) !== day) continue;   // 不跨日算收益
      const slot = rows[i][0].slice(11, 16);
      const sbs = sb[slot];
      if (!sbs || !(sbs.sigma > 0) || !(sbs.vmed > 0)) continue;
      const ret = rows[i][1] / rows[i - 1][1] - 1;
      const z = (ret - sbs.med) / sbs.sigma;
      const rvol = rows[i][2] / sbs.vmed;
      const cur = strongest[h.symbol];
      if (!cur || Math.abs(z) > Math.abs(cur.z))
        strongest[h.symbol] = { z, rvol, slot, sigma: sbs.sigma, bars: 0 };
      /* ⚠️ 计数不能放在「换掉最强那根」的分支里 —— 换一次就清零重数，
         最强的那根恰好是最后一根时，页面会报「1 根」。
         这一格问的是「今天算了多少根」，与哪根最强无关。 */
      evaluated[h.symbol] = (evaluated[h.symbol] || 0) + 1;
      if (!(Math.abs(z) >= th.theta_z_bar && rvol >= th.theta_v_bar)) continue;
      /* 面板上 PV5 那个开关此前不接线 —— 关掉它什么也不会发生。
         关掉的含义是「别再为它告警」，读数照旧（`scan[].bar` 在下面照写）。 */
      if (!sigOn("PV5")) continue;
      const at = rows[i][0] + ":00Z";
      /* ⚠️ id 用**这根 bar 自己的**日期，不是 `day`（那是最后一根的日期）。
         序列跨 UTC 午夜时两者会不一致:23:45Z 那根会被写成次日的 id，
         而它的 triggeredAt 还是当日 —— 同一条 finding 的两个日期互相矛盾，
         去重键也就跟着错位。 */
      const barDay = rows[i][0].slice(0, 10);
      pv5.push({
        id: `${barDay}:${h.symbol}:PV5:${slot}`,
        symbol: h.symbol, assetClass: cls, signalId: "PV5", unit: "bar",
        severity: "critical", triggeredAt: at, knownAt: at,
        episodeId: `${barDay}:${h.symbol}`, novelty: null, priority: null,
        measured: { z: +z.toFixed(2), rvol: +rvol.toFixed(2), move: +ret.toFixed(5) },
        trigger: { unit: "bar", moveAt: at, thresholdSource: th.source,
                   barSlot: slot, barClose: rows[i][1] },
        delivery: deliveryOf(b, "PV5"),
        context: {
          benchmark: { symbol: null, benchmarkMove: null, symbolMove: null, applicable: false },
          sizeRank: rankIn(b, slot, ret),
          /* 契约的 context 是四个键 —— 见 producer.js 同处注释 */
          pnl: (h.shares == null || h.avgCost == null) ? null : {
            today: +(h.shares * rows[i][1] * ret).toFixed(2),
            shares: h.shares,
            lifetime: h.lifetimePnl == null ? null : h.lifetimePnl },
          attribution: { timing: "none", summary: null, sources: [], model: null, generatedAt: null },
        },
      });
    }
  }

  /* ⚠️ 读-改-写，只换掉自己那条信号的行。整体覆盖会把日线 producer 写的 PV1 冲掉，
     而冲掉的表现是「今天没有日线告警」—— 看起来像市场安静，实际是我们删了它。 */
  /* scan 行上挂盘中块。⚠️ `scan[]` 归日线 producer 所有，这里只**补一个键**，
     不重建整行 —— 重建会把日线的读数冲掉。 */
  for (const row of (fj.scan || [])) {
    const st = strongest[row.symbol];
    const b = base[row.symbol] || {};
    const th2 = b.thresholds || {};
    if (!st || th2.theta_z_bar == null) { row.bar = null; continue; }
    row.bar = {
      z: +st.z.toFixed(2), rvol: +st.rvol.toFixed(2), slot: st.slot,
      line: +(th2.theta_z_bar * st.sigma).toFixed(5),
      volumeLine: th2.theta_v_bar,
      bars: evaluated[row.symbol] || 0,
      state: pv5.some(f => f.symbol === row.symbol) ? "triggered" : "quiet",
    };
  }

  /* 把当轮的盘中价刷回持仓。
     ⚠️ **刷一半比不刷更糟。** 第一版只更新了每只标的的 last / value / lifetimePnl，
        没有重算总值、权重、盈亏与 allocation —— 页面于是同时显示新的单只数字和旧的汇总，
        两个都「对」，加起来对不上。平台的巡检机器人当场报了这条。
        一致性是原子的：要么整本账一起推进到这一刻，要么一个字都不动。 */
  let priceAt = null, touched = 0;
  const LINKED = port.linked !== false;
  for (const h of port.holdings) {
    const lb = lastBar[h.symbol];
    if (!lb) continue;
    h.last = lb.price; touched++;
    if (LINKED && h.shares != null && h.avgCost != null) {
      h.value = +(h.shares * h.last).toFixed(2);
      h.lifetimePnl = +(h.value - h.shares * h.avgCost).toFixed(2);
    }
    if (!priceAt || lb.at > priceAt) priceAt = lb.at;
  }
  if (priceAt && touched) {
    if (LINKED) {
      let total = port.cash || 0, cost = 0;
      for (const h of port.holdings) {
        if (h.value == null || h.shares == null || h.avgCost == null) continue;
        total += h.value; cost += h.shares * h.avgCost;
      }
      const fin = (v, what) => {
        if (!Number.isFinite(v)) throw new Error(`${what} 算出了 ${v} —— 拒绝写盘`);
        return +v.toFixed(2);
      };
      for (const h of port.holdings)
        h.weight = (h.value == null || !total) ? h.weight : +(h.value / total).toFixed(4);
      port.kpi = port.kpi || {};
      port.kpi.totalValue = fin(total, "kpi.totalValue");
      const pnl = total - (port.cash || 0) - cost;
      port.kpi.totalPnl = { abs: fin(pnl, "kpi.totalPnl.abs"),
                            pctOnCost: cost ? +(pnl / cost).toFixed(4) : null };
      /* allocation 的三个切面都从 value 派生，一起重算，否则饼图与表格对不上 */
      const alloc = port.allocation || {};
      if (Array.isArray(alloc.byHolding)) {
        alloc.byHolding = port.holdings.map(h => ({
          key: h.symbol, value: h.value,
          weight: (h.value == null || !total) ? null : +(h.value / total).toFixed(4) }));
      }
      for (const axis of ["byAssetClass", "byTheme"]) {
        if (!Array.isArray(alloc[axis])) continue;
        for (const row of alloc[axis]) {
          const members = row.members
            || port.holdings.filter(h => h.assetClass === row.key).map(h => h.symbol);
          const v = port.holdings
            .filter(h => members.indexOf(h.symbol) >= 0 && h.value != null)
            .reduce((a, h) => a + h.value, 0);
          row.value = +v.toFixed(2);
          row.weight = total ? +(v / total).toFixed(4) : null;
        }
      }
      port.allocation = alloc;
    }
    port.asOf = priceAt;
    await wr("data/portfolio.json", port);
  }

  /* ⚠️ 按 (signalId, unit) 过滤，不能只按 signalId。
     日线与盘中都产 US 族，只按 ID 删会把对方刚写的那条一并删掉 ——
     表现是收盘后 15 分钟，日线那张用户线卡凭空消失。 */
  /* 用户线只有这一个 producer 在产，所以整族替换 */
  const kept = (fj.findings || []).filter(f =>
    f.signalId !== "PV5" && f.signalId.indexOf("US") !== 0);
  fj.findings = [...kept, ...pv5].sort((a, b2) => a.triggeredAt < b2.triggeredAt ? -1 : 1);
  /* ── 归因 ──
     ⚠️ 与日线**共用同一份额度**（state.json 的 attributionQuota）——
        两个 cronjob 各记各的等于把 10 次变成 20 次。先到先得。
     ⚠️ 只给这一轮新出现的 bar 调。日内累积意味着上一轮已经归因过的还在列表里，
        再调一次是白花 credits，而结论不会变。 */
  const cfg = await rd("config/alerts.json").catch(() => ({}));
  const CAP = ((cfg.attribution || {}).dailyCap) || 10;
  const st = await rd("data/state.json").catch(() => ({}));
  const utcDay = new Date().toISOString().slice(0, 10);
  const q = (st.attributionQuota && st.attributionQuota.day === utcDay)
    ? st.attributionQuota : { day: utcDay, used: 0 };
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
  /* ⚠️ 每轮都从零重建 pv5，归因字段是空的。跳过「已归因过」的那些时，
     必须把上一轮的结果搬过来 —— 否则那条去重标记只做了一半：
     记住了「调过了」，却把调出来的东西丢了。
     与「标记为已推送但没推」是同一个形状：标记记下了，载荷没带上。 */
  const attrLog = [];
  for (const f of pv5) {
    if (prevAttr[f.id]) { f.context.attribution = prevAttr[f.id]; continue; }
    if ((f.delivery || {}).level !== "L1" || done[f.id]) continue;
    if (q.used >= CAP) { f.context.attribution.notRun = "daily_cap"; continue; }
    q.used += 1; done[f.id] = 1;
    const h2 = port.holdings.find(x => x.symbol === f.symbol) || {};
    try {
      const out = await ATTR.attribute({ finding: f, symbol: f.symbol,
        name: h2.name || f.symbol, assetClass: f.assetClass, headers: H });
      f.context.attribution = out.attribution;
      attrLog.push({ sym: f.symbol, slot: f.trigger.barSlot, ...out.checks });
    } catch (e) {
      f.context.attribution.notRun = null;
      attrLog.push({ sym: f.symbol, outcome: "call_failed", err: String(e.message).slice(0, 120) });
    }
  }
  /* ── 用户线 ──
     盘中与日线共用 userlines.js。盘中用最新一根 bar 的价格，所以跨越能在盘中就被抓到 ——
     等到收盘再判，止损线的意义已经过了大半。
     ⚠️ 必须在写 state.json 之前 —— 开关位就存在同一个文件里。 */
  const ulOut = UL.evaluate({
    holdings: port.holdings, userLines: (cfg.userLines || {}),
    enabled: (cfg.enabled || {}), prevKeys: st.keys,
    nowIso: priceAt || new Date().toISOString() });
  st.keys = ulOut.keys;
  fj.findings = [...fj.findings, ...ulOut.findings]
    .sort((a, b2) => a.triggeredAt < b2.triggeredAt ? -1 : 1);

  st.attributionQuota = q;
  await wr("data/state.json", st);
  await ctx.kv.put(kvKey("attributed"), JSON.stringify(done));


  /* ⚠️ `fj` 是本轮开头读的。重读之后只替换自己那两族，别人的原样留下。
     归因写在 `pv5[]` 的元素上，所以要用 `fj.findings` 里 PV5/US 那部分作为 mine。 */
  await L.commitFindings(rd, wr, {
    owns: f => f.signalId === "PV5" || f.signalId.indexOf("US") === 0,
    mine: (fj.findings || []).filter(
      f => f.signalId === "PV5" || f.signalId.indexOf("US") === 0),
    /* 这一格归盘中，整行归日线 —— 贴到重读后的行上 */
    scanBar: Object.fromEntries((fj.scan || []).map(r => [r.symbol, r.bar ?? null])),
  });

  const meta = await rd("data/meta.json");
  /* ⚠️ 三种结局分开记，并且要**落盘**。
     实测：summary 为空，而 outcome 只活在返回值里（feed.run 吞掉了它）——
     只能再花一次 credits 重跑才查得出是解析失败、调用失败还是被硬门拦。 */
  meta.attributionRuns = [...(meta.attributionRuns || []).slice(-20), ...attrLog];
  meta.producedSignals = [...new Set([...(meta.producedSignals || []), "PV5"])];
  /* ⚠️ 撞到额度上限是**用户看得见的后果**（后面的告警没有解释段落），
     不是内部计数。页面为它写好了文案，而此前没有任何脚本发得出这条 gap。
     和欠条型 gap 一样，明天额度重置就该撕掉 —— 只并不清的话它会永久留着。 */
  {
    const _g = new Set(meta.gaps || []);
    for (const x of [..._g]) if (String(x).startsWith("attribution_daily_cap")) _g.delete(x);
    if (q.used >= CAP) _g.add(`attribution_daily_cap:${CAP}`);
    meta.gaps = [..._g];
  }
  /* ⚠️ 谁往这份产物里加东西，谁就把 `generatedAt` 推到现在。
     契约:「No finding may be timestamped after generatedAt」——
     只让日线写它，此后每一轮加进来的卡都比它晚。 */
  meta.generatedAt = new Date().toISOString();
  /* ⚠️ `prices` 也要推 —— **这一轮确实刷了价格**:上面写了 `h.last`、`h.value`、
     `kpi.totalValue`、权重与配置。只写 `intraday` 的话，页头那个「prices … ET」
     读的是日线收盘，而屏幕上那些数是这一轮刷的：**标签比数据旧十个小时**。

     它不冲突于「行情什么时候的」:加密 24 小时在动，持仓市值本来就跟着变；
     美股收盘后不动，戳往前走也不会让任何数字变。**周六戳走、数字不动，
     恰恰是对的** —— 那说明我们看过了，而不是我们停在周五。

     ⚠️ 日线读数用的是哪根 bar 是另一件事，它在 `findings.asOf` 与 `scan[].asOf`，
        不靠这个戳表达。 */
  meta.freshness = Object.assign({}, meta.freshness,
    { intraday: new Date().toISOString(), prices: new Date().toISOString() });
  await L.commitMeta(rd, wr, meta, {
    keys: ["attributionRuns"],
    freshness: ["prices", "intraday"],
    signals: ["PV5"],
    gapPrefixes: ["attribution_daily_cap"],
  });

  /* 推送：只推真会响手机的，而且**只推这一轮新出现的那几根** ——
     日内累积意味着上一轮推过的还在列表里，再推一次就是重复打扰。 */
  const seen = JSON.parse((await ctx.kv.load(kvKey("pushedBars"))) || "{}");
  /* ⚠️ 用户线也要在这里推。第一版只推 pv5，把 ulOut.pushable 丢掉了 ——
     而盘中每 15 分钟先跑，它已经把开关位翻成 on；等日线收盘再看时
     novelty 已经是 0，于是被过滤掉。**结果是这一族算得出、存得下、
     画得出来，却永远到不了手机。** 标记记下了，载荷没带上。 */
  const freshPv5 = pv5.filter(f => (f.delivery || {}).level === "L1" && !seen[f.id]);
  const freshUl  = (ulOut.pushable || []).filter(f => !seen[f.id]);
  const fresh    = [...freshPv5, ...freshUl];
  if (fresh.length) {
    const line = f => {
      const ul = (f.trigger || {}).userLine;
      if (ul) {
        const fmt = v => ul.kind === "US3" ? `${(v * 100).toFixed(1)}%` : String(v);
        const name = { US1: "stop line", US2: "take-profit line", US3: "drawdown line" }[ul.kind];
        return `${f.symbol} ${name} ${fmt(ul.value)} reached — now ${fmt(ul.actual)}`;
      }
      return `${f.symbol} ${f.measured.move > 0 ? "+" : ""}` +
             `${(f.measured.move * 100).toFixed(1)}%  ${f.trigger.barSlot} UTC  vol ${f.measured.rvol.toFixed(1)}x`;
    };
    const head = fresh.length === 1
      ? (freshUl.length ? `${fresh[0].symbol} reached a line you set`
                        : `${fresh[0].symbol} crossed both intraday lines`)
      : `${fresh.length} intraday alerts`;
    await ctx.self.ts("alerts", "events").append([{
      date: Date.now(),
      title: `Portfolio Watch · intraday`,
      body: [head, "", ...fresh.map(line), "", PLAYBOOK_URL].filter(Boolean).join("\n"),
    }]);
    for (const f of fresh) seen[f.id] = 1;
    await ctx.kv.put(kvKey("pushedBars"), JSON.stringify(seen));
  }

  /* 这一根在**同一时刻**的历史里排第几。
     ⚠️ 只有前 20 是精确的 —— 契约里每个槽位存的是 top 20（存全量太大）。
        掉出前 20 就返回 null，界面据此说「不在这个时刻的前 20」，
        而不是编一个名次出来。排名只在很靠前时才有意义。 */
  function rankIn(b, slot, ret) {
    const sl = ((b.distributionBar || {}).slots || {})[slot];
    if (!sl || !Array.isArray(sl.top) || !sl.n) return null;
    const a = Math.abs(ret);
    const k = sl.top.filter(x => x > a).length;
    if (k >= sl.top.length) return null;          // 掉出前 20，说不出精确名次
    return { rank: k + 1, of: sl.n, unit: "bars" };
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
