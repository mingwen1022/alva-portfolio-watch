"""从 vintage 数据构造「首次发布日历」。

每个 observation date 在 API 里出现多次（首发 + 后续修订 vintage）。
真实事件 = 首次发布 = min(release_date)。

两个必须处理的坑：
① 哨兵批次   release_date <= 2020-01-01 的行是 vintage 档案起点前的批量打标，
             CPI 32% / FEDERAL_FUNDS 75% 的行属于此类，不含真实发布日
② 借尸还魂   丢掉哨兵后，2020 年前的老观测会把「首次年度修订日」当成首发，
             在 2020-02-11 这类日期上凭空造出 60 条事件。
             解决：只保留 obs_date >= CUTOFF 的观测（其自然首发必然晚于档案起点），
             并对 obs→release 滞后设上限做二次校验
"""
import csv, os, datetime, statistics as st

D = "/Users/ming/project/alva/backtest/data/macro"
SENTINEL = "2020-01-01"
CUTOFF   = "2019-10-01"          # 其自然首发落在 2020-01 之后

# 每个指标的滞后上限（日）：超过说明是修订日冒充首发
LAG_MAX = {"CPI":70, "CORE_CPI":70, "TOTAL_NONFARM_PAYROLL":70,
           "UNEMPLOYMENT_RATE":70, "GDP":160, "REAL_GDP":160,
           "FEDERAL_FUNDS":60, "INITIAL_CLAIMS":30}

def load(ind):
    rows=[]
    with open(f"{D}/{ind}.csv") as f:
        for r in csv.DictReader(f):
            rows.append((r["obs_date"], float(r["value"]), r["release_date"]))
    return rows

def d(s): return datetime.date.fromisoformat(s)

def first_release(ind):
    """-> list of (release_date, obs_date, value)，按 release_date 升序"""
    best={}
    for od, v, rd in load(ind):
        if rd <= SENTINEL:  continue
        if od <  CUTOFF:    continue
        if od not in best or rd < best[od][0]:
            best[od]=(rd, v)
    out=[]
    lm = LAG_MAX.get(ind, 90)
    for od,(rd,v) in best.items():
        if (d(rd)-d(od)).days > lm:  continue
        out.append((rd, od, v))
    out.sort()
    return out

if __name__=="__main__":
    for ind in ["CPI","CORE_CPI","TOTAL_NONFARM_PAYROLL","UNEMPLOYMENT_RATE",
                "GDP","REAL_GDP","FEDERAL_FUNDS","INITIAL_CLAIMS"]:
        cal=first_release(ind)
        rds=[r[0] for r in cal]
        gaps=sorted((d(b)-d(a)).days for a,b in zip(rds,rds[1:]))
        lags=sorted((d(rd)-d(od)).days for rd,od,_ in cal)
        print(f"{ind:24s} 事件 {len(cal):4d}  {rds[0]}→{rds[-1]}  "
              f"间隔中位 {st.median(gaps):.0f}[{gaps[0]}–{gaps[-1]}]  "
              f"滞后中位 {st.median(lags):.0f}[{lags[0]}–{lags[-1]}]  同日重复 {len(rds)-len(set(rds))}")
