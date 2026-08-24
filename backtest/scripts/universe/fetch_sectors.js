const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org";
  const H={Authorization:"Bearer "+jwt};
  const secs=["BASIC_MATERIALS","COMMUNICATION_SERVICES","CONSUMER_CYCLICAL","CONSUMER_DEFENSIVE","ENERGY","FINANCIAL_SERVICES","HEALTHCARE","INDUSTRIALS","REAL_ESTATE","TECHNOLOGY","UTILITIES"];
  const out={};
  for(const s of secs){
    const r=await http.fetch(`${B}/api/v1/stocks/screener/basic-info/sector?sector=${s}`,{headers:H});
    if(!r.ok){ out[s]={err:"HTTP "+r.status}; continue; }
    const d=(await r.json()).data||[];
    out[s]=d.map(x=>x.symbol);
  }
  return out;
})();
