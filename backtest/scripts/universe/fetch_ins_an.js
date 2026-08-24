// Batch insider + analyst. args:{symbols:"A,B"}
const http=require("net/http"); const secret=require("secret-manager"); const env=require("env");
(async()=>{
  const {symbols}=env.args;
  const jwt=secret.loadPlaintext("ARRAYS_JWT");
  const B="https://data-tools.prd.arrays.org"; const H={Authorization:"Bearer "+jwt};
  const T=s=>Math.floor(new Date(s).getTime()/1000);
  const WIN=[["2018-01-01","2020-07-01"],["2020-07-01","2023-01-01"],["2023-01-01","2024-07-01"],["2024-07-01","2026-08-19"]];
  const out={};
  const clean=v=>String(v==null?"":v).replace(/[|\r\n\t]/g," ").trim();
  for(const s of String(symbols).split(",")){
    const ins=[]; const an=[]; const meta={ins_trunc:0,an_trunc:0,ins_err:[],an_err:[]};
    for(const [a,b] of WIN){
      const r=await http.fetch(`${B}/api/v1/stocks/insider/transactions?symbol=${s}&start_time=${T(a)}&end_time=${T(b)}&time_type=TRANSACTION_DATE&limit=5000`,{headers:H});
      if(!r.ok){ meta.ins_err.push(a+":"+r.status); }
      else { const d=(await r.json()).data||[];
        if(d.length>=5000) meta.ins_trunc++;
        for(const x of d) ins.push([
          clean(x.transaction_date).slice(0,10), clean(x.filing_date).slice(0,10),
          clean(x.transaction_code), (x.is_10b51===true||x.is_10b51===1)?1:0,
          (x.is_officer===true||x.is_officer===1)?1:0,
          (x.is_director===true||x.is_director===1)?1:0,
          clean(x.owner_name), clean(x.security_title),
          clean(x.transaction_shares!=null?x.transaction_shares:x.shares),
          clean(x.transaction_price!=null?x.transaction_price:x.price),
          clean(x.shares_owned_following!=null?x.shares_owned_following:x.shares_owned)
        ].join("|"));
      }
      const r2=await http.fetch(`${B}/api/v1/stocks/company/price-target-news?symbol=${s}&start_time=${T(a)}&end_time=${T(b)}&limit=5000`,{headers:H});
      if(!r2.ok){ meta.an_err.push(a+":"+r2.status); }
      else { const d2=(await r2.json()).data||[];
        if(d2.length>=5000) meta.an_trunc++;
        for(const x of d2) an.push([
          clean(x.publish_time), clean(x.analyst_company), clean(x.analyst_name),
          clean(x.price_target), clean(x.adj_price_target), clean(x.price_when_posted),
          clean(x.news_publisher), clean(x.news_title).slice(0,120)
        ].join("|"));
      }
    }
    const dedup=a=>Array.from(new Set(a));
    out[s]={ins:dedup(ins).sort().join("\n"), an:dedup(an).sort().join("\n"),
            n_ins:dedup(ins).length, n_an:dedup(an).length, meta};
  }
  return out;
})();
