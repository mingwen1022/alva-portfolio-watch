// Fetch funding-rate + open-interest full history for one symbol.
// args: {"symbol":"BTC"}  -> queries BTCUSDT
const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { symbol } = env.args;
  const pair = symbol + "USDT";
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const ts = s => Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000);

  // 3-month windows from 2020-07 to 2026-09 (<=1000 rows each even at 3/day)
  const wins = [];
  for (let y = 2020; y <= 2026; y++) {
    for (const [a, b] of [["01-01", "04-01"], ["04-01", "07-01"], ["07-01", "10-01"], ["10-01", "01-01"]]) {
      const y2 = b === "01-01" ? y + 1 : y;
      wins.push([ts(`${y}-${a}`), ts(`${y2}-${b}`)]);
    }
  }

  async function pull(path, extra) {
    const seen = {};
    for (const [a, b] of wins) {
      let r, j;
      for (let k = 0; k < 3; k++) {
        try {
          r = await http.fetch(`${B}${path}?symbol=${pair}&start_time=${a}&end_time=${b}${extra}&limit=1000`, { headers: H });
          j = await r.json();
          if (j && j.success) break;
        } catch (e) { j = null; }
      }
      if (!j || !j.success) continue;
      for (const x of (j.data || [])) seen[x.time] = x;
    }
    return Object.keys(seen).sort().map(k => seen[k]);
  }

  const fr = await pull("/api/v1/crypto/funding-rate", "");
  const oi = await pull("/api/v1/crypto/open-interest", "&interval=1d");

  return {
    symbol,
    fr_n: fr.length, fr_first: fr[0] ? fr[0].time : null, fr_last: fr[fr.length - 1] ? fr[fr.length - 1].time : null,
    oi_n: oi.length, oi_first: oi[0] ? oi[0].time : null, oi_last: oi[oi.length - 1] ? oi[oi.length - 1].time : null,
    fr_csv: fr.map(x => x.time + "," + x.funding_rate).join("\n"),
    oi_csv: oi.map(x => x.time + "," + x.sum_open_interest_value).join("\n")
  };
})();
