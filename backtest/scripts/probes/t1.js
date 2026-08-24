const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const H={Authorization:"Bearer "+jwt};
  const u="https://data-tools.prd.arrays.org/api/v1/social-feeds/x/by-handle?twitter_handle=WhiteHouse&limit=50&offset=0";
  const out={};
  for(let k=0;k<3;k++){
    try{ const r=await http.fetch(u,{headers:H}); const j=await r.json();
         out["try"+k]={ok:r.ok,n:(j.data||[]).length}; if(r.ok) break; }
    catch(e){ out["try"+k]="ERR "+String(e.message).slice(0,70); }
  }
  return out;
})();
