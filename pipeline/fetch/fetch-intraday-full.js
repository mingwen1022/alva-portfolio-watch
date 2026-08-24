const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org";
 const {sym, crypto, fromDay, toDay} = env.args;   // 相对今天的偏移天数
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const CH = crypto ? 20 : 45;
 const rows=[]; let errs=0;
 for(let off=fromDay; off<toDay; off+=CH){
   const b=t1-Math.min(toDay,off+CH)*86400, e=t1-off*86400;
   const u = crypto
     ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${sym}&interval=15min&start_time=${b}&end_time=${e}&limit=3000`
     : `${B}/api/v1/stocks/kline?symbol=${sym}&interval=15min&start_time=${b}&end_time=${e}&limit=3000`;
   const r=await http.fetch(u,{headers:H});
   if(!r.ok){ errs++; continue; }
   const d=(await r.json()).data||[];
   for(const x of d) rows.push([String(x.time_period_start||x.time_open).slice(0,16),
      x.price_close, (x.volume_traded!=null?x.volume_traded:x.volume)].join(","));
 }
 return {sym, errs, n:rows.length, csv:rows.join("\n")};
})();
