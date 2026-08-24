// 15min OHLCV in fixed calendar windows (API caps span at 366d AND 10000 bars).
// args:{symbols:"A,B", kind:"stock"|"crypto", start:"2024-08-19", end:"2026-08-19", win:120}
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols,kind,start,end,win}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=(s)=>Math.floor(new Date(s).getTime()/1000);
  const t0=T(start), t1=T(end);
  const isC = kind==="crypto";
  const W=(win|| (isC?100:120))*86400;
  const out={};
  for(const s of String(symbols).split(",")){
    let rows=[], calls=0, err=null, capped=0; const seen={};
    for(let a=t0; a<t1; a+=W){
      const b=Math.min(a+W, t1);
      const url = isC
        ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${s}&interval=15min&start_time=${a}&end_time=${b}&limit=10000`
        : `${B}/api/v1/stocks/kline?symbol=${s}&interval=15min&start_time=${a}&end_time=${b}&limit=10000`;
      let r;
      try{ r=await http.fetch(url,{headers:H}); }catch(e){ err=String(e).slice(0,120); break; }
      calls++;
      if(!r.ok){ err="HTTP "+r.status; break; }
      const d=(await r.json()).data||[];
      if(d.length>=10000) capped++;
      for(const x of d){
        const iso = isC? x.time_open : x.time_period_start;
        const ep = Math.floor(new Date(iso).getTime()/1000);
        if(seen[ep]) continue; seen[ep]=1;
        const v = isC? x.volume : x.volume_traded;
        rows.push(ep+","+x.price_close+","+v);
      }
    }
    out[s]= err? {err,n:rows.length} : {n:rows.length, calls, capped, csv:rows.join(";")};
  }
  return out;
})();
