// Fetch unlock events + spot daily klines for unlock-bearing tokens.
const http = require("net/http");
const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const ts = s => Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000);
  const IDS = {
    arbitrum: "ARB", optimism: "OP", sui: "SUI", aptos: "APT", hyperliquid: "HYPE",
    "avalanche-2": "AVAX", celestia: "TIA", starknet: "STRK", "sei-network": "SEI",
    jupiter: "JUP", worldcoin: "WLD", "immutable-x": "IMX", "the-sandbox": "SAND",
    "axie-infinity": "AXS", filecoin: "FIL", "internet-computer": "ICP"
  };
  const out = { unlock: {}, kline: {} };
  for (const tid of Object.keys(IDS)) {
    try {
      const r = await http.fetch(`${B}/api/v1/crypto/unlock-events?token_id=${tid}&start=2025-08-20&end=2026-12-31`, { headers: H });
      const j = await r.json();
      const d = (j.data || []).map(e => ({
        d: e.unlock_date, s: e.token_symbol,
        cliff_amt: e.cliff_unlocks ? e.cliff_unlocks.cliff_amount : 0,
        cliff_pct: e.cliff_unlocks ? e.cliff_unlocks.value_to_market_cap : 0,
        lin_amt: e.linear_unlocks ? e.linear_unlocks.linear_amount : 0,
        lin_pct: e.linear_unlocks ? e.linear_unlocks.value_to_market_cap : 0
      }));
      out.unlock[tid] = { ok: r.ok, n: d.length, events: d };
    } catch (e) { out.unlock[tid] = { exc: String(e.message).slice(0, 120) }; }
  }
  for (const sym of Object.values(IDS)) {
    try {
      const r = await http.fetch(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}&interval=1d&start_time=${ts("2024-01-01")}&end_time=${ts("2026-08-20")}&limit=5000`, { headers: H });
      const j = await r.json();
      const d = j.data || [];
      const rows = d.map(x => String(x.time_open).slice(0, 10) + "," + x.price_close + "," + x.volume);
      rows.reverse();
      out.kline[sym] = { n: rows.length, csv: rows.join("\n") };
    } catch (e) { out.kline[sym] = { exc: String(e.message).slice(0, 120) }; }
  }
  return out;
})();
