const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt};
  const out=[];
  for(const h of ["BEA_News","OPECSecretariat","PressSec"]){
    const r=await http.fetch(`${B}/by-handle?twitter_handle=${h}&limit=2`,{headers:H});
    let j=null; try{ j=await r.json(); }catch(e){ j={parse_err:String(e)}; }
    out.push({h, status:r.status, j:JSON.stringify(j).slice(0,300)});
  }
  return out;
})();
