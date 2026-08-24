const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const B="https://data-tools.prd.arrays.org", H={Authorization:"Bearer "+secret.loadPlaintext("ARRAYS_JWT")};
 const US=["NVDA","TSLA","AMD","MSTR","SOUN"], CR=["BTC","SOL","DOGE"];
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const out={}, rep=[];
 const grab=async(url)=>{ const r=await http.fetch(url,{headers:H});
   if(!r.ok) return {err:r.status}; return {d:((await r.json()).data||[])}; };
 for(const s of US){
   const rows=new Set(); let bad=0;
   for(let seg=0; seg<5; seg++){
     const hi=t1-Math.floor(seg*1000*86400*1.45), lo=hi-Math.floor(1000*86400*1.45);
     const g=await grab(`${B}/api/v1/stocks/kline?symbol=${s}&interval=1d&start_time=${lo}&end_time=${hi}&limit=1000`);
     if(g.err){ bad++; continue; }
     for(const k of g.d) rows.add([String(k.time_period_start).slice(0,10),k.price_close,k.volume_traded].join(","));
   }
   out[s]=[...rows].join("\n"); rep.push(`${s} ${rows.size} 根 · 失败段 ${bad}`);
 }
 for(const s of CR){
   const rows=new Set(); let bad=0;
   for(let seg=0; seg<5; seg++){
     const hi=t1-seg*1000*86400, lo=hi-1000*86400;
     const g=await grab(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${s}&interval=1d&start_time=${lo}&end_time=${hi}&limit=1000`);
     if(g.err){ bad++; continue; }
     for(const k of g.d) rows.add([String(k.time_open).slice(0,10),k.price_close,k.volume].join(","));
   }
   out[s]=[...rows].join("\n"); rep.push(`${s} ${rows.size} 根 · 失败段 ${bad}`);
 }
 return {report:rep, daily:out};
})();
