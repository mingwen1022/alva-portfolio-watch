const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const H={Authorization:"Bearer "+jwt}; const B="https://data-tools.prd.arrays.org";
  const out={};
  const t=async(k,u)=>{ try{ const r=await http.fetch(B+u,{headers:H});
      const j=await r.json(); out[k]={ok:r.ok,n:(j.data||[]).length}; }
    catch(e){ out[k]="ERR "+String(e.message).slice(0,60); } };
  await t("股票日线","/api/v1/stocks/kline?symbol=NVDA&interval=1d&limit=5");
  await t("社交by-handle","/api/v1/social-feeds/x/by-handle?twitter_handle=WhiteHouse&limit=5");
  await t("社交handles","/api/v1/social-feeds/x/entities/handles?limit=5");
  await t("内部人","/api/v1/stocks/insider/transactions?symbol=NVDA&limit=5");
  return out;
})();
