#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按依赖顺序跑完整条管线。

⚠️ 存在理由：`build.py` 只产出它自己算的那部分，其余字段由下游脚本补。
   审计发现「重跑 build.py 会把下游产出冲成 null」，而冲掉的表现是字段变 null,
   看起来像上游没给。现在 build.py 改成合并写，并由本脚本保证顺序。

⚠️ 任何一次性补丁都必须变成这里的一个阶段。
   补丁不在这里 = 下次重跑就没了 = 数据无法从仓库重新生成。
"""
import subprocess, sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))

STAGES = [
    ("build_signals.py",      "信号目录 signals.json —— 原来是手写的，加资产类别时不会跟着动"),
    ("build.py",              "M 层 → S 层 → portfolio · series · findings · baselines · symbols"),
    ("build_pv5.py",          "盘中 PV5：当日每一根触发 bar + 盘中线"),
    ("build_pv5_findings.py", "PV5 → findings · scan.bar · baselines.theta_*_bar · alertHistory"),
    ("build_enrich.py",       "新闻 · 资金费率 · 用户线 findings —— 这三块 build.py 不产出"),
    ("build_m23.py",          "M23 分布可用性 ρ"),
    ("build_grades.py",       "逐标的投递上限 signalGrades（全历史）"),
    ("build_intraday_dist.py","盘中幅度分位 distributionBar（同一时刻）"),
    ("build_derive.py",       "派生：novelty · priority · delivery · benchmark · pnl · assetClass"),
    ("build_template.py",     "交付模板 skill/template/index.html —— 从 mock 减法产出，不手工另存"),
]

def main():
    fail = []
    for script, what in STAGES:
        p = os.path.join(HERE, script)
        if not os.path.exists(p):
            print(f"❌ 缺 {script}"); fail.append(script); continue
        t0 = time.time()
        r = subprocess.run([sys.executable, p], capture_output=True, text=True, cwd=os.path.dirname(HERE))
        ms = int((time.time() - t0) * 1000)
        if r.returncode:
            print(f"❌ {script:26s} {what}\n{r.stdout[-800:]}{r.stderr[-800:]}")
            fail.append(script)
        else:
            print(f"✅ {script:26s} {ms:5d}ms  {what}")
    if fail:
        print(f"\n❌ {len(fail)} 个阶段失败：{fail}"); sys.exit(1)
    print("\n跑一致性检查确认产物：python3 backtest/scripts/check_consistency.py")

if __name__ == "__main__":
    main()
