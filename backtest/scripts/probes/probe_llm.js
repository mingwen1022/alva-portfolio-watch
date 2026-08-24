(async()=>{
  const pi=require("@alva/pi"); const out={};
  try{ out.hasApi = typeof pi.hasApi==="function" ? pi.hasApi() : pi.hasApi; }catch(e){ out.hasApi="ERR "+e.message; }
  try{ const m=pi.createModels(); out.models_keys=Object.keys(m).slice(0,20);
       for(const k of Object.keys(m).slice(0,8)) out["m."+k]= typeof m[k];
  }catch(e){ out.createModels="ERR "+String(e.message).slice(0,150); }
  try{ const g=pi.getModel(); out.getModel_type=typeof g; out.getModel_keys=g&&typeof g==="object"?Object.keys(g).slice(0,20):String(g).slice(0,80); }
  catch(e){ out.getModel="ERR "+String(e.message).slice(0,150); }
  out.Agent_type=typeof pi.Agent;
  out.createAgentSession=typeof pi.createAgentSession;
  out.thinking=typeof pi.getSupportedThinkingLevels==="function"?pi.getSupportedThinkingLevels():null;
  return out;
})();
