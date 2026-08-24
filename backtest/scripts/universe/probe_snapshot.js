const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org";
  const H={Authorization:"Bearer "+jwt};
  const out={};
  const probes=[
    ["2018-01-02", Math.floor(new Date("2018-01-02").getTime()/1000)],
    ["2020-01-02", Math.floor(new Date("2020-01-02").getTime()/1000)],
    ["2022-06-01", Math.floor(new Date("2022-06-01").getTime()/1000)],
    ["2026-08-18", Math.floor(new Date("2026-08-18").getTime()/1000)],
  ];
  const dead=["TWTR","ATVI","FB","XLNX","SIVB","FRC","CERN","ANTM","CTXS","VMW","MRO","HES","SGEN","PXD","STOR","RE"];
  for(const [label,ts] of probes){
    const u=`${B}/api/v1/stocks/screener/financial-metrics?snapshot=${ts}&metric_type=MARKET_CAP&range_min=1000000000&order_by=DESC`;
    const r=await http.fetch(u,{headers:H});
    if(!r.ok){ out[label]={err:"HTTP "+r.status, body:(await r.text()).slice(0,300)}; continue; }
    const j=await r.json();
    const d=j.data||[];
    const syms=d.map(x=>x.symbol);
    const set=new Set(syms);
    out[label]={n:d.length, date:d[0]&&d[0].date, top15:syms.slice(0,15),
                dead_found:dead.filter(s=>set.has(s))};
  }
  return out;
})();
