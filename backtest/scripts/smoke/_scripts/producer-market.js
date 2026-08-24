/* Market page (tab 3) — indices, treasury curve, commodities, crypto sentiment.
 *
 * A fourth cronjob, hourly. Objective reference data, never a signal source: nothing here
 * feeds a threshold or an alert, and the page must not imply otherwise.
 *
 * ⚠️ Without this file the page's boot() rejects and the whole dashboard shows
 *    "Data did not load" — every file it fetches is required, not optional.
 */
const { Feed, feedPath, makeDoc, str, num } = require("@alva/feed");
const http = require("net/http");
const secret = require("secret-manager");
const alfs = require("alfs");
const env = require("env");
const L = require("./lib.js");

const B = "https://data-tools.prd.arrays.org";

const INDICES = [
  ["%5EGSPC", "S&P 500"], ["%5EIXIC", "Nasdaq Composite"],
  ["%5EDJI", "Dow Jones"], ["%5EVIX", "VIX"],
];
const COMMODITIES = [
  ["GCUSD", "Gold"], ["SIUSD", "Silver"], ["CLUSD", "Crude oil"],
  ["NGUSD", "Natural gas"], ["HGUSD", "Copper"],
];
/* the treasury endpoint returns one row per date with a column per tenor */
const TENORS = [["month1", "1M"], ["month3", "3M"], ["month6", "6M"], ["year1", "1Y"],
                ["year2", "2Y"], ["year5", "5Y"], ["year10", "10Y"], ["year30", "30Y"]];

const feed = new Feed({ path: feedPath("portfolio-watch-market") });

