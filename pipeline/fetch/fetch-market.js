const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org"; const out={};
 const g=async(k,p)=>{const r=await http.fetch(B+p,{headers:H});
   out[k]= r.ok ? ((await r.json()).data||[]) : {err:r.status, body:(await r.text()).slice(0,180)};};
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const t0=t1-14*86400;
 // 指数：先看 roster 里美股三大指数与 VIX 的真实符号
 await g('roster','/api/v1/macro/index/symbols?limit=100');
 for (const sy of ['%5EGSPC','%5EIXIC','%5EDJI','%5EVIX']) await g('idx_'+sy, `/api/v1/macro/index/real-time?symbol=${sy}`);
 await g('treasury','/api/v1/macro/treasury-rates?limit=1');
 for (const sy of ['GCUSD','SIUSD','CLUSD','NGUSD','HGUSD'])
   await g('cmd_'+sy, `/api/v1/macro/commodity/real-time?symbol=${sy}`);
 await g('fg',   `/api/v1/crypto/fear-greed-index?start_time=${t0}&end_time=${t1}&limit=5`);
 await g('mcap', `/api/v1/crypto/market-cap?symbol=BTC&start_time=${t0}&end_time=${t1}&limit=5`);
 return out;
})();
