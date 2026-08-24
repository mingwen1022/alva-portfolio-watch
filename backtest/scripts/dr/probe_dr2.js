const http = require("net/http");
const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const ts = s => Math.floor(new Date(s + "T00:00:00Z").getTime() / 1000);
  const out = {};

  async function get(url) {
    const r = await http.fetch(url, { headers: H });
    const j = await r.json();
    return { ok: r.ok, success: j.success, data: j.data || [], err: j.error };
  }

  // 1. yearly coverage + frequency + magnitude for funding rate, per symbol
  const years = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
  for (const sym of ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]) {
    const rec = {};
    for (const y of years) {
      const a = ts(y + "-01-01"), b = ts(y + "-02-01");
      const g = await get(`${B}/api/v1/crypto/funding-rate?symbol=${sym}&start_time=${a}&end_time=${b}&limit=1000`);
      const vals = g.data.map(x => x.funding_rate);
      const abs = vals.map(Math.abs).sort((p, q) => p - q);
      rec[y] = {
        n: g.data.length,
        perDay: g.data.length ? +(g.data.length / 32).toFixed(2) : 0,
        medAbs: abs.length ? abs[Math.floor(abs.length / 2)] : null,
        maxAbs: abs.length ? abs[abs.length - 1] : null,
        firstTime: g.data.length ? g.data[g.data.length - 1].time : null,
        times3: g.data.slice(0, 3).map(x => x.time)
      };
    }
    out["fr_" + sym] = rec;
  }

  // 2. open-interest yearly coverage
  for (const sym of ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"]) {
    const rec = {};
    for (const y of years) {
      const a = ts(y + "-01-01"), b = ts(y + "-02-01");
      const g = await get(`${B}/api/v1/crypto/open-interest?symbol=${sym}&start_time=${a}&end_time=${b}&interval=1d&limit=1000`);
      rec[y] = { n: g.data.length, first: g.data.length ? g.data[g.data.length - 1].time : null };
    }
    out["oi_" + sym] = rec;
  }

  // 3. unlock events inside the allowed range
  const uo = {};
  for (const tid of ["arbitrum", "optimism", "sui", "solana", "ethereum", "bitcoin", "dogecoin", "aptos", "hyperliquid", "uniswap"]) {
    try {
      const g = await get(`${B}/api/v1/crypto/unlock-events?token_id=${tid}&start=2025-08-20&end=2026-12-31`);
      uo[tid] = { ok: g.ok, n: g.data.length, sample: g.data[0] ? JSON.stringify(g.data[0]).slice(0, 400) : null };
    } catch (e) { uo[tid] = { exc: String(e.message).slice(0, 120) }; }
  }
  out.unlock = uo;

  return out;
})();
