const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const out={};
  // 1. entities/handles works?
  let r=await http.fetch(`${B}/entities/handles?limit=3&offset=0`,{headers:H});
  out.handles_status=r.status;
  if(r.ok){ const d=await r.json(); out.handles_sample=(d.data||[]).map(x=>x.twitter_handle); out.pagination=d.pagination; }
  else out.handles_body=String(r.body||"").slice(0,300);
  // 2. by-handle without time window
  r=await http.fetch(`${B}/by-handle?twitter_handle=WhiteHouse&limit=2`,{headers:H});
  out.byhandle_nowindow_status=r.status;
  if(r.ok){const d=await r.json(); out.byhandle_nowindow_n=(d.data||[]).length; out.byhandle_first=(d.data||[])[0]?.published_at;}
  else out.byhandle_nowindow_body=String(r.body||"").slice(0,300);
  // 3. by-handle with window
  const since=Math.floor(new Date("2025-01-01T00:00:00Z").getTime()/1000);
  const until=Math.floor(new Date("2025-02-01T00:00:00Z").getTime()/1000);
  r=await http.fetch(`${B}/by-handle?twitter_handle=WhiteHouse&limit=2&since=${since}&until=${until}`,{headers:H});
  out.byhandle_window_status=r.status;
  if(r.ok){const d=await r.json(); out.byhandle_window_n=(d.data||[]).length; out.byhandle_window_first=(d.data||[])[0]?.published_at;}
  else out.byhandle_window_body=String(r.body||"").slice(0,300);
  return out;
})();
