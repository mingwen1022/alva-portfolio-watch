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
  const d = (await r.json()).data || [];
  const lags = [];
  for(const x of d){
    if(!x.transaction_date || !x.filing_date) continue;
    const a = new Date(String(x.transaction_date).slice(0,10)).getTime();
    const b = new Date(String(x.filing_date).slice(0,10)).getTime();
    if(isNaN(a)||isNaN(b)) continue;
    lags.push(Math.round((b-a)/864e5));
  }
  lags.sort((p,q)=>p-q);
  const q = f => lags.length ? lags[Math.min(lags.length-1, Math.floor(lags.length*f))] : null;
  return { symbol, n:lags.length, min:lags[0], p50:q(0.5), p90:q(0.9), p99:q(0.99), max:lags[lags.length-1],
           over2: lags.filter(x=>x>2).length };
})();
