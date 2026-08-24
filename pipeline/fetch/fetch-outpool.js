const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const B="https://data-tools.prd.arrays.org", H={Authorization:"Bearer "+secret.loadPlaintext("ARRAYS_JWT")};
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const t0=t1-1000*86400*1.45;
 const CAND=["SPY","QQQ","XLK","EWJ","GLD","TLT","IWM","DIA","EEM","EFA","VTI","XLF","XLE","XLV","SLV","ARKK","SMH","HYG","FIG","KLAR","CHYM","CRCL"];
 const rep=[], out={};
 for(const s of CAND){
   const r=await http.fetch(`${B}/api/v1/stocks/kline?symbol=${encodeURIComponent(s)}&interval=1d&start_time=${Math.floor(t0)}&end_time=${t1}&limit=1000`,{headers:H});
   if(!r.ok){ rep.push(`${s} ERR ${r.status}`); continue; }
   const d=(await r.json()).data||[];
   if(!d.length){ rep.push(`${s} 空`); continue; }
   out[s]=d.map(k=>[String(k.time_period_start).slice(0,10),k.price_close,k.volume_traded,k.price_open,k.price_high,k.price_low].join(",")).join("\n");
   rep.push(`${s} ${d.length} 根 · ${String(d[d.length-1].time_period_start).slice(0,10)} → ${String(d[0].time_period_start).slice(0,10)}`);
 }

 return {report:rep, daily:out};
})();
