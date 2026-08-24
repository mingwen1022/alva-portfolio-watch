// EV5 议员交易申报 · 批量版 args:{symbols:"A,B,C"}
// ⚠️ offset 无效（一直返回同一页）· limit 上限 1000 · 源数据含完全重复行 → 整行去重
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/stocks/congress/recent-trades";
  const H={Authorization:"Bearer "+jwt};
  const LIM=1000;
  const T=s=>Math.floor(Date.parse(s+"T00:00:00Z")/1000);
  const clean=(s)=>String(s==null?"":s).replace(/[|\r\n\t]/g," ").replace(/[\uD800-\uDFFF]/g,"").trim();
  const out={};
  for(const symbol of String(symbols).split(",")){
    const seen={}; const rows=[]; let calls=0, capped=0, rawn=0, err=null;
    const get=async(a,b)=>{
      for(let k=0;k<4;k++){
        try{ calls++;
          const r=await http.fetch(`${B}?symbol=${symbol}&start_time=${a}&end_time=${b}&limit=${LIM}&time_type=TRANSACTION_DATE&tag=all`,{headers:H});
          if(r.ok) return (await r.json()).data||[];
          if(r.status>=400&&r.status<500) return {err:r.status+" "+(await r.text()).slice(0,150)};
        }catch(e){}
      }
      return {err:"retries exhausted"};
    };
    const push=(x)=>{ rawn++;
      const rec=[clean(x.transaction_date).slice(0,10),clean(x.filing_date).slice(0,10),clean(x.name),
                 clean(x.transaction_type),clean(x.amounts),clean(x.issuer),clean(x.member_type),
                 clean(x.party),x.observed_at||""];
      const key=rec.slice(0,6).join("~");
      if(seen[key]) return; seen[key]=1; rows.push(rec.join("|"));
    };
    const walk=async(a,b,depth)=>{
      const d=await get(a,b);
      if(d && d.err) return {err:d.err,a,b};
      d.forEach(push);
      if(d.length>=LIM && depth<8){ capped++; const m=Math.floor((a+b)/2);
        const e1=await walk(a,m,depth+1); if(e1) return e1;
        const e2=await walk(m+1,b,depth+1); if(e2) return e2; }
      return null;
    };
    let y0=T("2015-01-01"); const E=T("2026-08-20");
    while(y0<E){
      const y1=Math.min(y0+365*24*3600,E);
      const e=await walk(y0,y1,0);
      if(e){ err=e; break; }
      y0=y1+1;
    }
    out[symbol]={n:rows.length,raw:rawn,calls,capped,err,csv:rows.join("\n")};
  }
  return out;
})();
