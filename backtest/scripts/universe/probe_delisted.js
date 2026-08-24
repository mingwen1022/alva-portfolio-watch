const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org";
  const H={Authorization:"Bearer "+jwt};
  const t0=Math.floor(new Date("2018-01-01").getTime()/1000);
  const now=Math.floor(new Date("2026-08-19").getTime()/1000);
  const syms=["TWTR","ATVI","SIVB","FRC","XLNX","CERN","VMW","PXD","SGEN","STOR","CTXS","ANTM","MRO","HES","AAPL"];
  const out={};
  for(const s of syms){
    const r=await http.fetch(`${B}/api/v1/stocks/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${now}&limit=5000`,{headers:H});
    if(!r.ok){ out[s]="HTTP "+r.status; continue; }
    const d=(await r.json()).data||[];
    out[s]= d.length? {n:d.length, last:String(d[0].time_period_start).slice(0,10), first:String(d[d.length-1].time_period_start).slice(0,10)} : "empty";
  }
  return out;
})();
