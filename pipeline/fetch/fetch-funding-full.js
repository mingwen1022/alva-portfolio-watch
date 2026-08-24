const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
 const jwt=secret.loadPlaintext("ARRAYS_JWT"); const H={Authorization:"Bearer "+jwt};
 const B="https://data-tools.prd.arrays.org"; const {sym}=env.args;
 const t1=Math.floor(new Date("2026-08-22T00:00:00Z").getTime()/1000);
 const rows=[]; let errs=0;
 for(let off=0; off<760; off+=120){
   const b=t1-Math.min(760,off+120)*86400, e=t1-off*86400;
   const r=await http.fetch(`${B}/api/v1/crypto/funding-rate?symbol=${sym}&start_time=${b}&end_time=${e}&limit=1000`,{headers:H});
   if(!r.ok){errs++;continue;}
   const d=(await r.json()).data||[];
   for(const x of d) rows.push([x.time||x.timestamp, x.funding_rate!=null?x.funding_rate:x.rate].join(","));
 }
 return {sym,errs,n:rows.length,csv:rows.join("\n")};
})();
