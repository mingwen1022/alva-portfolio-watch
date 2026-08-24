// 枚举全部已追踪账号（0 credits）。GET entities/handles，200/页。
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {start=0, pages=20}=env.args||{};
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const rows=[]; let off=start;
  for(let p=0;p<pages;p++){
    const r=await http.fetch(`${B}/entities/handles?limit=200&offset=${off}`,{headers:H});
    if(!r.ok) return {err:"HTTP "+r.status+" @"+off, got:rows.length, rows:rows.join("\n")};
    const d=(await r.json()).data||[];
    if(!d.length) break;
    for(const x of d){
      const t=x.tags||{};
      rows.push([x.twitter_handle, x.followers_count||0, x.earliest_backfilled_at||"", x.last_synced_at||"",
                 t.account_kind||"", t.institution_type||"", (t.topics||[]).join(","), (t.occupation||[]).join(","),
                 String(x.twitter_display_name||"").replace(/\t/g," "),
                 String(x.description||"").replace(/[\t\n\r]/g," ").slice(0,180)].join("\t"));
    }
    off+=d.length;
    if(d.length<200) break;
  }
  return {n:rows.length, next:off, tsv:rows.join("\n")};
})();
