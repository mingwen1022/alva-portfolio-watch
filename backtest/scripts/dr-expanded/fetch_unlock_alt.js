const http = require("net/http"); const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org"; const H = { Authorization: "Bearer " + jwt };
  const CAND = { BCH: ["bitcoin-cash","bch"], TRX: ["tron","tronix"], WLD: ["worldcoin-wld","world-coin","worldcoin"],
                 XLM: ["stellar","stellar-lumens"], XRP: ["ripple","xrp"] };
  const out = {};
  for (const sym of Object.keys(CAND)) {
    out[sym] = [];
    for (const tid of CAND[sym]) {
      try {
        const r = await http.fetch(`${B}/api/v1/crypto/unlock-events?token_id=${tid}&start=2025-08-20&end=2026-12-31`, { headers: H });
        const txt = await r.text(); let j = {}; try { j = JSON.parse(txt); } catch (e) {}
        out[sym].push({ tid, status: r.status, n: (j.data || []).length,
          events: (j.data||[]).map(e=>({d:e.unlock_date, cliff_pct: e.cliff_unlocks?e.cliff_unlocks.value_to_market_cap:0, lin_pct: e.linear_unlocks?e.linear_unlocks.value_to_market_cap:0})) });
      } catch (e) { out[sym].push({ tid, exc: String(e.message).slice(0,120) }); }
    }
  }
  return out;
})();
