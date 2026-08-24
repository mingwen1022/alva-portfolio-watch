const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {q, since, until}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const all=[]; let off=0;
  for(let p=0;p<10;p++){
    const u=`${B}/search?q=${encodeURIComponent(q)}&sort=latest&limit=200&offset=${off}`
          + (since?`&since=${since}`:"") + (until?`&until=${until}`:"");
    const r=await http.fetch(u,{headers:H});
    if(!r.ok) return {err:"HTTP "+r.status+" @off"+off, got:all.length};
    const d=(await r.json()).data||[];
    if(!d.length) break;
    for(const x of d) all.push([x.published_at, x.twitter_handle,
        String(x.full_text||"").replace(/[\t\n\r|]/g," ").slice(0,400)].join("\t"));
    off+=d.length;
    if(d.length<200) break;
  }
  return {q, n:all.length, tsv:all.join("\n")};
})();
