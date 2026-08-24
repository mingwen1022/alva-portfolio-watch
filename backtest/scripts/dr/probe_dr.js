const http = require("net/http");
const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const ts = s => Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000);
  const out = {};

  async function probe(name, url) {
    try {
      const r = await http.fetch(url, { headers: H });
      const txt = await r.text();
      let j = null;
      try { j = JSON.parse(txt); } catch (e) { }
      if (!j) { out[name] = { status: r.status, raw: txt.slice(0, 200) }; return; }
      const d = j.data || [];
      out[name] = {
        status: r.status, success: j.success, n: d.length,
        first: d[0], last: d[d.length - 1],
        err: j.error ? JSON.stringify(j.error).slice(0, 200) : undefined
      };
    } catch (e) { out[name] = { exc: String(e.message).slice(0, 200) }; }
  }

  // funding rate: recent 30d
  await probe("fr_btc_recent",
    `${B}/api/v1/crypto/funding-rate?symbol=BTCUSDT&start_time=${ts("2026-07-01")}&end_time=${ts("2026-08-19")}&limit=1000`);
  // funding rate: earliest probe (Binance perp launched 2019-09)
  await probe("fr_btc_2019",
    `${B}/api/v1/crypto/funding-rate?symbol=BTCUSDT&start_time=${ts("2019-09-01")}&end_time=${ts("2019-12-01")}&limit=1000`);
  await probe("fr_btc_2018",
    `${B}/api/v1/crypto/funding-rate?symbol=BTCUSDT&start_time=${ts("2018-01-01")}&end_time=${ts("2018-06-01")}&limit=1000`);
  await probe("fr_doge_2021",
    `${B}/api/v1/crypto/funding-rate?symbol=DOGEUSDT&start_time=${ts("2021-01-01")}&end_time=${ts("2021-03-01")}&limit=1000`);
  await probe("fr_sol_2021",
    `${B}/api/v1/crypto/funding-rate?symbol=SOLUSDT&start_time=${ts("2021-01-01")}&end_time=${ts("2021-03-01")}&limit=1000`);

  // open interest
  await probe("oi_btc_recent",
    `${B}/api/v1/crypto/open-interest?symbol=BTCUSDT&start_time=${ts("2026-06-01")}&end_time=${ts("2026-08-19")}&interval=1d&limit=1000`);
  await probe("oi_btc_2021",
    `${B}/api/v1/crypto/open-interest?symbol=BTCUSDT&start_time=${ts("2021-01-01")}&end_time=${ts("2021-06-01")}&interval=1d&limit=1000`);
  await probe("oi_btc_2023",
    `${B}/api/v1/crypto/open-interest?symbol=BTCUSDT&start_time=${ts("2023-01-01")}&end_time=${ts("2023-06-01")}&interval=1d&limit=1000`);
  await probe("oi_btc_2025",
    `${B}/api/v1/crypto/open-interest?symbol=BTCUSDT&start_time=${ts("2025-01-01")}&end_time=${ts("2025-06-01")}&interval=1d&limit=1000`);
  // no interval param
  await probe("oi_btc_nointerval",
    `${B}/api/v1/crypto/open-interest?symbol=BTCUSDT&start_time=${ts("2026-06-01")}&end_time=${ts("2026-08-19")}&limit=1000`);

  // unlock events
  for (const tid of ["arbitrum", "solana", "optimism", "sui", "dogecoin", "ethereum", "bitcoin"]) {
    await probe("unlock_" + tid,
      `${B}/api/v1/crypto/unlock-events?token_id=${tid}&start=2018-01-01&end=2026-12-31`);
  }
  return out;
})();
