const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {handle,since,until}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const all=[]; let off=0;
  for(let p=0;p<20;p++){
    const r=await http.fetch(`${B}/by-handle?twitter_handle=${handle}&limit=200&offset=${off}&since=${since}&until=${until}`,{headers:H});
    if(!r.ok) return {err:"HTTP "+r.status,got:all.length};
    const d=(await r.json()).data||[];
    if(!d.length) break;
    for(const x of d){
      const t=String(x.full_text||"").replace(/[\t\n\r|]/g," ").replace(/[\uD800-\uDFFF]/g,"");
      all.push([x.published_at, handle, x.content_type||"", t.slice(0,600)].join("\t"));
    }
    off+=d.length;
    if(d.length<200) break;
  }
  return {n:all.length, tsv:all.join("\n")};
})();
