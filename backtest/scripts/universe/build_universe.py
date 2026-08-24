#!/usr/bin/env python3
import csv,json,math,os,statistics
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEC={'BASIC_MATERIALS':'原材料','COMMUNICATION_SERVICES':'通信服务','CONSUMER_CYCLICAL':'可选消费',
 'CONSUMER_DEFENSIVE':'必需消费','ENERGY':'能源','FINANCIAL_SERVICES':'金融','HEALTHCARE':'医疗',
 'INDUSTRIALS':'工业','REAL_ESTATE':'房地产','TECHNOLOGY':'科技','UTILITIES':'公用事业','':''}
gaps=json.load(open('raw/gaps.json'))
def series(p):
    r=list(csv.DictReader(open(p)))
    key='date'
    c=[(x[key],float(x['close'])) for x in r if float(x['close'] or 0)>0]
    return r,c
def sigma(c,skip=None):
    lr=[]
    for i in range(1,len(c)):
        if skip and skip[0]<=c[i][0]<=skip[1]: continue
        lr.append(math.log(c[i][1]/c[i-1][1]))
    return statistics.pstdev(lr)*math.sqrt(252) if len(lr)>30 else float('nan')
def vt(s): return 'low' if s<0.25 else ('mid' if s<=0.50 else 'high')
def cnt(p):
    if not os.path.exists(p): return 0
    return max(0,sum(1 for _ in open(p))-1)

out=[]
for r in json.load(open('raw/selection_us.json')):
    s=r['symbol']; raw,c=series(f'data/daily/{s}.csv')
    sg=sigma(c); sgx=sigma(c,('2020-02-15','2020-04-30'))
    out.append(dict(symbol=s,asset_class='us_equity',stratum=r['stratum'],
        sector=SEC.get(r.get('sector',''),r.get('sector','')),sector_raw=r.get('sector',''),
        size_tier=r.get('size_tier',''),vol_tier=vt(sg),
        mktcap_2026_usd=round(r['mcap']) if r.get('mcap') else '',
        mktcap_2018_usd=round(r['mcap18']) if r.get('mcap18') else '',
        avg_dollar_vol_usd=round(r['addv']) if r.get('addv') else '',
        beta=round(r['beta'],3) if r.get('beta') is not None else '',
        sigma_ann=round(sg,4), sigma_ann_ex_covid=round(sgx,4),
        ipo_date=r.get('ipo','') or '',
        data_start=raw[0]['date'], data_end=raw[-1]['date'], bars=len(raw),
        cell_rank=r.get('cell_idx',''), cell_size=r.get('cell_n',''),
        n_insider=cnt(f'data/insider/{s}.csv'), n_analyst=cnt(f'data/analyst/{s}.csv'),
        n_funding='', n_open_interest='',
        gap_days=max((g[2] for g in gaps.get(s,[])),default=0),
        replaced='Y' if r.get('replaced') else ''))
for r in json.load(open('raw/selection_crypto.json')):
    s=r['symbol']; raw,c=series(f'data/crypto/{s}.csv')
    sg=sigma(c); sgx=sigma(c,('2020-02-15','2020-04-30'))
    out.append(dict(symbol=s,asset_class='crypto',stratum='crypto_legacy' if s in('BTC','ETH','SOL','DOGE') else 'crypto',
        sector='加密',sector_raw='CRYPTO',size_tier='',vol_tier=vt(sg),
        mktcap_2026_usd='',mktcap_2018_usd='',
        avg_dollar_vol_usd=round(r['perp_turnover_med']),beta='',
        sigma_ann=round(sg,4),sigma_ann_ex_covid=round(sgx,4),ipo_date='',
        data_start=raw[0]['date'],data_end=raw[-1]['date'],bars=len(raw),
        cell_rank=r['rank'],cell_size=76,n_insider='',n_analyst='',
        n_funding=cnt(f'data/crypto/{s}_funding.csv'),
        n_open_interest=cnt(f'data/crypto/{s}_oi.csv'),
        gap_days=max((g[2] for g in gaps.get(s,[])),default=0),replaced=''))
cols=list(out[0].keys())
with open('universe.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(out)
print('universe.csv rows',len(out))
