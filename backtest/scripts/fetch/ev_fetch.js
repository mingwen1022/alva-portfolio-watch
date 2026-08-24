const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbol}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org";
  const H={Authorization:"Bearer "+jwt};
  const t0=Math.floor(new Date("2018-01-01").getTime()/1000);
  const now=Math.floor(new Date("2026-08-19").getTime()/1000);
  const r=await http.fetch(`${B}/api/v1/stocks/insider/transactions?symbol=${symbol}&start_time=${t0}&end_time=${now}&time_type=TRANSACTION_DATE&limit=5000`,{headers:H});
  if(!r.ok) return {err:"HTTP "+r.status};
  const d=(await r.json()).data||[];
  const rows=d.filter(x=>x.transaction_date&&x.filing_date&&x.owner_name)
    .map(x=>[String(x.transaction_date).slice(0,10), String(x.filing_date).slice(0,10),
             x.transaction_code||"?", (x.is_10b51===true||x.is_10b51===1)?1:0,
             (x.is_officer===true||x.is_officer===1)?1:0,
             String(x.owner_name).replace(/[,|]/g," ")].join("|"));
  return {symbol, n:rows.length, csv:rows.join("\n")};
})();
