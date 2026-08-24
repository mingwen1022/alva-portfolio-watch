const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {handle,since,until}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const get=async(u)=>{
    for(let k=0;k<4;k++){
      try{ const r=await http.fetch(u,{headers:H}); if(r.ok) return await r.json(); }
      catch(e){}
    }
    return null;
  };
  const all=[]; let off=0; let fails=0;
  for(let p=0;p<40;p++){
    const j=await get(`${B}/by-handle?twitter_handle=${handle}&limit=100&offset=${off}&since=${since}&until=${until}`);
    if(!j){ fails++; if(fails>2) break; continue; }
    const d=j.data||[];
    if(!d.length) break;
    for(const x of d){
      const t=String(x.full_text||"").replace(/[\t\n\r|]/g," ").replace(/[\uD800-\uDFFF]/g,"").slice(0,400);
      all.push([x.published_at, handle, t].join("\t"));
    }
    off+=d.length;
    if(d.length<100) break;
  }
  return {n:all.length, fails, tsv:all.join("\n")};
})();
