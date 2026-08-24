# -*- coding: utf-8 -*-
"""这一本账 —— 单一来源。

⚠️ 存在理由：`US` / `CR` 两个列表原来在 **六个脚本里各写一份**
   （build · build_grades · build_enrich · build_intraday_dist · build_pv5 · build_pv5_full）。
   加一只标的要改六处，而**漏掉任何一处都不会报错** ——
   那只票只会在某一层悄悄消失：没有投递上限、没有盘中分位、没有新闻。
   症状出现在页面上时看起来像「上游没给」。

⚠️ 顺序即页面顺序。
"""

POS = {
    "NVDA": dict(cls="us_equity", sh=60,    cost=150.0,   name="NVIDIA"),
    "TSLA": dict(cls="us_equity", sh=25,    cost=300.0,   name="Tesla"),
    "AMD":  dict(cls="us_equity", sh=15,    cost=210.0,   name="AMD"),
    "MSTR": dict(cls="us_equity", sh=40,    cost=180.0,   name="MicroStrategy"),
    "SOUN": dict(cls="us_equity", sh=900,   cost=9.40,    name="SoundHound AI"),
    # ⚠️ 这两只是**故意加的反例**：全历史跑判据都没过（95% 区间下界 ≤ 1.0），
    #    投递上限落 L2 —— 页面必须能说清「线过了、手机没响、为什么」。
    #    在此之前主账本八只全是 usable，那条路径在这本账上一次都渲染不出来。
    "RIVN": dict(cls="us_equity", sh=300,   cost=22.00,   name="Rivian"),
    "SOFI": dict(cls="us_equity", sh=400,   cost=9.20,    name="SoFi Technologies"),
    "BTC":  dict(cls="crypto",    sh=0.12,  cost=68000.0, name="Bitcoin"),
    "SOL":  dict(cls="crypto",    sh=45,    cost=140.0,   name="Solana"),
    "DOGE": dict(cls="crypto",    sh=52000, cost=0.115,   name="Dogecoin"),
    # ⚠️ ETF 归「其他」，不是美股。样本池是 92 只**个股**按 GICS 部门分的，
    #    部门分类蕴含了单一公司 —— 拿它担保一篮子就是把已验证的标记借出去。
    #    阈值走池级反解（θv=1.75，18 只 ETF 池），thresholdSource = fallback_solved，
    #    并且**不启用 PV5**：盘中阈值没有兜底反解规则。
    "SPY":  dict(cls="other",     sh=40,    cost=430.0,   name="SPDR S&P 500 ETF"),
    "QQQ":  dict(cls="other",     sh=25,    cost=390.0,   name="Invesco QQQ Trust"),
    "GLD":  dict(cls="other",     sh=30,    cost=215.0,   name="SPDR Gold Shares"),
    "TLT":  dict(cls="other",     sh=120,   cost=95.0,    name="iShares 20+ Year Treasury"),
    "XLE":  dict(cls="other",     sh=200,   cost=88.0,    name="Energy Select Sector SPDR"),
}
CASH = 3200.0

US = [s for s, v in POS.items() if v["cls"] == "us_equity"]
CR = [s for s, v in POS.items() if v["cls"] == "crypto"]
OT = [s for s, v in POS.items() if v["cls"] == "other"]      # ETF 等未验证类别
NAME = {s: v["name"] for s, v in POS.items()}

# 图标。美股走 Arrays 的公共资源（按代码拼），加密走 CoinMarketCap 的数字 ID。
# ⚠️ **ETF 那个 pattern 是不存在的。** 实测 SPY / QQQ / GLD / TLT / XLE / IWM 全部 404，
#    而这里一直照 `US + OT` 拼 —— mock 于是给五只 ETF 各配了一张碎图。
#    字母块是设计，碎图是故障，两者在页面上差得很远。
#    ETF 一律不给 logo，让页面画字母块。skill 那边 `init.js` 是先 HEAD 探再填，
#    这里是静态账本，直接按类别排除。
CMC_ID = {"BTC": 1, "SOL": 5426, "DOGE": 74}
LOGO = {**{s: f"https://storage.googleapis.com/arrays-public-assets/logos/{s}.svg" for s in US},
        **{s: f"https://s2.coinmarketcap.com/static/img/coins/64x64/{i}.png" for s, i in CMC_ID.items()}}

# 主题归类。⚠️ 缺一只 build.py 直接报错退出 —— 留空会让 PF2/PF3 少算一整块而不出声。
# ⚠️ 只有美股个股进主题维度。ETF 本身就是一篮子，把它塞进某个主题
#    会让「主题集中度」把一只 SPY 算成一次押注。
THEME = {"NVDA":"AI", "AMD":"AI", "SOUN":"AI",
         "TSLA":"Autos", "RIVN":"Autos",
         "MSTR":"Crypto proxy",
         "SOFI":"Fintech"}
