const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org";
 const day="2026-08-21";
 const t0=Math.floor(new Date(day+"T00:00:00Z").getTime()/1000), t1=t0+86400;
 const SY=["NVDA","TSLA","AMD","MSTR","SOUN","BTC","SOL","DOGE"];
 const out={news:{}, market:{}};
 for(const s of SY){
   const r=await http.fetch(`${B}/api/v1/stocks/market-news?symbol=${s}&start_time=${t0}&end_time=${t1}&limit=100`,{headers:H});
   const d=r.ok?((await r.json()).data||[]):[];
   out.news[s]=d.map(x=>({t:x.time_published,ts:x.publish_time,src:x.source,title:x.title,
     url:x.url,sum:(x.summary||"").slice(0,300),
     rel:(x.tickers||[]).filter(k=>k.ticker===s).map(k=>k.relevance_score)[0]||"0",
     sent:x.overall_sentiment_label}))
     .filter(x=>parseFloat(x.rel)>=0.80).slice(0,12);
 }
 const g=async(p)=>{const r=await http.fetch(B+p,{headers:H}); return r.ok?((await r.json()).data||[]):[];};
 out.market.indices    = await g('/api/v1/macro/index/real-time?symbol=%5ESPX,%5ENDX,%5EDJI,%5EVIX');
 out.market.treasury   = await g('/api/v1/macro/treasury-rates?limit=1');
 out.market.commodity  = await g('/api/v1/macro/commodity/real-time?symbol=GCUSD,SIUSD,CLUSD,NGUSD,HGUSD');
 out.market.fearGreed  = await g('/api/v1/crypto/fear-greed-index?limit=1');
 out.market.mcap       = await g('/api/v1/crypto/market-cap?limit=1');
 const e0=Math.floor(new Date("2026-08-24T00:00:00Z").getTime()/1000);
 out.market.earnWeek   = await g(`/api/v1/stocks/earnings-calendar?start_time=${e0}&end_time=${e0+5*86400}&limit=1000`);
 return out;
})();
