const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const snap=T("2026-08-19T00:00:00Z");
  // 1) shares volume + ma20 -> estimated spot turnover
  const g=async m=>{const r=await http.fetch(`${B}/api/v1/crypto/screener/metrics?snapshot=${snap}&metric_type=${m}&order_by=DESC`,{headers:H});
    if(!r.ok) return null; return (await r.json()).data||[];};
  const sv=await g("SHARES_VOLUME"), ma=await g("MA_20"), v90=await g("VOLATILITY_90"), mc=await g("MARKET_CAP");
  if(!sv||!ma) return {err:"screener failed"};
  const M={}; for(const x of ma) M[x.symbol]=x.value;
  const est=sv.filter(x=>M[x.symbol]).map(x=>[x.symbol, x.value*M[x.symbol]]);
  est.sort((a,b)=>b[1]-a[1]);
  const top80=est.slice(0,80).map(x=>x[0]);
  // 2) perp turnover, last 180 days, median(close*volume)
  const t1=T("2026-08-19"), t0=t1-180*86400;
  const perp={}; const perr={};
  for(const pair of top80){
    const base=pair.replace(/USDT$/,"");
    const r=await http.fetch(`${B}/api/v1/crypto/binance/perp/usdt/kline?symbol=${base}&interval=1d&start_time=${t0}&end_time=${t1}&limit=1000`,{headers:H});
    if(!r.ok){ perr[pair]="HTTP "+r.status; continue; }
    const d=(await r.json()).data||[];
    if(!d.length){ perr[pair]="empty"; continue; }
    const tv=d.map(x=>Number(x.price_close)*Number(x.volume)).filter(x=>x>0).sort((a,b)=>a-b);
    if(!tv.length){ perr[pair]="novol"; continue; }
    perp[pair]={n:d.length, med:tv[Math.floor(tv.length/2)]};
  }
  return {est_top80:est.slice(0,80), perp, perr,
          v90:(v90||[]).map(x=>[x.symbol,x.value]), mc:(mc||[]).map(x=>[x.symbol,x.value])};
})();
