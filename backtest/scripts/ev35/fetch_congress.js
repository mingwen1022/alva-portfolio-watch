// EV5 原始数据：议员交易申报
// ⚠️ offset 无效（一直返回同一页）· limit 上限 1000 · 源数据含 7–11% 完全重复行
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbol}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/stocks/congress/recent-trades";
  const H={Authorization:"Bearer "+jwt};
  const LIM=1000;
  const S=Math.floor(Date.parse("2012-01-01T00:00:00Z")/1000);
  const E=Math.floor(Date.parse("2026-08-20T00:00:00Z")/1000);
  const seen={}; const rows=[]; let calls=0; let capped=0; let rawn=0;
  const get=async(a,b)=>{
    for(let k=0;k<4;k++){
      try{
        calls++;
        const r=await http.fetch(`${B}?symbol=${symbol}&start_time=${a}&end_time=${b}&limit=${LIM}&time_type=TRANSACTION_DATE&tag=all`,{headers:H});
        if(r.ok) return (await r.json()).data||[];
        if(r.status>=400&&r.status<500) return {err:r.status+" "+(await r.text()).slice(0,200)};
      }catch(e){}
    }
    return {err:"retries exhausted"};
  };
  const clean=(s)=>String(s==null?"":s).replace(/[|\r\n\t]/g," ").replace(/[\uD800-\uDFFF]/g,"").trim();
  const push=(x)=>{
    rawn++;
    // 整行去重键：议员 + 交易日 + 申报日 + 金额 + 方向 + issuer（与 results-phase2-ev §8.2 一致）
    const rec=[clean(x.transaction_date),clean(x.filing_date),clean(x.name),clean(x.transaction_type),
               clean(x.amounts),clean(x.issuer),clean(x.member_type),clean(x.party),x.observed_at||""];
    const key=rec.slice(0,6).join("~");
    if(seen[key]) return; seen[key]=1;
    rows.push(rec.join("|"));
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
  let err=null; let y0=S;
  while(y0<E){
    const y1=Math.min(y0+365*24*3600,E);
    const e=await walk(y0,y1,0);
    if(e){ err=e; break; }
    y0=y1+1;
  }
  return {symbol,n:rows.length,raw:rawn,dupRate:rawn?+(1-rows.length/rawn).toFixed(3):0,calls,capped,err,csv:rows.join("\n")};
})();
