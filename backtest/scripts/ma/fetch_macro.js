const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { inds, tt } = env.args;             // inds: comma separated
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2015-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const out = {};
  for (const ind of inds.split(",")) {
    const url = `${B}/api/v1/macro/economic-indicators?indicator_type=${ind}&time_type=${tt}&start_time=${t0}&end_time=${now}&limit=5000`;
    const r = await http.fetch(url, { headers: H });
    if (!r.ok) { const tx = await r.text(); out[ind] = { err: "HTTP " + r.status, body: tx.slice(0,300) }; continue; }
    const j = await r.json();
    const d = (j.data || [])[0];
    if (!d) { out[ind] = { err: "empty" }; continue; }
    const rows = (d.observations||[]).map(o =>
      [o.date, o.value, o.release_date, o.observed_at].join(","));
    rows.reverse();
    out[ind] = { title: d.series && d.series.title, freq: d.series && d.series.frequency,
                 units: d.series && d.series.units, n: rows.length, csv: rows.join("\n") };
  }
  return out;
})();
