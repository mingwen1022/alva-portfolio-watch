// 扩建池 25 个代币的解锁事件。0 credits（纯 HTTP）。
const http = require("net/http");
const secret = require("secret-manager");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const IDS = {
    AAVE: "aave", ADA: "cardano", AVAX: "avalanche-2", BCH: "bitcoin-cash",
    BNB: "binancecoin", BTC: "bitcoin", DOGE: "dogecoin", DOT: "polkadot",
    ENA: "ethena", ETH: "ethereum", FIL: "filecoin", LINK: "chainlink",
    LTC: "litecoin", NEAR: "near", PENGU: "pudgy-penguins", SOL: "solana",
    SUI: "sui", TAO: "bittensor", TRUMP: "official-trump", TRX: "tron",
    UNI: "uniswap", WLD: "worldcoin", XLM: "stellar", XRP: "ripple", ZEC: "zcash"
  };
  const out = {};
  for (const sym of Object.keys(IDS)) {
    const tid = IDS[sym];
    try {
      const r = await http.fetch(`${B}/api/v1/crypto/unlock-events?token_id=${tid}&start=2025-08-20&end=2026-12-31`, { headers: H });
      const txt = await r.text();
      let j = {};
      try { j = JSON.parse(txt); } catch (e) { }
      const d = (j.data || []).map(e => ({
        d: e.unlock_date, s: e.token_symbol,
        cliff_amt: e.cliff_unlocks ? e.cliff_unlocks.cliff_amount : 0,
        cliff_pct: e.cliff_unlocks ? e.cliff_unlocks.value_to_market_cap : 0,
        lin_amt: e.linear_unlocks ? e.linear_unlocks.linear_amount : 0,
        lin_pct: e.linear_unlocks ? e.linear_unlocks.value_to_market_cap : 0
      }));
      out[sym] = { token_id: tid, status: r.status, ok: r.ok, n: d.length, events: d, err: r.ok ? null : txt.slice(0, 200) };
    } catch (e) { out[sym] = { token_id: tid, exc: String(e.message).slice(0, 200) }; }
  }
  return out;
})();
