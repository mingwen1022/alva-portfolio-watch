(async()=>{
  const out={};
  for(const m of ["@alva/adk","@alva/pi","@alva/feed","@alva/onnx"]){
    try{ const x=require(m); out[m]=Object.keys(x).slice(0,30); }
    catch(e){ out[m]="ERR "+String(e.message).slice(0,90); }
  }
  try{
    const adk=require("@alva/adk");
    for(const k of Object.keys(adk)){
      const v=adk[k];
      out["adk."+k]= typeof v==="function" ? "fn("+v.length+")" : (v&&typeof v==="object"? Object.keys(v).slice(0,15) : typeof v);
    }
  }catch(e){}
  return out;
})();
