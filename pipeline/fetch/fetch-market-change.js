const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org"; const out={};
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000), t0=t1-12*86400;
 const g=async(k,p)=>{const r=await http.fetch(B+p,{headers:H});
   out[k]= r.ok ? ((await r.json()).data||[]) : {err:r.status, body:(await r.text()).slice(0,150)};};
 for (const sy of ['%5EGSPC','%5EIXIC','%5EDJI','%5EVIX'])
   await g('idx_'+sy, `/api/v1/macro/index/historical?symbol=${sy}&start_time=${t0}&end_time=${t1}&limit=10`);
 for (const sy of ['GCUSD','SIUSD','CLUSD','NGUSD','HGUSD'])
   await g('cmd_'+sy, `/api/v1/macro/commodity/historical?symbol=${sy}&start_time=${t0}&end_time=${t1}&limit=10`);
 await g('fg', `/api/v1/crypto/fear-greed-index?start_time=${t0}&end_time=${t1}&limit=20`);
 return out;
})();
