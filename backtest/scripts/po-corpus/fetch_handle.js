// 拉单个账号的完整时间线（0 credits）。GET by-handle，200/页，按 published_at DESC 返回。
// ⚠️ retweet 的 full_text 恒为空，正文在 source.full_text —— 必须单独取，否则转推全部丢文本。
// 输出列：published_at \t handle \t 自有正文 \t content_type \t platform_id \t 被引用原文 \t 原作者
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const a=env.args||{};
  const handle=a.handle, pages=a.pages||60;
  const since=Math.floor(new Date(a.since+"T00:00:00Z").getTime()/1000);   // 秒，不是毫秒
  const until=Math.floor(new Date(a.until+"T00:00:00Z").getTime()/1000);
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const clean=(s,n)=>String(s||"").replace(/[\uD800-\uDFFF]/g,"").replace(/[\t\n\r]/g," ").slice(0,n);
  const rows=[]; let off=a.offset||0; let done=false;
  for(let p=0;p<pages;p++){
    const u=`${B}/by-handle?twitter_handle=${encodeURIComponent(handle)}&limit=200&offset=${off}&since=${since}&until=${until}`;
    const r=await http.fetch(u,{headers:H});
    if(!r.ok) return {handle, err:"HTTP "+r.status, got:rows.length, next:off, tsv:rows.join("\n")};
    const d=(await r.json()).data||[];
    if(!d.length){ done=true; break; }
    for(const x of d){
      const s=x.source||{};
      rows.push([x.published_at, x.twitter_handle, clean(x.full_text,1500), x.content_type||"",
                 x.platform_id||"", clean(s.full_text,1500), s.twitter_handle||""].join("\t"));
    }
    off+=d.length;
    if(d.length<200){ done=true; break; }
  }
  return {handle, n:rows.length, next:off, done, tsv:rows.join("\n")};
})();
