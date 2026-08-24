"""汇总：通过比例 + 分层交叉表"""
import sys, os, json, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ev_engine2 import ROOT, universe
from collections import Counter, defaultdict

U = universe()
R = json.load(open(f"{ROOT}/out/ev_main.json"))
NOINS = [s for s in U if U[s]["n_insider"] < 30 and s != "SPY"]
NOAN = [s for s in U if U[s]["n_analyst"] < 10 and s != "SPY"]


def bucket(sid, x):
    """标的在该信号下的归类"""
    s = x["sym"]
    if sid in ("EV1", "EV2") and s in NOINS:
        return "数据不适用"
    if sid == "EV3" and s in NOAN:
        return "数据不适用"
    if x["n_trig_cal"] == 0:
        return "零触发"
    if x["err"] or x["nb"] < 5:
        return "样本不足"
    return "通过" if x["lo"] > 1.0 else ("反向" if x["hi"] < 1.0 else "未通过")


SUM = {}
for sid, blk in R.items():
    rows = blk["rows"]
    for x in rows:
        x["bucket"] = bucket(sid, x)
    c = Counter(x["bucket"] for x in rows)
    ev = [x for x in rows if x["bucket"] in ("通过", "未通过", "反向")]
    print(f"\n{'='*92}\n{sid}  {blk['desc']}\n{'='*92}")
    print("  " + " · ".join(f"{k} {v}" for k, v in
          sorted(c.items(), key=lambda kv: -kv[1])) + f"  （合计 {len(rows)}）")
    if ev:
        rr = sorted(x["r"] for x in ev)
        print(f"  可判定 {len(ev)} 只 → 通过 {c['通过']} 只 = {c['通过']/len(ev)*100:.1f}%"
              f" · 反向 {c['反向']} 只 = {c['反向']/len(ev)*100:.1f}%")
        print(f"  倍数分布 中位 {st.median(rr):.3f} · 最小 {rr[0]:.2f} · 最大 {rr[-1]:.2f}"
              f" · >1 的只数 {sum(1 for v in rr if v>1)}/{len(rr)}")
        trg = [x["per_yr"] for x in rows if x["n_trig_cal"] > 0]
        print(f"  触发密度 次/年：中位 {st.median(trg):.1f} · 区间 {min(trg):.1f}–{max(trg):.1f}")
    SUM[sid] = dict(counts=dict(c), n_eval=len(ev),
                    pass_rate=(c["通过"] / len(ev)) if ev else None,
                    rev_rate=(c["反向"] / len(ev)) if ev else None,
                    med_r=st.median([x["r"] for x in ev]) if ev else None)

    # 通过 / 反向 名单
    for tag in ("通过", "反向"):
        L = sorted([x for x in rows if x["bucket"] == tag], key=lambda x: -x["r"])
        if L:
            print(f"\n  【{tag}】{len(L)} 只")
            print(f"  {'标的':<7}{'部门':<7}{'市值':<7}{'次新':<5}{'触发':>5}{'块':>4}{'倍数':>7}{'95% 区间':>16}{'次/年':>7}")
            for x in L:
                ci = "[%.2f, %.2f]" % (x["lo"], x["hi"])
                print(f"  {x['sym']:<7}{x['sector'] or '—':<7}{x['size'] or '—':<7}"
                      f"{'是' if x['new'] else '':<5}{x['n']:>5}{x['nb']:>4}{x['r']:>7.2f}{ci:>16}{x['per_yr']:>7.1f}")

    # 分层交叉表
    for key, lab in (("sector", "行业"), ("size", "市值档"), ("vol", "波动档"), ("new", "次新股")):
        g = defaultdict(lambda: Counter())
        for x in rows:
            k = ("是" if x["new"] else "否") if key == "new" else (x[key] or "—")
            g[k][x["bucket"]] += 1
        print(f"\n  {lab}分层")
        print(f"  {'':<9}{'通过':>5}{'反向':>5}{'未通过':>7}{'样本不足':>9}{'零触发':>7}{'不适用':>7}{'通过率':>8}")
        for k in sorted(g):
            c2 = g[k]
            ne = c2["通过"] + c2["未通过"] + c2["反向"]
            pr = f"{c2['通过']/ne*100:.0f}%" if ne else "—"
            print(f"  {k:<9}{c2['通过']:>5}{c2['反向']:>5}{c2['未通过']:>7}{c2['样本不足']:>9}"
                  f"{c2['零触发']:>7}{c2['数据不适用']:>7}{pr:>8}")

json.dump(SUM, open(f"{ROOT}/out/summary.json", "w"), indent=1, ensure_ascii=False)
json.dump(R, open(f"{ROOT}/out/ev_main.json", "w"), indent=1, ensure_ascii=False, default=str)
