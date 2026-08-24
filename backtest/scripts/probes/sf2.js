const http=require("net/http"); const secret=require("secret-manager");
(async()=>{
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org/api/v1/social-feeds/x";
  const H={Authorization:"Bearer "+jwt}; const out={};
  const g=async(p)=>{const r=await http.fetch(B+p,{headers:H});
    const b=await r.text(); if(!r.ok) return {err:"HTTP "+r.status+" "+b.slice(0,150)};
    try{return JSON.parse(b);}catch(e){return {err:"parse "+b.slice(0,120)};}};
  // Trump 账号的历史深度
  const j=await g("/by-handle?handle=realDonaldTrump&limit=100&sort=latest");
  const d=j.data||j.items||j.posts||[];
  out.trump_keys = d.length?Object.keys(d[0]):Object.keys(j).slice(0,12);
  out.trump_n = d.length;
  if(d.length){
    const tf=Object.keys(d[0]).filter(k=>/time|date|created/i.test(k));
    out.trump_time_fields=tf;
    const ts=d.map(x=>tf.map(k=>x[k]).find(Boolean)).filter(Boolean).sort();
    out.trump_newest=ts[ts.length-1]; out.trump_oldest_in_page=ts[0];
    out.trump_sample_text=(d[0].full_text||d[0].text||"").slice(0,120);
  }
  // 往前翻：用 until 参数取更早的
  const yr=(y)=>Math.floor(new Date(y+"-01-01").getTime()/1000);
  for(const y of ["2026","2025","2024","2023"]){
    const r=await g(`/by-handle?handle=realDonaldTrump&limit=5&until=${yr(y)}&sort=latest`);
    const dd=r.data||r.items||r.posts||[];
    const tf=dd.length?Object.keys(dd[0]).filter(k=>/time|date|created/i.test(k)):[];
    out["before_"+y]= dd.length? (tf.map(k=>dd[0][k]).find(Boolean)||"有数据无时间字段") : (r.err||"无");
  }
  return out;
})();
