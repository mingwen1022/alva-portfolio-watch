(async()=>{
  const adk=require("@alva/adk"); const out={};
  out.agent_src = String(adk.agent).slice(0,600);
  out.custom_src = String(adk.custom).slice(0,400);
  return out;
})();
