const http = require("net/http");
const secret = require("secret-manager");
const env = require("env");
(async () => {
  const { symbol } = env.args;
  const jwt = secret.loadPlaintext("ARRAYS_JWT");
  const B = "https://data-tools.prd.arrays.org";
  const H = { Authorization: "Bearer " + jwt };
  const t0 = Math.floor(new Date("2018-01-01").getTime()/1000);
  const now = Math.floor(new Date("2026-08-19").getTime()/1000);
  const r = await http.fetch(`${B}/api/v1/stocks/insider/transactions?symbol=${symbol}&start_time=${t0}&end_time=${now}&time_type=TRANSACTION_DATE&limit=5000`, {headers:H});
  const j = await r.json(); const d = j.data || [];
  const S = d.filter(x => x.transaction_code === "S");
  const plan = S.filter(x => x.is_10b51 === true || x.is_10b51 === 1);
  const disc = S.filter(x => !(x.is_10b51 === true || x.is_10b51 === 1));
  const own = a => new Set(a.map(x=>x.owner_name)).size;
  // 自主卖出的簇：30 日历日窗口内 distinct owner >= 2
  const days = disc.map(x=>({d:String(x.transaction_date).slice(0,10), o:x.owner_name, off:x.is_officer}))
                   .sort((a,b)=>a.d<b.d?-1:1);
  let clusters=0, lastEnd="";
  for(let i=0;i<days.length;i++){
    const t0d=new Date(days[i].d).getTime();
    const win=days.filter(x=>{const t=new Date(x.d).getTime(); return t>=t0d && t<t0d+30*864e5;});
    if(new Set(win.map(x=>x.o)).size>=2){
      const end=win[win.length-1].d;
      if(end>lastEnd){ clusters++; lastEnd=end; i=days.findIndex(x=>x.d>end); if(i<0)break; i--; }
    }
  }
  return { symbol, S:S.length, S_owners:own(S),
           plan10b51:plan.length, discretionary:disc.length, disc_owners:own(disc),
           officer_disc: disc.filter(x=>x.is_officer).length,
           clusters_30d_k2: clusters };
})();
