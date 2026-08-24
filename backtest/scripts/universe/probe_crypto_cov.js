const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const t0=Math.floor(new Date("2018-01-01").getTime()/1000);
  const t1=Math.floor(new Date("2026-08-19").getTime()/1000);
  const out={};
  for(const s of String(symbols).split(",")){
    const r=await http.fetch(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${t1}&limit=5000`,{headers:H});
    if(!r.ok){ out[s]="HTTP "+r.status; continue; }
    const d=(await r.json()).data||[];
    out[s]= d.length? {n:d.length, last:String(d[0].time_open).slice(0,10), first:String(d[d.length-1].time_open).slice(0,10)} : "empty";
  }
  return out;
})();
