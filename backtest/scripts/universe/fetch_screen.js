const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org";
  const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const SNAP=T("2026-08-18"), SNAP18=T("2018-01-02");
  const out={}; const errs={};
  async function grab(key,url){
    const r=await http.fetch(url,{headers:H});
    if(!r.ok){ errs[key]="HTTP "+r.status+" "+(await r.text()).slice(0,200); return; }
    const j=await r.json();
    out[key]=(j.data||[]).map(x=>[x.symbol,x.value]);
  }
  await grab("mcap26",`${B}/api/v1/stocks/screener/financial-metrics?snapshot=${SNAP}&metric_type=MARKET_CAP&range_min=50000000&order_by=DESC`);
  await grab("mcap18",`${B}/api/v1/stocks/screener/financial-metrics?snapshot=${SNAP18}&metric_type=MARKET_CAP&range_min=50000000&order_by=DESC`);
  await grab("addv",`${B}/api/v1/stocks/screener/technical-metrics?snapshot=${SNAP}&metric_type=AVERAGE_DAILY_DOLLAR_VOLUME&range_min=100000&order_by=DESC&symbol_type=stock`);
  await grab("vol90",`${B}/api/v1/stocks/screener/technical-metrics?snapshot=${SNAP}&metric_type=VOLATILITY_90&order_by=DESC&symbol_type=stock`);
  await grab("beta",`${B}/api/v1/stocks/screener/technical-metrics?snapshot=${SNAP}&metric_type=BETA&order_by=DESC&symbol_type=stock`);
  await grab("ma20",`${B}/api/v1/stocks/screener/technical-metrics?snapshot=${SNAP}&metric_type=MA_20&order_by=DESC&symbol_type=stock`);
  // IPO dates
  const r=await http.fetch(`${B}/api/v1/stocks/screener/events?event_type=IPO%20Date&start_time=${T("1970-01-01")}&end_time=${T("2026-08-19")}`,{headers:H});
  if(r.ok){ const j=await r.json(); out.ipo=(j.data||[]).map(x=>[x.symbol,x.value]); } else errs.ipo="HTTP "+r.status;
  const sizes={}; for(const k in out) sizes[k]=out[k].length;
  return {sizes,errs,out};
})();
