const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const out={}; const errs={};
  // try progressively: 1y windows 2014..2026
  const rows=[];
  for(let y=2014;y<=2026;y++){
    const a=T(y+"-01-01"), b=T((y+1)+"-01-01");
    const r=await http.fetch(`${B}/api/v1/stocks/screener/events?event_type=IPO%20Date&start_time=${a}&end_time=${b}`,{headers:H});
    if(!r.ok){ errs[y]="HTTP "+r.status+" "+(await r.text()).slice(0,150); continue; }
    const d=(await r.json()).data||[];
    for(const x of d) rows.push([x.symbol,x.value]);
    out[y]=d.length;
  }
  return {counts:out, errs, n:rows.length, rows};
})();