feed.run(async (ctx, args = {}) => {
  const A = Object.assign({}, (env.args || {}), args);
  const ROOT = A.root;
  if (!ROOT) throw new Error(
    "missing args.root — pass the playbook's absolute ALFS path via "
    + "alva deploy create --args '{\"root\":\"/alva/home/<user>/playbooks/<name>\"}'");

  const H = { Authorization: "Bearer " + secret.loadPlaintext("ARRAYS_JWT") };
  const rd = async p => JSON.parse(await alfs.readFile(`${ROOT}/${p}`));
  const wr = async (p, o) => alfs.writeFile(`${ROOT}/${p}`, JSON.stringify(o));

  const errs = [];
  const get = async (path) => {
    try {
      const r = await http.fetch(B + path, { headers: H });
      if (!r.ok) { errs.push(`${path.split("?")[0]} ${r.status}`); return []; }
      return (await r.json()).data || [];
    } catch (e) { errs.push(`${path.split("?")[0]} ${e.message}`); return []; }
  };

  /* ⚠️ The real-time endpoints return a single point and ignore a time range, so a change
     cannot be derived from one call. Carry the previous session's price in the file itself
     and difference against it. The first run has no previous value and reports null —
     which is correct: a quantity we cannot compute is not displayed. Never substitute 0,
     because "unchanged" is a claim and "unknown" is not. */
  const prev = await rd("data/market.json").catch(() => ({}));
  const prevPrice = {};
  for (const row of [...(prev.indices || []), ...(prev.commodities || [])]) {
    if (row.prevClose != null && row.prevCloseDate) {
      prevPrice[row.symbol] = { price: row.prevClose, date: row.prevCloseDate };
    } else if (row.price != null && row.asOf) {
      prevPrice[row.symbol] = { price: row.price, date: row.asOf.slice(0, 10) };
    }
  }

  const quote = async (kind, sym, name) => {
    const d = await get(`/api/v1/macro/${kind}/real-time?symbol=${sym}`);
    if (!d.length) return null;
    const q = d[0];
    const day = String(q.date || "").slice(0, 10);
    const p = prevPrice[q.symbol];
    /* only difference against a DIFFERENT session — differencing within one day would
       report an intraday drift as a daily change */
    const usable = p && p.date && p.date !== day ? p : null;
    return {
      symbol: q.symbol, name,
      price: q.price,
      change:    usable ? +(q.price - usable.price).toFixed(4) : null,
      changePct: usable ? +((q.price / usable.price) - 1).toFixed(6) : null,
      asOf: q.date,
      prevClose: usable ? usable.price : (p ? p.price : null),
      prevCloseDate: usable ? usable.date : (p ? p.date : day),
    };
  };

  const indices = [];
  for (const [sym, name] of INDICES) {
    const q = await quote("index", sym, name);
    if (q) indices.push(q);
  }
  const commodities = [];
  for (const [sym, name] of COMMODITIES) {
    const q = await quote("commodity", sym, name);
    if (q) commodities.push(q);
  }

  const tr = await get("/api/v1/macro/treasury-rates?limit=1");
  let treasury = null;
  if (tr.length) {
    const row = tr[0];
    const curve = TENORS
      .filter(([k]) => row[k] != null)
      .map(([k, label]) => ({ tenor: label, yield: +(row[k] / 100).toFixed(5) }));
    const y2 = row.year2, y10 = row.year10;
    treasury = {
      asOf: row.date,
      curve,
      /* basis points, and null rather than 0 when either leg is missing */
      spread2y10y: (y2 != null && y10 != null) ? Math.round((y10 - y2) * 100) : null,
    };
  }

  const t1 = Math.floor(Date.now() / 1000), t0 = t1 - 14 * 86400;
  const fg = await get(`/api/v1/crypto/fear-greed-index?start_time=${t0}&end_time=${t1}&limit=5`);
  const latestFg = fg.length ? fg[fg.length - 1] : null;

  /* ⚠️ Total market cap and BTC dominance are NOT reachable: /crypto/market-cap requires a
     symbol, and there is no total. Reporting BTC's own cap as "total" would be wrong, and
     dominance cannot be computed from one number. Both stay null and the gap is recorded. */
  const crypto = {
    asOf: latestFg ? new Date((latestFg.timestamp || 0) * 1000).toISOString() : null,
    fearGreed: latestFg ? +latestFg.value : null,
    totalMarketCap: null,
    btcDominance: null,
  };

  /* ── 本周财报 ──────────────────────────────────────────────────────────
     全市场,不限于持仓 —— 卡片问的是「这周市场上有多少家发」,那是背景不是持仓。
     ⚠️ 不带 symbol 就是全市场,而且这个端点**免费**(CLAUDE.md 计费表)。
        此前这里写死 `earningsWeek: []`,卡片永远空 —— 而不取它没有成本上的理由。 */
  const wk = new Date();
  wk.setUTCHours(0, 0, 0, 0);
  wk.setUTCDate(wk.getUTCDate() - ((wk.getUTCDay() + 6) % 7));   // 回到本周一
  const w0 = Math.floor(wk.getTime() / 1000);
  /* ⚠️ `end_time` 是**闭区间**。写 `w0 + 7*86400` 就是下周一 00:00，于是下周一那天的
     财报被算进「本周」—— 实测多出第六天（08-24，41 家），把本周的量看起来撑大了。
     卡片问的是「这周」，那就到本周日 23:59:59 为止。 */
  const earn = await get(`/api/v1/stocks/earnings-calendar`
    + `?start_time=${w0}&end_time=${w0 + 7 * 86400 - 1}&limit=1000`);
  const byDay = {};
  for (const x of earn) {
    const d = String(x.date || "").slice(0, 10);
    if (!d) continue;
    const b = byDay[d] || (byDay[d] = { d, beforeOpen: 0, afterClose: 0, unknown: 0 });
    /* 端点给 bmo / amc,偶有空值。空值单独一列 —— 并进任一侧都是在替它做判断,
       而「盘前」与「不知道盘前还是盘后」是两件事。 */
    const t = String(x.time || "").toLowerCase();
    if (t === "bmo") b.beforeOpen += 1;
    else if (t === "amc") b.afterClose += 1;
    else b.unknown += 1;
  }
  /* ⚠️ `unknown` 那一列**永远带着**，哪怕是 0。省掉它的时候消费方就看不出
     「这天没有时间未知的」和「这份数据里没有这个概念」的区别 ——
     页面据此把总数算成 bmo+amc，每天少掉 2–12 家。字段在不在，本身就是一句话。 */
  const earningsWeek = Object.values(byDay).sort((a, b) => a.d < b.d ? -1 : 1);

  const market = { indices, treasury, commodities, crypto, earningsWeek };
  await wr("data/market.json", market);

  const meta = await rd("data/meta.json").catch(() => ({}));
  const gaps = new Set(meta.gaps || []);
  gaps.add("crypto_market_totals_unavailable");
  if (errs.length) gaps.add("market_fetch_errors:" + errs.join("|"));
  else for (const g of [...gaps]) if (String(g).startsWith("market_fetch_errors:")) gaps.delete(g);
  /* ⚠️ **加得进就要清得掉。** `market_not_yet_fetched` 是 init 立的一张欠条 ——
     「市场页现在还是骨架」。这一轮把 market.json 写满了，欠条就该撕掉。
     不撕的后果实测过:R5 的 market.json 里躺着 4 个指数，
     而方法页照旧写着「市场数据尚未取过」—— **它在说一件当时为真、现在为假的事**。
     gap 集合只并不清的话，每一条 gap 都只会变成永久的。 */
  gaps.delete("market_not_yet_fetched");
  meta.gaps = [...gaps];
  /* ⚠️ 谁往这份产物里加东西，谁就把 `generatedAt` 推到现在。
     契约:「No finding may be timestamped after generatedAt」——
     只让日线写它，此后每一轮加进来的卡都比它晚。 */
  meta.generatedAt = new Date().toISOString();
  meta.freshness = Object.assign({}, meta.freshness, { market: new Date().toISOString() });
  await L.commitMeta(rd, wr, meta, {
    freshness: ["market"],
    gapPrefixes: ["crypto_market_totals_unavailable", "market_fetch_errors",
                  "market_not_yet_fetched"],
  });

  return makeDoc({
    indices: num(indices.length), commodities: num(commodities.length),
    tenors: num(treasury ? treasury.curve.length : 0),
    errors: str(errs.join(" | ") || "none"),
  });
});
