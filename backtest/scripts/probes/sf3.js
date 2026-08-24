const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt}; const out={};
  const g=async p=>{const r=await http.fetch(B+p,{headers:H});const b=await r.text();
    if(!r.ok) return {err:"HTTP "+r.status+" "+b.slice(0,120)};
    try{return JSON.parse(b);}catch(e){return {err:"parse"};}};
  const yr=y=>Math.floor(new Date(y).getTime()/1000);

  for(const h of ["realDonaldTrump","elonmusk"]){
    const j=await g(`/by-handle?twitter_handle=${h}&limit=200&sort=latest`);
    const d=j.data||[];
    const ts=d.map(x=>x.published_at).filter(Boolean).sort();
    out[h]={n:d.length, newest:ts[ts.length-1], oldest_in_page:ts[0]};
    // 逐年探深度
    const depth={};
    for(const y of ["2026-01-01","2025-01-01","2024-01-01","2023-01-01","2021-01-01","2019-01-01"]){
      const r=await g(`/by-handle?twitter_handle=${h}&limit=3&until=${yr(y)}`);
      const dd=r.data||[];
      depth[y.slice(0,4)+"前"] = dd.length ? dd[0].published_at : (r.err||"无");
    }
    out[h].depth=depth;
  }
  // 全文检索的时间跨度
  const s=await g(`/search?q=tariff&sort=latest&limit=200`);
  const sd=s.data||[];
  const sts=sd.map(x=>x.published_at).filter(Boolean).sort();
  out.search_tariff={n:sd.length, newest:sts[sts.length-1], oldest:sts[0],
    handles:[...new Set(sd.map(x=>x.twitter_handle))].slice(0,12)};
  return out;
})();
