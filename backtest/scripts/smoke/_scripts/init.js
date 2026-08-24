/* Initialization — runs ONCE, before any cronjob exists.
 *
 * The cron producers only do increments. Everything they read has to exist first, and the
 * page rejects its whole load if any required file is missing — so a deployment with
 * cronjobs but no initialization shows "Data did not load", not a partial page.
 *
 * This writes: signals · baselines · portfolio · findings · series · news · market · meta
 * plus data/symbols/<SYM>.json for every holding.
 *
 * ⚠️ The expensive, easy-to-get-wrong part is `signalGrades` — the per-symbol delivery
 *    ceiling. It gates every push, a wrong implementation changes it silently, and the
 *    criterion sits on a hard line at 1.0. The arithmetic lives in lib.js so that this
 *    script and any reimplementation cannot drift.
 */
const { Feed, feedPath, makeDoc, str, num } = require("@alva/feed");
const http = require("net/http");
const secret = require("secret-manager");
const alfs = require("alfs");
const env = require("env");
const L = require("./lib.js");

const B = "https://data-tools.prd.arrays.org";
const W = 90, F = 5, MIN_BASELINE = 60, RHO_LO = 0.02, RHO_HI = 0.40;
const THETA = {
  us_equity: { theta_z: 1.5, theta_v: 2.0, theta_z_bar: 4.75, theta_v_bar: 2.0 },
  crypto:    { theta_z: 1.5, theta_v: 3.0, theta_z_bar: 10.0, theta_v_bar: 3.0 },
  other:     { theta_z: 1.5, theta_v: 2.0 },   // no intraday fallback — PV5 stays off
};

/* ⚠️ All 13, always — scope is the `assetClass` field, never omission. The page's type
   labels, its own ID-whitelist audit, and the eval whitelist all read this one file. */
const US = "us_equity", CR = "crypto", OT = "other";
/* ⚠️ `maxDelivery` 是**三道投递上限之一**（另两道是 symbol_grade 与 degraded），
   它决定这条信号实际投到哪一层。而 signal-spec.md 是已定案信号的唯一定义处 ——
   这张表只是它的可执行副本，两处不一致时**以 spec 为准**。
   2026-08-23 实测漂了两处:EV1 这里 L3 而 spec 是 L4、PF3 这里 L2 而 spec 是 L3。
   后果是 EV1 会出现在持仓页（spec 说它属于记录页）、PF3 会进概览信号流（spec 说不进）。
   `check_consistency.py` 现在逐行比对这两处，漂了就红。 */
const CATALOG = [
  ["PV1","价量异动 · 日线","Price-volume move · daily","alert",[US,CR,OT],"daily","green","critical","L1",true],
  ["PV5","价量异动 · 盘中 15 分钟","Price-volume move · 15-min","alert",[US,CR],"bar","green","critical","L1",true],
  ["PV3","幅度标注","Size marker","display",[US,CR,OT],"daily","na",null,"L3",false],
  ["PV4","覆盖标注","Coverage marker","display",[US,CR,OT],"daily","na",null,"L3",false],
  ["EV1","内部人簇买","Insider cluster buy","record",[US],"daily","na",null,"L4",false],
  ["EV4","财报日历","Earnings calendar","calendar",[US],"daily","na","informational","L1",true],
  ["EV6","公司新闻","Company news","attribution",[US],"daily","yellow",null,"L3",false],
  ["DR1","费率极端","Funding extremes","display",[CR],"daily","amber",null,"L3",false],
  /* ⚠️ PF2/PF3 were missing from the catalogue this replaces, which is why the count read 11
     against a spec that says 13. They stay listed even where theme data is unreachable —
     a catalogue entry says the signal exists, findings say whether it fired. */
  ["PF2","主题集中度","Theme concentration","display",[US],"daily","amber",null,"L3",false],
  ["PF3","主题共振","Theme resonance","display",[US],"daily","amber",null,"L3",false],
  /* ⚠️ Critical for the whole family — the user drew these lines. The table this replaces
     said "warning", against signal-spec → US1, US2, US3. */
  ["US1","止损线","Stop line","alert",[US,CR,OT],"daily","na","critical","L1",true],
  ["US2","止盈线","Take-profit line","alert",[US,CR,OT],"daily","na","critical","L1",true],
  ["US3","回撤线","Drawdown line","alert",[US,CR,OT],"daily","na","critical","L1",true],
];

const feed = new Feed({ path: feedPath("portfolio-watch-init") });

