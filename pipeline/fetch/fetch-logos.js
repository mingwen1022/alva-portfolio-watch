const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org"; const out={};
 for(const s of ["NVDA","TSLA","AMD","MSTR","SOUN"]){
   const r=await http.fetch(`${B}/api/v1/stocks/company/detail?symbol=${s}`,{headers:H});
   const d=r.ok?((await r.json()).data||[]):[]; out[s]=d[0]?(d[0].logo||null):null;
 }
 for(const s of ["BTC","SOL","DOGE"]){
   const r=await http.fetch(`${B}/api/v1/crypto/detail?symbol=${s}`,{headers:H});
   if(!r.ok){ out[s]=null; continue; }
   const d=(await r.json()).data||[];
   out[s]=d[0]?(d[0].logo||d[0].logo_url||d[0].image||null):null;
 }
 return out;
})();
