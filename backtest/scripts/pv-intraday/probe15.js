// Probe 15min bars. args: {symbol, kind, days}
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbol,kind,days}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const t1=Math.floor(new Date("2026-08-15").getTime()/1000);
  const t0=t1-(days||10)*86400;
  const url = kind==="crypto"
    ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${symbol}&interval=15min&start_time=${t0}&end_time=${t1}&limit=10000`
    : `${B}/api/v1/stocks/kline?symbol=${symbol}&interval=15min&start_time=${t0}&end_time=${t1}&limit=10000`;
  const r=await http.fetch(url,{headers:H});
  if(!r.ok) return {err:"HTTP "+r.status, body:String(r.body).slice(0,300)};
  const j=await r.json(); const d=j.data||[];
  const keys=d.length?Object.keys(d[0]):[];
  // count bars per day using the ts field
  const tsf = kind==="crypto" ? "time_open" : "time_period_start";
  const byday={};
  d.forEach(x=>{const k=String(x[tsf]).slice(0,10); byday[k]=(byday[k]||0)+1;});
  const firstday=d.length?String(d[d.length-1][tsf]).slice(0,10):null;
  const sample=d.slice(-8).map(x=>JSON.stringify(x));
  return {n:d.length, keys, first:d.length?d[d.length-1][tsf]:null, last:d.length?d[0][tsf]:null,
          byday, sample};
})();
