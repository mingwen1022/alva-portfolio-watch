const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2015-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const url = `${B}/api/v1/macro/economic-indicators?indicator_type=__BOGUS__&time_type=RELEASE_DATE&start_time=${t0}&end_time=${now}&limit=10`;
  const r = await http.fetch(url, { headers: H });
  const tx = await r.text();
  return { status: r.status, body: tx.slice(0, 3000) };
})();
