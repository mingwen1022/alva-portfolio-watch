const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const snap=T("2026-08-19T00:00:00Z");
  const out={},errs={};
  for(const m of ["MARKET_CAP","SHARES_VOLUME","VOLATILITY_90"]){
    const r=await http.fetch(`${B}/api/v1/crypto/screener/metrics?snapshot=${snap}&metric_type=${m}&order_by=DESC`,{headers:H});
    if(!r.ok){errs[m]="HTTP "+r.status+" "+(await r.text()).slice(0,150);continue;}
    const d=(await r.json()).data||[];
    out[m]=d.map(x=>[x.symbol,x.value]);
  }
  const sizes={}; for(const k in out) sizes[k]=out[k].length;
  return {sizes,errs,date:out.MARKET_CAP&&out.MARKET_CAP.length,out};
})();
