const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { symbol, kind } = env.args;
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2018-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const url = kind === "crypto"
    ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${symbol}&interval=1d&start_time=${t0}&end_time=${now}&limit=5000`
    : `${B}/api/v1/stocks/kline?symbol=${symbol}&interval=1d&start_time=${t0}&end_time=${now}&limit=5000`;
  const r = await http.fetch(url, { headers: H });
  if (!r.ok) return { err: "HTTP " + r.status };
  const j = await r.json();
  const d = j.data || [];
  if (!d.length) return { err: "empty" };
  const rows = d.map(x => {
    const ts = kind === "crypto" ? x.time_open : x.time_period_start;
    const vol = kind === "crypto" ? x.volume : x.volume_traded;
    return String(ts).slice(0,10) + "," + x.price_close + "," + vol;
  });
  rows.reverse();                       // ascending by date
  return { symbol, n: rows.length, csv: rows.join("\n") };
})();
