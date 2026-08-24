(async()=>{
  const pi=require("@alva/pi"); const out={};
  const t=(k,f)=>{ try{ out[k]=f(); }catch(e){ out[k]="ERR "+String(e.message).slice(0,120); } };
  t("hasApi", ()=> typeof pi.hasApi==="function"?pi.hasApi():pi.hasApi);
  t("JAGENT_KEY", ()=> pi.JAGENT_MANAGED_API_KEY? String(pi.JAGENT_MANAGED_API_KEY).slice(0,12)+"…" : null);
  t("createModels", ()=>{ const m=pi.createModels(); return Object.keys(m); });
  t("createProvider", ()=> typeof pi.createProvider);
  t("createAlvaSessOpts", ()=>{ const o=pi.createAlvaAgentSessionOptions; return typeof o; });
  t("getModel_noarg", ()=>{ const g=pi.getModel(); return g&&typeof g==="object"?Object.keys(g):String(g).slice(0,60); });
  for(const name of ["claude-sonnet-4","sonnet","haiku","default"]){
    t("getModel:"+name, ()=>{ const g=pi.getModel(name); return g&&typeof g==="object"?Object.keys(g).slice(0,12):String(g).slice(0,60); });
  }
  return out;
})();
