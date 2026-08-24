// Batch daily OHLCV. args: {symbols:"A,B,C", kind:"stock"|"crypto"}
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols,kind}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const t0=Math.floor(new Date("2018-01-01").getTime()/1000);
  const t1=Math.floor(new Date("2026-08-19").getTime()/1000);
  const out={};
  for(const s of String(symbols).split(",")){
    const url = kind==="crypto"
      ? `${B}/api/v1/crypto/binance/spot/usdt/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${t1}&limit=5000`
      : `${B}/api/v1/stocks/kline?symbol=${s}&interval=1d&start_time=${t0}&end_time=${t1}&limit=5000`;
    const r=await http.fetch(url,{headers:H});
    if(!r.ok){ out[s]={err:"HTTP "+r.status}; continue; }
    const d=(await r.json()).data||[];
    if(!d.length){ out[s]={err:"empty"}; continue; }
    const rows=d.map(x=>{
      const ts = kind==="crypto"? x.time_open : x.time_period_start;
      const vol= kind==="crypto"? x.volume    : x.volume_traded;
      return [String(ts).slice(0,10),x.price_open,x.price_high,x.price_low,x.price_close,vol].join(",");
    });
    rows.reverse();
    out[s]={n:rows.length, csv:rows.join("\n")};
  }
  return out;
})();
