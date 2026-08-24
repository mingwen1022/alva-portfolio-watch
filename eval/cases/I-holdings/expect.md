# I-holdings · 带持仓的组合

## 为什么要这个案例

**在此之前每一个案例都是自选清单（`linked: false`）。**
于是「有持仓」那一整条路从来没被跑过:

```
totalValue · totalPnl · todayPnl · fromHigh   四个 KPI
holdings[].shares / avgCost / value / lifetimePnl
weight 按市值算（不是等权）
allocation.byHolding / byAssetClass 的 value 维度
series.json 的净值曲线 —— 唯一能让它非空的案例
```

真跑两轮之后才发现这个缺口:BC13 讨论了半天「未连账户时净值卡该说什么」,
而**「连了账户时它画得对不对」一次都没测过**。

## 持仓从哪来

⚠️ Alva 的券商账户接口在这个 eval 里连不上（那需要用户本人授权一个真实账户），
所以**持仓写在 query 里**。这也更接近真实用法 —— 用户就是这么说话的。

Skill 要能从一句自然语言里解析出 `symbol · shares · avgCost`，并落进 `book`。

## 判什么

```
L0   series.json 的 points 必须**非空** —— 这是唯一一个它该有内容的案例
     holdings[].shares / avgCost / value 三个都不为 null
L2   账目自洽:Σ(shares × last) + cash == kpi.totalValue（容差 0.01）
     weight 之和 == 1（容差 0.001）· 按市值不是等权
     lifetimePnl == value − shares × avgCost
L4   净值卡**必须画出曲线**，不是空态文案 —— 与 BC13 正好相反的方向
     「未连接账户」这句话不得出现
```

## 与 A-mixed 的区别

A-mixed 是「盯下我的持仓」——**没给持仓**，考的是 agent 会不会去问、
或者会不会编。I-holdings 给了持仓，考的是**给了它会不会用对**。
两个案例问的是相反的问题，都要留。