feed.run(async (ctx, args = {}) => {
  const A = Object.assign({}, (env.args || {}), args);
  const ROOT = A.root;
  if (!ROOT) throw new Error(
    "missing args.root — pass the playbook's absolute ALFS path via "
    + "alva deploy create --args '{\"root\":\"/alva/home/<user>/playbooks/<name>\"}'");

  const H = { Authorization: "Bearer " + secret.loadPlaintext("ARRAYS_JWT") };
  const wr = async (p, o) => alfs.writeFile(`${ROOT}/${p}`, JSON.stringify(o));
  const rd = async p => JSON.parse(await alfs.readFile(`${ROOT}/${p}`));

  /* Holdings come from args, or from a portfolio.json a previous run left behind.
     Shape: [{symbol, assetClass, name, shares, avgCost}] */
  let book = A.holdings;
  if (!book) { try { book = (await rd("data/portfolio.json")).holdings; } catch (e) { book = null; } }
  if (!Array.isArray(book) || !book.length)
    throw new Error("no holdings — pass args.holdings [{symbol, assetClass, …}] "
                    + "or write data/portfolio.json first");

  const errs = [], gaps = [];
  const get = async (path) => {
    try {
      const r = await http.fetch(B + path, { headers: H });
      if (!r.ok) { errs.push(`${path.split("?")[0].split("/").pop()} ${r.status}`); return []; }
      return (await r.json()).data || [];
    } catch (e) { errs.push(e.message); return []; }
  };

  const nowSec = Math.floor(Date.now() / 1000);
  /* ⚠️ `start_time=0` 返回 400 —— 端点不收纪元零。用一个真实的早期时刻，
     2018-01-01 是本项目样本池的起点，早于它的数据端点本来也没有。 */
  const EPOCH = 1514764800;
  const daily = async (sym, cls) => {
    const p = cls === "crypto"
      ? `/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}USDT&interval=1d&start_time=${EPOCH}&end_time=${nowSec}&limit=3000`
      : `/api/v1/stocks/kline?symbol=${sym}&interval=1d&start_time=${EPOCH}&end_time=${nowSec}&limit=3000`;
    /* [date, close, volume, open, high, low] —— OHL **appended**, never inserted.
       Every existing reader indexes r[0]/r[1]/r[2]; appending leaves them untouched,
       whereas a field whitelist (`{d, c, v}`) would silently drop whatever is added next
       and the loss would surface as an em dash on the page, i.e. as if the endpoint
       had returned nothing. */
    const rows = (await get(p)).map(x => cls === "crypto"
      ? [String(x.time_open).slice(0, 10), +x.price_close, +x.volume,
         +x.price_open, +x.price_high, +x.price_low]
      : [String(x.time_period_start).slice(0, 10), +x.price_close, +x.volume_traded,
         +x.price_open, +x.price_high, +x.price_low]);
    rows.sort((a, b) => a[0] < b[0] ? -1 : 1);      // endpoint returns newest-first
    return rows;
  };
  /* 窗口的单位是**同槽位样本数**，不是日历天。signal-spec §PV5 写「前 90 天同一时刻」——
     对 24 小时市场这两个说法一样，对美股不一样：90 个日历日只有约 62 个交易日
     （实测 NVDA 每槽 61–62 个）。θz_bar = 4.75 是在 92 只美股上反解的，
     用的是 90 个**样本**的窗口，所以按日历天截会让美股的尺子短三分之一。

     ⚠️ 这是同一个错误的第三次变形：先是 `limit` 截断，再是把窗口写成 150，
        现在是单位选错。三次都不报错，都要把两本账并排看才看得见。
     取数按日历天（够就行），落基线时按样本数截。 */
  const SLOT_SAMPLES = 90;
  const fetchDays = cls => cls === "crypto" ? 95 : 140;   // 各自留出足够富余凑满 90 个样本
  const intraday = async (sym, cls) => {
    /* ⚠️ **Ask for 150 days in one call and crypto silently gets 31.**
       `limit=3000` is a row cap, and crypto trades 96 fifteen-minute bars a day,
       so one request can only ever carry 31.25 days. US equities have ~26 RTH bars
       a day, so 150 days is ~2,700 rows and the same call returns the whole window.
       The result was that the same skill measured a crypto book against a one-month
       ruler and a stock book against a five-month one — nothing errored, and the
       recorded `n` (31) was honest, so only comparing two books side by side showed it.
       Measured cost of that: on a BTC/SOL/DOGE book the short window shrank σ enough
       to turn |z| = 7.0–7.3 bars into 10.3–16.6, i.e. three PV5 alerts in a morning
       where the intended window says none.
       Segment so the requested window actually arrives. 25 days keeps crypto at
       2,400 rows — under the cap with room for a venue that posts extra bars.
       ⚠️ The first fix segmented to 150 days, which only moved the disagreement:
          the spec says 90 and the thresholds were solved on 90. Getting more
          history is not the goal — matching the ruler the threshold was
          validated against is. */
    const DAYS = fetchDays(cls);
    const CH = cls === "crypto" ? 25 : 45;
    const seen = new Map();
    let chunks = 0, failed = 0;
    for (let off = 0; off < DAYS; off += CH) {
      const e = nowSec - off * 86400;
      const b = nowSec - Math.min(DAYS, off + CH) * 86400;
      const p = cls === "crypto"
        ? `/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}USDT&interval=15min&start_time=${b}&end_time=${e}&limit=3000`
        : `/api/v1/stocks/kline?symbol=${sym}&interval=15min&start_time=${b}&end_time=${e}&limit=3000`;
      chunks++;
      const got = await get(p);
      /* ⚠️ `get()` returns [] both when the segment is genuinely empty and when the
         request failed — it only pushes to `errs`. Collapsing those two is how a
         half-length baseline passes for a full one. An empty segment inside a
         150-day crypto window is not a real state, so count it as failed. */
      if (!got.length) { failed++; continue; }
      for (const x of got) {
        const row = cls === "crypto"
          ? [String(x.time_open).slice(0, 16), +x.price_close, +x.volume]
          : [String(x.time_period_start).slice(0, 16), +x.price_close, +x.volume_traded];
        seen.set(row[0], row);                 // segments touch at the seam; key by bar
      }
    }
    let rows = [...seen.values()].sort((a, b) => a[0] < b[0] ? -1 : 1);
    if (cls !== "crypto") rows = rows.filter(r => {          // RTH only, derived from ET
      const [lo, hi] = L.rthWindowUTC(r[0].slice(0, 10));
      const t = r[0].slice(11);
      return t >= lo && t < hi;
    });
    /* What actually arrived, so a short ruler is a fact on the page and not a silence. */
    rows.coverage = {
      askedDays: DAYS, askedSamples: SLOT_SAMPLES, chunks, failedChunks: failed,
      spanDays: rows.length
        ? +((new Date(rows[rows.length - 1][0] + ":00Z") - new Date(rows[0][0] + ":00Z"))
            / 86400000).toFixed(1)
        : 0,
    };
    return rows;
  };

  /* fired() for the daily tier — a rolling robust baseline, recomputed at each index so it
     matches what the runtime does rather than a single whole-series baseline */
  const firedDaily = (c, v, th) => (t) => {
    if (t < W + 1) return false;
    const r = L.returns(c);
    const w = r.slice(t - W - 1, t - 1);
    if (w.length !== W) return false;
    const { med, sigma } = L.robust(w);
    if (!(sigma > 0)) return false;
    const vm = L.median(v.slice(t - W, t));
    if (!(vm > 0)) return false;
    return Math.abs((r[t - 1] - med) / sigma) >= th.theta_z && v[t] / vm >= th.theta_v;
  };

  const baselines = {}, symbolDocs = {};
  for (const h of book) {
    const sym = h.symbol, cls = h.assetClass || "us_equity";
    const th = THETA[cls] || THETA.other;
    const rows = await daily(sym, cls);

    /* The candle chart on tab 2 and the row sparkline both read from the contract — the page
       has no price series of its own to cut one from. Writing `kline: []` leaves a blank chart
       that looks exactly like an upstream outage.

       ⚠️ Captured **before** the insufficient-baseline return, because "cannot compute a
       baseline" and "cannot draw a chart" are different statements. A newly listed symbol has
       too few sessions to solve thresholds and still has bars worth drawing; letting one
       `continue` swallow both makes the page claim the second when only the first is true. */
    if (rows.length) {
      const cc = rows.map(r => r[1]);
      symbolDocs[sym] = Object.assign(symbolDocs[sym] || {}, {
        kline: rows.slice(-502).map(r => ({ d: r[0], o: r[3], h: r[4], l: r[5], c: r[1], v: r[2] })),
        spark: cc.slice(-30),
        low52: Math.min(...cc.slice(-252)),
      });
    }

    if (rows.length < MIN_BASELINE) {
      baselines[sym] = { baselineDays: rows.length, usable: false,
                         m23: { rho: null, verdict: "insufficient_sample", n: rows.length },
                         thresholds: { theta_z: th.theta_z, theta_v: th.theta_v,
                                       source: cls === "other" ? "fallback_solved" : "validated" },
                         signalGrades: {}, degraded: "short_baseline" };
      gaps.push(`insufficient_baseline:${sym}:${rows.length}`);
      continue;
    }
    const c = rows.map(r => r[1]), v = rows.map(r => r[2]);
    const n = c.length, r = L.returns(c);
    const { sigma } = L.robust(r.slice(-W));
    const ann = sigma * Math.sqrt(cls === "crypto" ? 365 : 252);

    /* rho over the last 504 sessions, at theta_z = 1.5 — the fixed value M23 is defined on */
    const zs = [];
    for (let t = Math.max(W + 1, n - 504); t < n; t++) {
      const w = r.slice(t - W - 1, t - 1);
      if (w.length !== W) continue;
      const rb = L.robust(w);
      if (!(rb.sigma > 0)) continue;
      zs.push(Math.abs((r[t - 1] - rb.med) / rb.sigma));
    }
    const rho = zs.length >= 250 ? +(zs.filter(x => x >= 1.5).length / zs.length).toFixed(4) : null;
    const m23 = { rho, n: zs.length,
      verdict: rho == null ? "insufficient_sample"
             : rho < RHO_LO ? "too_tight" : rho > RHO_HI ? "too_loose" : "pass" };

    const grades = {};
    const gPV1 = L.grade(c, v, firedDaily(c, v, th), { W, F, B: 20000, seed: L.seedFor(sym, "PV1") });
    if (gPV1) grades.PV1 = gPV1;

    /* ── PV5 is graded on the series it fires on ────────────────────────────────
       ⚠️ Not on daily data. Grading it there measures a different signal, and it is why
       PV5 grades were absent — which silenced the whole family once a missing grade began
       capping at L2. Baselines are per time-of-day slot, so the same-slot history is what
       the rolling window has to be. */
    const slotBaselines = {}, distributionBar = { unit: "15min", tz: "UTC", slots: {} };
    let pv5Hits = [];
    let barCoverage = null;
    if (cls !== "other") {
      const bars = await intraday(sym, cls);
      barCoverage = bars.coverage
        || { askedDays: null, askedSamples: SLOT_SAMPLES, chunks: 0, failedChunks: 0, spanDays: 0 };
      if (bars.length > W) {
        const bySlot = {};
        for (let i = 1; i < bars.length; i++) {
          /* ⚠️ 只对有隔夜缺口的市场设防。加密 24 小时连续，23:45→00:00 是一段
             真实收益，不是跳空 —— 无条件跳过会让 00:00 那个槽位一个样本都攒不到,
             于是它没有基线(实测:加密 95 槽而不是 96)。而运行期
             `producer-intraday.js` 的守卫本来就是 `cls !== "crypto"` ——
             两边不一致的后果是 00:00 那根**永远评不出读数**,而且是静默的:
             `sbs` 取不到就 continue,看起来跟「那根没触发」一模一样。 */
          if (cls !== "crypto"
              && bars[i][0].slice(0, 10) !== bars[i - 1][0].slice(0, 10)) continue;
          const slot = bars[i][0].slice(11, 16);
          (bySlot[slot] = bySlot[slot] || []).push({ i, ret: bars[i][1] / bars[i - 1][1] - 1, v: bars[i][2] });
        }
        for (const slot of Object.keys(bySlot)) {
          /* ⚠️ 截到最近 90 个样本。不截的话窗口长度就是「取回来多少天」的函数，
             而那随资产类别、交易日历、端点当天心情变化 —— 两本账的尺子又不一样长了。
             spec 定的是 90，就截到 90。 */
          const xs = bySlot[slot].slice(-SLOT_SAMPLES);
          if (xs.length < 30) continue;               // no reading under 30 same-slot samples
          const rb = L.robust(xs.map(x => x.ret));
          const vmed = L.median(xs.map(x => x.v));
          if (!(rb.sigma > 0) || !(vmed > 0)) continue;
          slotBaselines[slot] = { med: rb.med, sigma: rb.sigma, vmed, n: xs.length };
          const abs = xs.map(x => Math.abs(x.ret)).sort((a, b) => b - a);
          distributionBar.slots[slot] = { n: xs.length, top: abs.slice(0, 20),
            p50: L.median(abs), p95: abs[Math.floor(abs.length * 0.05)] };
        }
        /* ⚠️ 短了要说出来，而且要按**样本**说 —— 那才是窗口的单位。
           尺子短不是同一个答案的粗糙版，是另一个答案：σ 收窄，同一根 bar 的 |z| 变大，
           告警变多。报的是实际攒到的最少那个槽位，不是平均 —— 平均会把一个空槽位
           摊平到看不见，而正是那个槽位决定某个时刻能不能出读数。 */
        const gotN = Object.values(slotBaselines).map(x => x.n);
        barCoverage.slots = gotN.length;
        barCoverage.samplesMin = gotN.length ? Math.min(...gotN) : 0;
        if (gotN.length && barCoverage.samplesMin < SLOT_SAMPLES)
          gaps.push(`intraday_history_short:${sym},${barCoverage.samplesMin},${SLOT_SAMPLES}`);
        const bc = bars.map(b => b[1]), bv = bars.map(b => b[2]);
        const firedBar = (t) => {
          const slot = bars[t] && bars[t][0].slice(11, 16);
          const sb = slotBaselines[slot];
          if (!sb) return false;
          if (bars[t][0].slice(0, 10) !== bars[t - 1][0].slice(0, 10)) return false;
          const ret = bc[t] / bc[t - 1] - 1;
          return Math.abs((ret - sb.med) / sb.sigma) >= th.theta_z_bar
                 && bv[t] / sb.vmed >= th.theta_v_bar;
        };
        const gPV5 = L.grade(bc, bv, firedBar, { W, F, B: 20000, seed: L.seedFor(sym, "PV5") });
        if (gPV5) grades.PV5 = gPV5;
        else gaps.push(`pv5_grade_unavailable:${sym}`);

        /* Replay the bars we just graded on and keep the days that fired. Without this the
           page's alert-history chart has no markers and the row reads "0 in two years" —
           and a zero is worse than a blank: a blank is an absence, a zero is a wrong answer.

           ⚠️ Counted in **days**, not bars, because `windowSessions` next to it is a day
           count — two numbers under one label have to share a unit. Several bars can fire
           in one session; the strongest by |z| is the one the day is represented by. */
        const pv5ByDay = {};
        for (let t = 1; t < bars.length; t++) {
          if (!firedBar(t)) continue;
          const sb = slotBaselines[bars[t][0].slice(11, 16)];
          const ret = bc[t] / bc[t - 1] - 1;
          const z = (ret - sb.med) / sb.sigma;
          const d = bars[t][0].slice(0, 10);
          if (!pv5ByDay[d] || Math.abs(z) > Math.abs(pv5ByDay[d].z)) {
            pv5ByDay[d] = { d, signalId: "PV5", z: +z.toFixed(2), move: +ret.toFixed(5),
                            rvol: +(bv[t] / sb.vmed).toFixed(2),
                            priceLine: +(th.theta_z_bar * sb.sigma).toFixed(5),
                            volLine: th.theta_v_bar };
          }
        }
        pv5Hits = Object.values(pv5ByDay);
        symbolDocs[sym] = Object.assign(symbolDocs[sym] || {},
          { intradayBars: bars.slice(-3 * 26), pv5From: bars.length ? bars[0][0].slice(0, 10) : null });
      }
    }


    /* ── 历史回放 ─────────────────────────────────────────────────────────
       ⚠️ 用的是 `L.reading` + `L.firedPV1`,也就是**日线 producer 每天跑的那两个函数**,
          不是另写一份判据。另写一份的后果不是「算得不一样」,是
          「历史说这天触发过、今天同样的读数说没触发」—— 而两个数会同时出现在一张卡上。
       ⚠️ 切片是有界的(W+2 根):`reading` 只看最后 W+1 个收益,
          给它 92 根与给它 2171 根返回同一个读数,而后者是 O(n²)。 */
    const PV1_WINDOW = 502;
    const pv1From = Math.max(W + 1, n - PV1_WINDOW);
    const pv1Hits = [];
    for (let t = pv1From; t < n; t++) {
      const rdg = L.reading(c.slice(t - W - 1, t + 1), v.slice(t - W - 1, t + 1), W);
      if (!L.firedPV1(rdg, th.theta_z, th.theta_v)) continue;
      pv1Hits.push({ d: rows[t][0], signalId: "PV1", z: +rdg.z.toFixed(2),
                     move: +rdg.move.toFixed(5), rvol: +rdg.rvol.toFixed(2),
                     priceLine: +(th.theta_z * rdg.sigma).toFixed(5), volLine: th.theta_v });
    }
    /* 一天最多一条,两族按日期归并 —— 图上一天一个位置,同一天两条会叠在一起 */
    const alertHistory = [...pv1Hits, ...pv5Hits].sort((a, b) => a.d < b.d ? -1 : 1);
    const last7Days = new Set(rows.slice(-7).map(x => x[0]));
    const histTriggers = {
      PV1: pv1Hits.length, PV5: pv5Hits.length,
      /* ⚠️ 数的是**真判过**的天数,不是 min(n, 502)。
         历史刚好 502 天的标的,前 90 天在基线热身期里judge不了 ——
         写 502 而只判了 411,读者会拿分子除以一个从没发生过的分母。 */
      windowSessions: n - pv1From,
      last7: { PV1: pv1Hits.filter(x => last7Days.has(x.d)).length,
               PV5: pv5Hits.filter(x => last7Days.has(x.d)).length },
    };
    symbolDocs[sym] = Object.assign(symbolDocs[sym] || {}, { alertHistory });

    const last = c[n - 1];
    const high = Math.max(...c.slice(-252));
    baselines[sym] = {
      sigmaRobust: +sigma.toFixed(6), sigmaAnn: +ann.toFixed(4),
      baselineDays: n, usable: n >= MIN_BASELINE && m23.verdict === "pass",
      m23,
      thresholds: { theta_z: th.theta_z, theta_v: th.theta_v,
                    theta_z_bar: th.theta_z_bar == null ? null : th.theta_z_bar,
                    theta_v_bar: th.theta_v_bar == null ? null : th.theta_v_bar,
                    source: cls === "other" ? "fallback_solved" : "validated" },
      signalGrades: grades,
      triggerLine: {
        session: { price: +(th.theta_z * sigma).toFixed(5), volume: th.theta_v },
        bar: th.theta_z_bar == null ? null : { price: null, volume: th.theta_v_bar },
      },
      slotBaselines, distributionBar, barCoverage,
      historicalTriggers: histTriggers,
      degraded: m23.verdict === "too_loose" ? "m23_loose"
              : m23.verdict === "too_tight" ? "m23_strict"
              : ann > (cls === "crypto" ? 0.928 : 0.50) ? "high_vol" : null,
      _last: last, _high: high,
    };
  }

  /* ── files the page requires ─────────────────────────────────────────── */
  await wr("data/signals.json", { generatedFrom: "signal-spec.md",
    signals: Object.fromEntries(CATALOG.map(([id, zh, en, typ, ac, gran, ev, sev, md, push]) =>
      [id, { name: { zh, en }, type: typ, assetClass: ac, granularity: gran,
             evidence: ev, severity: sev, maxDelivery: md, pushable: push }])) });

  const asOf = new Date().toISOString();
  /* ── 图标 ─────────────────────────────────────────────────────────────
     ⚠️ 规格原来把这件事交给 agent「你知道 NVDA 是什么」，却没给可用的 URL ——
        于是**四轮真跑里每一本账的每一只标的 logo 都是 null**，页面一律画字母块。
        字母块本身是正经设计，不是故障态；但一个永远为 null 的字段等于一条
        没人走过的分支，spec 自己就是这么写的。
     这件事是机械的，不该交给判断:
        美股与新股  storage 那个 pattern 直接成立（实测 NVDA/AAPL/MSFT/TSLA/AMD/
                    KLAR/CHYM 全 200）
        ETF        同一个 pattern **全部 404**（SPY/QQQ/GLD/TLT/XLE/IWM 实测）
        加密        要 CoinMarketCap 的数字 id，从代号推不出来
     ⚠️ 所以必须**先探再填**。照 pattern 硬填，ETF 那一格就是一张碎图 ——
        那比字母块糟得多:字母块是设计，碎图是故障。 */
  const CMC = { BTC: 1, ETH: 1027, SOL: 5426, DOGE: 74, XRP: 52, ADA: 2010, AVAX: 5805,
                LINK: 1975, DOT: 6636, MATIC: 3890, LTC: 2, BCH: 1831, TRX: 1958,
                SHIB: 5994, UNI: 7083, ATOM: 3794, ETC: 1321, XLM: 512, NEAR: 6535,
                APT: 21794, ARB: 11841, OP: 11840, SUI: 20947, PEPE: 24478, TON: 11419 };
  const logoOf = async (h) => {
    if (h.logo) return h.logo;                       // 调用方给了就用它的
    const cls = h.assetClass || "us_equity";
    const url = cls === "crypto"
      ? (CMC[h.symbol] ? `https://s2.coinmarketcap.com/static/img/coins/64x64/${CMC[h.symbol]}.png` : null)
      : `https://storage.googleapis.com/arrays-public-assets/logos/${h.symbol}.svg`;
    if (!url) return null;
    try {
      const r = await http.fetch(url, { method: "HEAD" });
      return r.ok ? url : null;
    } catch (e) { return null; }
  };
  const logos = {};
  for (const h of book) logos[h.symbol] = await logoOf(h);
  const _nLogo = Object.values(logos).filter(Boolean).length;
  if (!_nLogo) gaps.push("logos_unavailable");

  const holdings = book.map(h => {
    const b = baselines[h.symbol] || {};
    const last = b._last == null ? null : b._last;
    const shares = h.shares == null ? null : h.shares;
    const value = (shares != null && last != null) ? +(shares * last).toFixed(2) : null;
    return { symbol: h.symbol, name: h.name || h.symbol, assetClass: h.assetClass || "us_equity",
             logo: logos[h.symbol] || null, last, todayPct: null, fiveDayPct: null,
             shares, avgCost: h.avgCost == null ? null : h.avgCost, value,
             weight: null,
             lifetimePnl: (value != null && h.avgCost != null)
               ? +(value - shares * h.avgCost).toFixed(2) : null,
             vol30d: b.sigmaRobust == null ? null : +b.sigmaRobust.toFixed(4),
             fromHighPct: (last != null && b._high) ? +((last / b._high) - 1).toFixed(4) : null,
             /* theme 只在账本给了、且是美股个股时才带 —— 缺省整个不写这个键，
                不写 null:契约靠键存不存在区分「不适用」与「暂时没有」 */
             ...(h.theme && (h.assetClass || "us_equity") === "us_equity"
                 ? { theme: h.theme } : {}),
             spark: (symbolDocs[h.symbol] || {}).spark || [], notes: [] };
  });
  const linked = holdings.some(h => h.shares != null);
  let total = A.cash || 0;
  for (const h of holdings) if (h.value != null) total += h.value;
  for (const h of holdings)
    h.weight = linked && total ? +(h.value / total).toFixed(4)
                               : +(1 / holdings.length).toFixed(4);
  await wr("data/portfolio.json", {
    linked, asOf, cash: A.cash || 0,
    weightSource: linked && total ? "value" : "equal",
    kpi: linked && total
      ? { totalValue: +total.toFixed(2), totalPnl: null, todayPnl: null, fromHigh: null }
      : { fromHigh: null, totalValue: null, totalPnl: null, todayPnl: null },
    holdings,
    allocation: {
      byHolding: holdings.map(h => ({ key: h.symbol, value: h.value, weight: h.weight })),
      byAssetClass: [...new Set(holdings.map(h => h.assetClass))].map(k => {
        const g = holdings.filter(h => h.assetClass === k);
        const v = g.every(h => h.value == null) ? null
                : +g.reduce((s, h) => s + (h.value || 0), 0).toFixed(2);
        return { key: k, value: v,
                 weight: (linked && total) ? +((v || 0) / total).toFixed(4)
                                           : +(g.length / holdings.length).toFixed(4) };
      }),
      /* ⚠️ 主题从**账本**来，不从任何接口来。`pipeline/book.py` 里它就是一个手写字典 ——
         建账本的 agent 认得 NVDA 是什么，填主题和填名字是同一类动作，不花 credits。
         此前这里写死 `[]`，于是 PF2/PF3 两条已定案信号永远拿不到输入。

         ⚠️ **只有个股进这个维度。** ETF 本身就是一篮子，把 SPY 塞进某个主题，
            「主题集中度」会把一只指数基金算成一次押注 —— 那是这个指标最想避免的事。
            没有 theme 的持仓不进任何组，而不是进一个「其他」组:
            「没归类」与「归到杂项」是两句话。 */
      byTheme: (() => {
        const themed = holdings.filter(h => h.theme && h.assetClass === "us_equity");
        const keys = [...new Set(themed.map(h => h.theme))];
        return keys.map(k => {
          const g = themed.filter(h => h.theme === k);
          const v = g.every(h => h.value == null) ? null
                  : +g.reduce((s, h) => s + (h.value || 0), 0).toFixed(2);
          return { key: k, value: v,
                   weight: (linked && total) ? +((v || 0) / total).toFixed(4)
                                             : +(g.length / holdings.length).toFixed(4),
                   members: g.map(h => h.symbol).sort() };
        }).sort((a, b) => b.weight - a.weight);
      })(),
    },
    checks: [],
  });

  for (const h of book) {
    const b = baselines[h.symbol] || {};
    await wr(`data/symbols/${h.symbol}.json`, {
      symbol: h.symbol,
      kline: (symbolDocs[h.symbol] || {}).kline || [],
      range52w: { low: (symbolDocs[h.symbol] || {}).low52 ?? null,
                  high: b._high ?? null,
                  asOf: ((symbolDocs[h.symbol] || {}).kline || []).slice(-1)[0]?.d ?? null },
      alertHistory: (symbolDocs[h.symbol] || {}).alertHistory || [],
      intraday: (symbolDocs[h.symbol] || {}).intradayBars
        ? { unit: "15min", tz: "UTC", sessions: 3,
            bars: symbolDocs[h.symbol].intradayBars.map(r => ({ t: r[0], c: r[1], v: r[2] })) }
        : undefined,
      coverage: { pv5From: (symbolDocs[h.symbol] || {}).pv5From ?? null },
    });
  }

  /* ── 把这本账真正的边界说出来 ──────────────────────────────────────────
     ⚠️ 页面为这些情况写好了文案、键表里也挂着，而**没有任何脚本发得出它们** ——
        22 条 gap 文案里 skill 只用得上 13 条。剩下 8 条只在本地 mock 里被发过，
        于是文案通过了「发出来的都有文案」那道检查，反方向从来没人查。
        后果:R8 那本账里三只 ETF 跑在没人验证过的兜底阈值上，
        两只新股被高波降级，**页面一个字都没说**。
        gap 恰恰是这个产品承认自己不知道什么的地方 —— 发不出来等于没承认。 */
  const _bl = Object.values(baselines);
  const _etf = book.filter(h => (h.assetClass || "us_equity") === "other");
  if (_etf.length) {
    const _tv = (baselines[_etf[0].symbol] || {}).thresholds || {};
    gaps.push(`unvalidated_asset_class:${_etf.length},${_tv.theta_v ?? "?"}`);
  }
  if (_bl.some(b2 => b2.degraded === "high_vol")) gaps.push("pv1_highvol_downgrade_undecided");
  if (_bl.some(b2 => !b2.m23 || b2.m23.verdict === "not_run")) gaps.push("m23_not_run");
  /* 「这本账没有盘中」与「这一轮没算」是两回事:前者是账本构成决定的（全是 ETF），
     后者是这一轮出了状况。分开发，不然读者只知道那一格空着。 */
  const _withBar = _bl.filter(b2 => Object.keys(b2.slotBaselines || {}).length);
  if (!_withBar.length) gaps.push(book.every(h => (h.assetClass || "us_equity") === "other")
    ? "no_intraday_for_this_book" : "pv5_not_computed");

  for (const k of Object.keys(baselines)) { delete baselines[k]._last; delete baselines[k]._high; }
  await wr("data/baselines.json", baselines);
  await wr("data/findings.json", { asOf, findings: [], scan: [] });
  /* ── 组合净值序列 ────────────────────────────────────────────────────────
     ⚠️ 这里原来写 `points: []`，而**没有任何 producer 填过它** —— 这是 init 埋占位符
        的第七次。页面上是一张空的净值图，而空图和「这本账刚建、还没有历史」
        长得一模一样，看不出是哪一种。
     我们确实没有历史持仓快照 —— `alva portfolio` 给不了「三个月前你持有什么」。
     有的只是现在的股数。所以按**当前股数不变**回推，并照契约自报家门：
     `basis: "backcast"` · `basisNote` · 一条 gap。
     猜一个起点基数才是编；用现有股数回推，每一个数都追得到源。
     ⚠️ 日期轴取各标的的**交集**。混合账本里加密有周末而美股没有，
        取并集会让周末那天缺一半持仓 —— 净值凭空掉一块，看起来像回撤。 */
  const navShares = book.every(h => h.shares != null && h.shares !== 0);
  let series = { unit: "USD", points: [], basis: null, basisNote: null,
                 benchmark: null, high: null };
  if (linked && navShares) {
    const closesBy = {};
    for (const h of book) {
      const kl = (symbolDocs[h.symbol] || {}).kline || [];
      closesBy[h.symbol] = Object.fromEntries(kl.map(k => [k.d, k.c]));
    }
    const syms = book.map(h => h.symbol);
    let axis = Object.keys(closesBy[syms[0]] || {});
    for (const sy of syms.slice(1)) axis = axis.filter(d => closesBy[sy][d] != null);
    axis.sort();
    if (axis.length) {
      const cashUsd = A.cash || 0;
      const vals = axis.map(d =>
        +(cashUsd + book.reduce((a, h) => a + h.shares * closesBy[h.symbol][d], 0)).toFixed(2));
      const base = vals[0];
      series.points = axis.map((d, i) => ({
        d, value: vals[i],
        dayPnl: i ? +(vals[i] - vals[i - 1]).toFixed(2) : 0,
        cumReturn: base ? +(vals[i] / base - 1).toFixed(4) : 0,
      }));
      const hi = series.points.reduce((a, b) => b.value > a.value ? b : a, series.points[0]);
      series.high = { d: hi.d, value: hi.value };
      series.basis = "backcast";
      series.basisNote = "Rebuilt from today's share counts held constant over the window — "
        + "we have no historical position snapshots, so this is what the current book "
        + "would have been worth, not what the account actually held.";
      gaps.push("nav_series_backcast");

      /* 基准与净值必须同一条日期轴，否则两条线在图上错位而没人看得出来。 */
      const spy = await daily("SPY", "us_equity");
      const spyBy = Object.fromEntries(spy.map(r => [r[0], r[1]]));
      const bp = axis.filter(d => spyBy[d] != null);
      const b0 = bp.length ? spyBy[bp[0]] : null;
      series.benchmark = {
        symbol: "SPY",
        points: b0 ? bp.map(d => ({ d, cumReturn: +(spyBy[d] / b0 - 1).toFixed(4) })) : [],
        /* ⚠️ 含加密的组合只能是 `us_equity_only` —— 加密没有市场基准，
           默默把它算进去跟 SPY 比就是拿两样东西相减。 */
        coverage: book.some(h => (h.assetClass || "us_equity") !== "us_equity")
          ? "us_equity_only" : "full",
      };
    }
  }
  await wr("data/series.json", series);
  await wr("data/news.json", { asOf, chain: "wide", minRelevance: 0.80, items: [] });
  /* ⚠️ market.json is a hard boot dependency and its own cronjob may not have run yet —
     write a skeleton so the page loads instead of rejecting everything. */
  try { await rd("data/market.json"); } catch (e) {
    await wr("data/market.json", { indices: [], treasury: null, commodities: [],
                                   crypto: { asOf: null, fearGreed: null,
                                             totalMarketCap: null, btcDominance: null },
                                   earningsWeek: [] });
    gaps.push("market_not_yet_fetched");
  }
  if (errs.length) gaps.push("fetch_errors:" + errs.slice(0, 8).join("|"));
  await wr("data/meta.json", { generatedAt: asOf, nextRun: null,
    specVersion: "signal-spec.md", producedSignals: [],
    /* 建库时新闻还没扫过 —— `null` 是「还没扫」，`0` 是「扫了，一条都没有」。
       两者在页面上是两句话，写 0 就把前者说成了后者。 */
    scanned: { holdings: book.length, newsItems: null, newsPassed: null },
    freshness: { prices: asOf }, gaps });

  const graded = Object.values(baselines).filter(b => (b.signalGrades || {}).PV1).length;
  const gradedBar = Object.values(baselines).filter(b => (b.signalGrades || {}).PV5).length;
  return makeDoc({
    symbols: num(book.length), pv1Graded: num(graded), pv5Graded: num(gradedBar),
    errors: str(errs.join(" | ") || "none"),
  });
});
