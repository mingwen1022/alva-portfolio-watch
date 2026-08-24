const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt}; const out={};
  const yr=y=>Math.floor(new Date(y).getTime()/1000);
  for(const h of ["WhiteHouse","POTUS","SecScottBessent","CommerceGov","federalreserve","USTreasury"]){
    const per={};
    for(const [y,a,b] of [["2024","2024-01-01","2025-01-01"],["2025","2025-01-01","2026-01-01"],["2026","2026-01-01","2026-08-20"]]){
      let n=0,off=0;
      for(let p=0;p<12;p++){
        const r=await http.fetch(`${B}/by-handle?twitter_handle=${h}&limit=200&offset=${off}&since=${yr(a)}&until=${yr(b)}`,{headers:H});
        if(!r.ok){per[y]="HTTP "+r.status;break;}
        const d=(await r.json()).data||[]; n+=d.length; off+=d.length;
        if(d.length<200) break;
      }
      if(typeof per[y]!=="string") per[y]=n;
    }
    out[h]=per;
  }
  return out;
})();
