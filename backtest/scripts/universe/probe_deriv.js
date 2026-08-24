const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const out={};
  for(const sym of ["BTCUSDT","ETHUSDT","PENGUUSDT"]){
    for(const [k,path,extra] of [["fund","funding-rate",""],["oi","open-interest","&interval=1d"]]){
      // earliest: ask a wide window with limit 1000 ASC-unknown; API returns reverse-chron
      const r=await http.fetch(`${B}/api/v1/crypto/${path}?symbol=${sym}&start_time=${T("2018-01-01")}&end_time=${T("2026-08-19")}&limit=1000${extra}`,{headers:H});
      if(!r.ok){ out[sym+"_"+k]="HTTP "+r.status+" "+(await r.text()).slice(0,120); continue; }
      const d=(await r.json()).data||[];
      out[sym+"_"+k]= d.length? {n:d.length, f0:JSON.stringify(d[0]).slice(0,200), fN:JSON.stringify(d[d.length-1]).slice(0,200)} : "empty";
    }
  }
  return out;
})();
