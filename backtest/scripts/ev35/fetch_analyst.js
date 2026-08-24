// EV3 原始数据：分析师目标价新闻
// offset 不可信 → 按时间窗分段拉，窗口满额则二分细化
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbol}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/stocks/company/price-target-news";
  const H={Authorization:"Bearer "+jwt};
  const LIM=1000;
  const S=Math.floor(Date.parse("2010-01-01T00:00:00Z")/1000);
  const E=Math.floor(Date.parse("2026-08-20T00:00:00Z")/1000);
  const seen={}; const rows=[]; let calls=0; let capped=0;
  const get=async(a,b)=>{
    for(let k=0;k<4;k++){
      try{
        calls++;
        const r=await http.fetch(`${B}?symbol=${symbol}&start_time=${a}&end_time=${b}&limit=${LIM}`,{headers:H});
        if(r.ok) return (await r.json()).data||[];
        if(r.status>=400&&r.status<500) return {err:r.status+" "+(await r.text()).slice(0,200)};
      }catch(e){}
    }
    return {err:"retries exhausted"};
  };
  const push=(x)=>{
    const key=(x.news_url||"")+"|"+(x.publish_time||"")+"|"+(x.analyst_company||"")+"|"+(x.price_target||"");
    if(seen[key]) return; seen[key]=1;
    const clean=(s)=>String(s==null?"":s).replace(/[|\r\n\t]/g," ").replace(/[\uD800-\uDFFF]/g,"").trim();
    rows.push([clean(x.publish_time),x.observed_at||"",clean(x.analyst_company),clean(x.analyst_name),
               x.price_target==null?"":x.price_target, x.adj_price_target==null?"":x.adj_price_target,
               x.price_when_posted==null?"":x.price_when_posted, clean(x.news_title).slice(0,220)].join("|"));
  };
  const walk=async(a,b,depth)=>{
    const d=await get(a,b);
    if(d && d.err) return {err:d.err,a,b};
    d.forEach(push);
    if(d.length>=LIM && depth<8){            // 窗口满额 → 可能被截断，二分
      capped++;
      const m=Math.floor((a+b)/2);
      await walk(a,m,depth+1); await walk(m+1,b,depth+1);
    }
    return null;
  };
  // 先按年切，避免单窗过大
  let err=null;
  let y0=S;
  while(y0<E){
    const y1=Math.min(y0+365*24*3600,E);
    const e=await walk(y0,y1,0);
    if(e){ err=e; break; }
    y0=y1+1;
  }
  return {symbol,n:rows.length,calls,capped,err,csv:rows.join("\n")};
})();
