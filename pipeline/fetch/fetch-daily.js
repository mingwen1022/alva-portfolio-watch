const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org";
 const t0=Math.floor(new Date("2023-06-01T00:00:00Z").getTime()/1000);
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const US=["NVDA","TSLA","AMD","MSTR","SOUN"], CR=["BTC","SOL","DOGE"];
 const out={daily:{}, earnings:{}, insider:{}, funding:{}};
 const csv=(rows)=>rows.join("\n");
 for(const s of US){
   const r=await http.fetch(`${B}/api/v1/stocks/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${t1}&limit=1000`,{headers:H});
   const d=r.ok?((await r.json()).data||[]):[];
   out.daily[s]=csv(d.map(x=>[String(x.time_period_start).slice(0,10),x.price_open,x.price_high,x.price_low,x.price_close,x.volume_traded].join(",")));
   const e=await http.fetch(`${B}/api/v1/stocks/earnings-calendar?symbol=${s}&start_time=${t0}&end_time=${t1}&limit=50`,{headers:H});
   out.earnings[s]=e.ok?((await e.json()).data||[]).map(x=>[x.date,x.time].join(",")).join("\n"):"";
   const ti=Math.floor(new Date("2026-06-01T00:00:00Z").getTime()/1000);
   const i=await http.fetch(`${B}/api/v1/stocks/insider/transactions?symbol=${s}&start_time=${ti}&end_time=${t1}&time_type=FILING_DATE&limit=300`,{headers:H});
   // ⚠️ 股数字段是 `amount`（带符号，负=处置），**不是** `securities_transacted` ——
   //    后者这个端点根本不返回。写错字段名的后果不是报错，是每一行股数都变成空，
   //    页面照实印「—」，还配了一句「端点没返回股数」—— 把自己的 bug 说成了上游的缺口。
   //    `price` 是成交价，与股数一起才能算出这笔卖了多少钱。
   out.insider[s]=i.ok?((await i.json()).data||[]).map(x=>[String(x.filing_date).slice(0,10),x.transaction_code,x.owner_name,x.amount,x.price].join("|")).join("\n"):"";
 }
 for(const s of CR){
   const r=await http.fetch(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${t1}&limit=1200`,{headers:H});
   const d=r.ok?((await r.json()).data||[]):[];
   out.daily[s]=csv(d.map(x=>[String(x.time_open).slice(0,10),x.price_open,x.price_high,x.price_low,x.price_close,x.volume].join(",")));
   const ti=Math.floor(new Date("2026-07-01T00:00:00Z").getTime()/1000);
   const f=await http.fetch(`${B}/api/v1/crypto/funding-rate?symbol=${s}&start_time=${ti}&end_time=${t1}&limit=500`,{headers:H});
   out.funding[s]=f.ok?((await f.json()).data||[]).slice(0,200).map(x=>[x.time||x.timestamp,x.funding_rate||x.rate].join(",")).join("\n"):"";
 }
 return out;
})();
