// args:{symbols:"BTC,ETH"}  -> funding rate + open interest, paged backwards
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T0=Math.floor(new Date("2018-01-01").getTime()/1000);
  const T1=Math.floor(new Date("2026-08-19").getTime()/1000);
  const out={};
  for(const base of String(symbols).split(",")){
    const pair=base+"USDT";
    const res={};
    for(const [key,path,extra,maxPage] of [["fund","funding-rate","",20],["oi","open-interest","&interval=1d",8]]){
      const seen={}; let end=T1; let pages=0; let keys=null; let err=null;
      while(pages<maxPage){
        const r=await http.fetch(`${B}/api/v1/crypto/${path}?symbol=${pair}&start_time=${T0}&end_time=${end}&limit=1000${extra}`,{headers:H});
        if(!r.ok){ err="HTTP "+r.status; break; }
        const d=(await r.json()).data||[];
        if(!d.length) break;
        if(!keys) keys=Object.keys(d[0]);
        let minTs=Infinity;
        for(const x of d){ const ts=x.timestamp; if(ts<minTs)minTs=ts; seen[ts]=x; }
        pages++;
        if(d.length<1000) break;
        if(minTs<=T0) break;
        if(minTs>=end) break;
        end=minTs-1;
      }
      const ts=Object.keys(seen).map(Number).sort((a,b)=>a-b);
      const rows=ts.map(t=>{const x=seen[t];
        return key==="fund" ? [x.time,x.funding_rate].join(",")
                            : [x.time,x.sum_open_interest,x.sum_open_interest_value].join(",");});
      res[key]={n:rows.length, pages, err, keys,
                first:ts.length?seen[ts[0]].time:null, last:ts.length?seen[ts[ts.length-1]].time:null,
                csv:rows.join("\n")};
    }
    out[base]=res;
  }
  return out;
})();
