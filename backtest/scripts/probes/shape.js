const http = require("net/http");
const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2018-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const out = {};
  const r1 = await http.fetch(`${B}/api/v1/stocks/kline?symbol=NVDA&interval=1d&start_time=${t0}&end_time=${now}&limit=5000`, {headers:H});
  const j1 = await r1.json();
  const d1 = j1.data || [];
  out.stock = { n: d1.length, sample_first: d1[0], sample_last: d1[d1.length-1] };
  const r2 = await http.fetch(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=BTC&interval=1d&start_time=${t0}&end_time=${now}&limit=5000`, {headers:H});
  const j2 = await r2.json();
  const d2 = j2.data || [];
  out.crypto = { n: d2.length, sample_first: d2[0], sample_last: d2[d2.length-1] };
  return out;
})();
