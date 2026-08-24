const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { indicator, tt } = env.args;
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2018-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const url = `${B}/api/v1/macro/economic-indicators?indicator_type=${indicator}&time_type=${tt}&start_time=${t0}&end_time=${now}&limit=5000`;
  const r = await http.fetch(url, { headers: H });
  if (!r.ok) { const tx = await r.text(); return { err: "HTTP " + r.status, body: tx.slice(0,600) }; }
  const j = await r.json();
  const d = j.data || j.items || [];
  return { indicator, tt, n: (d.length||0), keys: d.length ? Object.keys(d[0]) : Object.keys(j),
           first3: d.slice(0,3), last3: d.slice(-3), topkeys: Object.keys(j) };
})();
