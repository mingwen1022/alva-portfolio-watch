const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { symbol } = env.args;
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2018-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const r = await http.fetch(`${B}/api/v1/stocks/insider/transactions?symbol=${symbol}&start_time=${t0}&end_time=${now}&time_type=TRANSACTION_DATE&limit=5000`, {headers:H});
  if(!r.ok) return {err:"HTTP "+r.status};
  const j = await r.json();
  const d = j.data || [];
  if(!d.length) return {symbol, n:0};
  const byCode = {}; const ownersByCode = {};
  const keys = Object.keys(d[0]);
  for(const x of d){
    const code = x.transaction_code || x.transactionCode || "?";
    byCode[code] = (byCode[code]||0)+1;
    const ow = x.owner_name || x.ownerName || x.reporting_name || "?";
    (ownersByCode[code] = ownersByCode[code] || new Set()).add(ow);
  }
  const owners = {}; for(const k in ownersByCode) owners[k] = ownersByCode[k].size;
  return { symbol, n:d.length, byCode, owners, keys: keys.slice(0,18) };
})();
