const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const out={};
  // 1) 已追踪账号列表（只读）
  try{
    const r=await http.fetch(`${B}/entities/handles?limit=200`,{headers:H});
    const j=await r.json();
    const d=j.data||j.items||[];
    out.tracked_count=Array.isArray(d)?d.length:0;
    out.sample=(Array.isArray(d)?d:[]).slice(0,25).map(x=>x.twitter_handle||x.handle||x.screen_name||JSON.stringify(x).slice(0,40));
  }catch(e){out.handles_err=String(e.message).slice(0,120);}
  // 2) 全文检索，看语料最早时间（只读，不触发计费）
  for(const q of ["tariff","semiconductor","China"]){
    try{
      const r=await http.fetch(`${B}/search?q=${q}&sort=latest&limit=1`,{headers:H});
      const j=await r.json(); const d=j.data||j.items||[];
      const r2=await http.fetch(`${B}/search?q=${q}&sort=relevance&limit=100`,{headers:H});
      const j2=await r2.json(); const d2=j2.data||j2.items||[];
      const ts=d2.map(x=>x.created_at||x.time||x.posted_at).filter(Boolean).sort();
      out["search_"+q]={total_hint:(j.total||j.count||null), n:d2.length,
        newest:d.length?(d[0].created_at||d[0].time):null,
        oldest_in_100:ts[0]||null};
    }catch(e){out["search_"+q]="ERR "+String(e.message).slice(0,90);}
  }
  return out;
})();
