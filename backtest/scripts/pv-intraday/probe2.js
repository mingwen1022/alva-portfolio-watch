const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const out={};
  const T=(s)=>Math.floor(new Date(s).getTime()/1000);
  async function get(u){ const r=await http.fetch(u,{headers:H}); if(!r.ok) return {err:"HTTP "+r.status, body:String(r.body).slice(0,200)}; const j=await r.json(); return {data:j.data||[]}; }
  // winter week, stock
  let a=await get(`${B}/api/v1/stocks/kline?symbol=NVDA&interval=15min&start_time=${T("2026-01-05")}&end_time=${T("2026-01-09")}&limit=10000`);
  if(a.data){ const bd={}; a.data.forEach(x=>{const k=x.time_period_start.slice(0,10); bd[k]=(bd[k]||0)+1;});
    out.winter={n:a.data.length, byday:bd, first:a.data[a.data.length-1].time_period_start, last:a.data[0].time_period_start}; } else out.winter=a;
  // session=RTH / ETH
  for(const s of ["RTH","ETH","rth"]){
    let b=await get(`${B}/api/v1/stocks/kline?symbol=NVDA&interval=15min&start_time=${T("2026-08-10")}&end_time=${T("2026-08-12")}&limit=10000&session=${s}`);
    out["sess_"+s]= b.data? {n:b.data.length, first:b.data[b.data.length-1].time_period_start, last:b.data[0].time_period_start} : b;
  }
  // how far back does 15min go
  let c=await get(`${B}/api/v1/stocks/kline?symbol=NVDA&interval=15min&start_time=${T("2018-06-01")}&end_time=${T("2018-06-20")}&limit=10000`);
  out.old2018 = c.data? {n:c.data.length, first:c.data.length?c.data[c.data.length-1].time_period_start:null}: c;
  // 366-day span behaviour (cap)
  let d=await get(`${B}/api/v1/stocks/kline?symbol=NVDA&interval=15min&start_time=${T("2025-08-15")}&end_time=${T("2026-08-15")}&limit=10000`);
  out.span366 = d.data? {n:d.data.length, first:d.data.length?d.data[d.data.length-1].time_period_start:null, last:d.data.length?d.data[0].time_period_start:null}: d;
  // crypto
  let e=await get(`${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=BTC&interval=15min&start_time=${T("2026-08-10")}&end_time=${T("2026-08-13")}&limit=10000`);
  out.crypto = e.data? {n:e.data.length, keys:Object.keys(e.data[0]||{}), first:e.data[e.data.length-1].time_open, last:e.data[0].time_open, sample:e.data.slice(0,2)}: e;
  return out;
})();
