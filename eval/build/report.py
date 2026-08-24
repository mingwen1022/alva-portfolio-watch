# -*- coding: utf-8 -*-
"""把若干次 eval 真跑的结果渲染成一张 HTML。

⚠️ 这份报告**不给总分**。案例平均分会让「账目差 0.03」和「编造数字」折算成同一个扣分 ——
   汇总不得把失败态折叠进正常态。报的是两个东西：
     · 逐案例 × 逐层的 pass / fail 矩阵
     · 每条失败的「期望 vs 实际」两侧的值

⚠️ 「没跑」「跑了没发现」「跑了发现问题」是三种状态，不能挤成两种。
   矩阵里分别是 —（未跑）· ✓（通过）· ✗（失败），缺任何一种都会让读者误读。

用法：
    python3 eval/report.py                      # 扫 alva_test/runs/*/collected
    python3 eval/report.py --out /tmp/eval.html
"""
import json, sys, pathlib, datetime, html, subprocess, os

BASE = pathlib.Path("/Users/ming/project/alva_test/runs")
REPO = pathlib.Path(__file__).resolve().parents[2]      # eval/build/ → 仓库根
OUT = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
      else REPO / "eval" / "report.html"

BADCASES = "https://claude.ai/code/artifact/f4320e13-c1e3-43ba-b07f-0a260264ade3"   # eval/badcases.py 发布出来的那一页

LAYERS = [("L0", "结构"), ("L1", "白名单"), ("L2", "参数与账目"),
          ("L3", "跨文件自洽"), ("L4", "渲染"), ("L5", "需要判断的")]


def judge(collected: pathlib.Path):
    """对一次抓取跑判官。

    ⚠️ 层归属由判官脚本给（`--json` 的 byLayer），不在这里从中文输出里 grep。
       上一版用 `"L1" in line` 分层 —— 「L1-L3 未跑」那一行会同时命中 L1 和 L3，
       而判官的措辞一改，分层就静默失效，报告照样满屏 ✓。

    ⚠️ 「跑了通过」「跑了失败」「一条都没求值」是三种结局。
       某一层 ran=0 时报「未跑」，**不报通过** —— 2026-08-23 第一次真跑就是这个形状：
       0 条 finding，逐 finding 的断言一条都没求值，旧判官打印「全过」，
       而产物的蜡烛图是空的。
    """
    pb = collected / "playbook"
    if not pb.exists():
        # ⚠️ **「没发布」有两种，判反了会把一次正确的拒绝记成失败。**
        #    R9（0700.HK）:agent 真去探了端点、拿到 `400 stock symbol not found`、
        #    引 skill 自己的规则拒绝建一个全空的面板，并给了具体替代（TCEHY）。
        #    那是**这条规则想要的结果**，不是它没做到。
        #    区分靠 collect 存下来的 `outcome` —— 它看的是 agent 说了什么，不是产物有没有。
        try:
            man = json.loads((collected / "manifest.json").read_text())
        except Exception:
            man = {}
        if man.get("outcome") == "no_playbook":
            # ⚠️ ⊘ 的意思是「**没有产物，理由待判**」，不是「拒绝得对」。
            #    收集器只摆证据（agent 最后一段 + 它在拒绝前跑过几条 alva 命令），
            #    站不站得住由 L5 判 —— 一次静默的空跑和一次有依据的拒绝，
            #    产物目录长得一模一样，靠代码分不开。
            n = man.get("probedBeforeDeclining")
            why = (man.get("finalMessage") or "agent 什么都没说 —— 这一条大概率是 ✗").strip()
            head = f"未产出 · 拒绝前跑过 {n} 条 alva 命令 · 理由待 L5 判\n\n" if n is not None else ""
            return {k: ("declined" if k == "L0" else "skip", [head + why])
                    for k, _ in LAYERS}, []
        return {k: ("fail" if k == "L0" else "skip",
                    ["产物根不存在 —— agent 没有发布"]) for k, _ in LAYERS}, []

    r = subprocess.run(["python3", str(REPO / "eval/assertions.py"),
                        str(pb / "data"), "--json"], capture_output=True, text=True, cwd=REPO)
    try:
        out = json.loads(r.stdout)
    except Exception:
        return {k: ("fail" if k == "L0" else "skip",
                    [f"判官自己挂了: {(r.stderr or r.stdout)[-300:]}"])
                for k, _ in LAYERS}, []

    fails, misses = out.get("fail", []), out.get("miss", [])
    res = {}
    for k, _ in LAYERS:
        # 判官的层名带后缀（L3量纲 / L3归因…），按前缀归并
        agg = {kk: v for kk, v in (out.get("byLayer") or {}).items() if kk.startswith(k)}
        ran = sum(v["ran"] for v in agg.values())
        bad = [x for x in fails if x.startswith(f"[{k}")]
        miss = [x for x in misses if x.startswith(f"[{k}")]
        if bad:
            res[k] = ("fail", bad[:12])
        elif ran:
            res[k] = ("pass", [f"求值 {ran} 条"] + (miss[:4] if miss else []))
        else:
            res[k] = ("notrun", miss[:4] or ["这一层一条断言都没求值 —— 不是通过，是没查"])
    # ── L4 渲染层：真的在浏览器里跑一遍产物 ──
    # ⚠️ 需要 index.html 与产物在同一个目录。真跑抓回来的 playbook 根就是这个形状。
    if (pb / "index.html").exists():
        r4 = subprocess.run(["node", str(REPO / "eval/l4_render.js"), str(pb), "--json"],
                            capture_output=True, text=True, cwd=REPO)
        try:
            o4 = json.loads(r4.stdout)
            f4, m4, ran4 = o4.get("fail", []), o4.get("miss", []), o4.get("ran", 0)
            if f4:
                res["L4"] = ("fail", f4[:12])
            elif ran4:
                res["L4"] = ("pass", [f"求值 {ran4} 条"] + m4[:4])
            else:
                res["L4"] = ("notrun", m4[:4] or ["一条都没求值"])
        except Exception:
            res["L4"] = ("notrun", [f"L4 自己挂了: {(r4.stderr or r4.stdout)[-200:]}"])
    else:
        res["L4"] = ("notrun", ["产物里没有 index.html，页面渲染无从跑起"])
    # ── L5 · 需要判断的 ──
    # 判官是主 session 的子 agent，判决落在 collected/l5.json（见 eval/l5_collect.py）。
    # ⚠️ 文件不在 = **没判**，不是通过。这一层默认「未跑」，只有拿到判决才改。
    f5 = collected / "l5.json"
    if not f5.exists():
        res["L5"] = ("notrun", ["还没判 —— 跑 eval/l5_extract.py 抽题、派子 agent、"
                                "再用 eval/l5_collect.py 收票"])
    else:
        try:
            o5 = json.loads(f5.read_text())
            bad = [i for i in o5["items"] if i["verdict"] == "fail"]
            low = [i for i in o5["items"] if i.get("lowConfidence")]
            if o5.get("absentLenses"):
                res["L5"] = ("notrun", [f"角度缺席 {o5['absentLenses']} —— 全票制下缺一票就判不了"])
            elif bad:
                res["L5"] = ("fail", [f"{i['id']} ← {'/'.join(i['failedLenses'])}"
                                      for i in bad[:12]])
            elif o5["items"]:
                res["L5"] = ("pass", [f"{len(o5['items'])} 道题 · {len(o5['lenses'])} 个角度全票通过"]
                                     + ([f"⚠️ {len(low)} 道有角度判不了"] if low else []))
            else:
                res["L5"] = ("notrun", ["抽不出题 —— 这一轮没有需要判断的东西"])
        except Exception as e:
            res["L5"] = ("notrun", [f"l5.json 读不了: {e}"])
    return res, [f"findings {out.get('findings')}", f"求值合计 {out.get('ran')}"]


def credits_of(collected):
    """按 source 分组核账。

    ⚠️ 不能用「总额 ÷ 条目数」—— 一次逻辑调用在账单里是 5–8 条，
       带检索的 ask 产出一条 79–299 的 rollup（`extras` 为 null）外加若干条
       6 上下的检索子条。拿条目数去除总额得到的数不对应任何真实的东西。

    ⚠️ `playbook` 是**第三类**计费来源：脚本跑起来本身按 2 credits/分钟。
       它既不是拉数也不是 LLM，按「端点 × 单价」的模型核账会整类漏掉。
       所以这里枚举 source 的全部取值，未知类别单列出来，而不是并进「其他」——
       并进去就等于下一个没见过的来源同样会被吞掉。
    """
    f = collected / "credits.json"
    if not f.exists():
        return None
    try:
        raw = json.loads(f.read_text())
        rows = [e["node"] for e in raw["items"]["edges"]]
    except Exception:
        return None
    # ⚠️ 切不出本轮时间窗时**不显示数字**。显示当天总额等于把「账号今天花了多少」
    #    写在「这一轮花了多少」那一列下面 —— 一个看起来精确的错数。
    if raw.get("_window") is None and not rows:
        return {"total": None, "attributions": 0, "runtimeSec": 0, "by": {},
                "note": raw.get("_note") or "无法归属到本轮"}
    known = {"ask", "playbook", "arrays_x_feed"}
    by, attr, runtime_ms = {}, 0, 0
    for n in rows:
        src, amt, ex = n.get("source"), (n.get("amount") or 0), n.get("extras")
        if src == "ask":
            # rollup 的 extras 是 null；检索子条带 billing_source。实测确认
            k = "归因(LLM)" if ex in (None, "") else "归因(检索子条)"
            if ex in (None, ""):
                attr += 1
        elif src == "playbook":
            k = "运行时长"
            try:
                runtime_ms += json.loads(ex or "{}").get("runtime_ms") or 0
            except Exception:
                pass
        elif src in known:
            k = "拉数(计费端点)"
        else:
            k = f"未归类:{src}"      # 新来源要看得见，不能并进「其他」
        b = by.setdefault(k, {"n": 0, "amt": 0})
        b["n"] += 1
        b["amt"] += amt
    return {"total": sum(b["amt"] for b in by.values()), "attributions": attr,
            "runtimeSec": round(runtime_ms / 1000), "by": by}


def query_of(case_dir_name):
    """run 目录名形如 `C-single-20260823-003545` —— 前面是案例名，后面是时间戳。
    ⚠️ 案例名里本身带连字符，所以只能从**右边**切两段时间戳，不能 split("-")[0]。"""
    parts = case_dir_name.rsplit("-", 2)
    case = parts[0] if len(parts) == 3 and parts[1].isdigit() else case_dir_name
    f = REPO / "eval" / "cases" / case / "input.md"
    if not f.exists():
        return case, "（找不到 input.md）", None
    lines = [l for l in f.read_text().strip().split("\n") if l.strip()]
    q = lines[0]
    # ⚠️ 只印第一行会把这一轮真正在测的东西藏起来。K-book9 的第一行是
    #    「帮我盯着这些持仓，有大事提醒我。现金 3200 美元。」——
    #    而九只标的的股数与成本、四条用户线，全在后面几行，**都在同一条消息里**。
    #    读报告的人看到那一行会以为持仓是从别处连进来的，而这一轮恰恰是在测
    #    「持仓写进 query」这条路（§1.1 的第三格）。
    rest = " ".join(lines[1:]).strip()
    return case, q, (rest[:220] + ("…" if len(rest) > 220 else "")) if rest else None


# 轮次按时间排序。**轮次是这份报告的主键** —— 一轮 = 一个 query = 一套 badcase。
# 只写案例名的话，同一个案例跑两次就没法分辨哪条失败属于哪一次。
runs = sorted([p for p in BASE.glob("*/collected") if p.is_dir()],
              key=lambda p: p.parent.name.rsplit("-", 2)[-2:]) if BASE.exists() else []
rows = []
for rn, c in enumerate(runs, 1):
    case = c.parent.name
    case_name, query, query_more = query_of(case)
    man = {}
    try:
        man = json.loads((c / "manifest.json").read_text())
    except Exception:
        pass
    # ⚠️ 模式必须显示。「先选了 skill」与「靠描述自己触发」是**两道不同的题**，
    #    把两种模式的结果并排放而不标出来，等于拿两个不同实验的数字互相比。
    mf = c.parent / "mode.txt"
    mode = mf.read_text().strip() if mf.exists() else "（早于模式开关，按未指名记）"
    res, _ = judge(c)
    rows.append({"round": f"R{rn}", "case": case, "caseName": case_name, "query": query,
                 "queryMore": query_more,
                 "nth": sum(1 for r in rows if r["caseName"] == case_name) + 1,
                 "mode": mode,
                 "files": len(man.get("files", [])),
                 "user": man.get("user"), "at": man.get("collectedAt"),
                 "res": res, "credits": credits_of(c),
                 "ext": man.get("externalRefs", "missing")})

# ⚠️ **修完不等于验过。** 一条缺陷只有在**同一个 query 重跑、原来那批断言变绿**之后
#    才算关掉 —— 「我改了代码」和「它现在对了」是两句话。
#    所以同一个案例跑第二次时，报告要直接把「哪一层从红转绿」摆出来，
#    而不是让人对着两行自己比。
def regression(rows):
    # ⚠️ **只在同一模式内比。** 指名 skill 与不指名是两道题 ——
    #    拿未指名的 R2 去比指名的 R4，那条「✗→✓」到底是修复生效还是换了模式，分不出来。
    #    跨模式的相邻两轮**不产出结论**，只记一行「模式变了，不可比」。
    out = []
    seen = {}
    for r in rows:
        prev = seen.get(r["caseName"])
        if prev and prev.get("mode") != r.get("mode"):
            out.append({"case": r["caseName"], "from": prev["round"], "to": r["round"],
                        "flips": [], "incomparable":
                        f'模式从「{prev.get("mode")}」变成「{r.get("mode")}」—— 不可比'})
            seen[r["caseName"]] = r
            continue
        if prev:
            flips = []
            for k, name in LAYERS:
                a, b = prev["res"][k][0], r["res"][k][0]
                if a != b:
                    flips.append((k, name, a, b))
            out.append({"case": r["caseName"], "from": prev["round"], "to": r["round"],
                        "flips": flips})
        seen[r["caseName"]] = r
    return out


# ⚠️ 「正确地拒绝」必须与「失败」分开。一次拒绝里 agent 探了端点、
#    拿到明确的 400、引规则说明为什么不建、并给了替代 —— 那是规则想要的结果。
#    记成 ✗ 会让「不建一个全空的面板」这条规则在报告里显示为一次退步。
MARK = {"pass": ("✓", "ok"), "fail": ("✗", "bad"), "skip": ("–", "skip"),
        "declined": ("⊘", "declined"), "notrun": ("—", "none")}
# ⊘ = 没有产物且 agent 留了话。**它不表示「拒绝得对」** —— 那要 L5 判。

def cell(v):
    m, cls = MARK[v[0]]
    return f'<td class="{cls}" title="{html.escape(" | ".join(v[1])[:400])}">{m}</td>'

body = []
for r in rows:
    tds = "".join(cell(r["res"][k]) for k, _ in LAYERS)
    cr = r["credits"]
    # 三种状态分开写:没抓到账单 · 抓到了但切不出本轮 · 切出来了
    if not cr:
        crs = "—"
    elif cr.get("total") is None:
        crs = cr.get("note") or "无法归属到本轮"
    else:
        parts = " + ".join(f'{k} {v["amt"]}' for k, v in
                           sorted(cr["by"].items(), key=lambda x: -x[1]["amt"]))
        crs = (f'{cr["total"]} = {parts} · 归因 {cr["attributions"]} 次 '
               f'· 跑了 {cr["runtimeSec"]}s') if parts else f'{cr["total"]}'
    # 「第 N 次」在 f-string 外面算好 —— 隐式拼接的 f-string 之间插一个 `+ (...)`
    # 会把链条断掉，而报出来的行号指向整段的开头，看着像别的地方错了。
    nth = (f'<span class="nth">第 {r["nth"]} 次</span>') if r["nth"] > 1 else ''
    md = r.get("mode", "")
    mode_badge = (f'<span class="nth mode-{"sel" if "selected" in md and "not" not in md else "uns"}">'
                  f'{html.escape("指名了 skill" if md == "skill-selected" else ("未指名" if md == "skill-not-selected" else md))}</span>')
    # ⚠️ 平台自己有一个同名同用途的 `portfolio-watch-setup`，agent 拉得到。
    #    实测过一轮：拉完照着它写，撞 Pro 订阅墙，绕回来时只建了两个 producer。
    #    **不判对错**（用户手上本来就同时有这两个，要测的正是「两个都在时我们赢不赢」），
    #    但一轮参考了竞品实现的成绩不能被当成我们这个 skill 的成绩，所以必须在行上看得见。
    ext = r.get("ext")
    if ext == "missing" or ext is None:
        ext_badge = '<span class="nth ext-unk" title="这一轮没抓到 transcript，查不了">外部实现 未知</span>'
    elif ext:
        ext_badge = ('<span class="nth ext-hit" title="'
                     + html.escape(" · ".join(f"{k}×{v}" for k, v in ext.items()))
                     + '">参考了外部实现</span>')
    else:
        ext_badge = ''
    ts = r["case"].rsplit("-", 2)
    stamp = f'{ts[-2]}-{ts[-1]}' if len(ts) == 3 else r["case"]
    # ⚠️ 在 f-string 链**外面**算好 —— 隐式拼接的几段之间插一个 `+ (...)`
    #    会把链条断掉，而 Python 报的行号指向整段开头，看着像别处错了。
    #    这条本文件上面就写过一次（「第 N 次」那处），我又踩了一遍。
    qmore = (f'<span class="qmore">同一条消息里还写了：'
             f'{html.escape(r["queryMore"])}</span>') if r.get("queryMore") else ''
    body.append(f'<tr><th class="rd">{r["round"]}</th>'
                f'<td class="q"><b>{html.escape(r["caseName"])}</b>{nth}{mode_badge}{ext_badge}'
                f'<br><span class="qt">「{html.escape(r["query"])}」</span>{qmore}'
                f'<br><span class="ts">{html.escape(stamp)}</span></td>'
                f'{tds}'
                f'<td class="n">{r["files"]}</td><td class="n">{html.escape(crs)}</td>'
                f'<td class="n">{html.escape(str(r["user"] or "—"))}</td></tr>')

fails = []
for r in rows:
    for k, name in LAYERS:
        st, detail = r["res"][k]
        if st == "fail":
            for d in detail or ["（无细节）"]:
                fails.append(f'<tr data-round="{r["round"]}"><td class="rd">{r["round"]}</td>'
                             f'<td class="n">{html.escape(r["caseName"])}</td>'
                             f'<td>{k} {name}</td>'
                             f'<td>{html.escape(d)}</td></tr>')

REGR = regression(rows)
_rg = []
for g in REGR:
    if g.get("incomparable"):
        _rg.append(f'<tr><td class="rd">{g["from"]}→{g["to"]}</td>'
                   f'<td class="n">{html.escape(g["case"])}</td>'
                   f'<td colspan="2" class="bad" style="text-align:left">'
                   f'⚠️ {html.escape(g["incomparable"])}</td></tr>')
    elif not g["flips"]:
        _rg.append(f'<tr><td class="rd">{g["from"]}→{g["to"]}</td>'
                   f'<td class="n">{html.escape(g["case"])}</td>'
                   f'<td colspan="2" class="n">逐层结果没有变化</td></tr>')
    for k, name, a, b in g["flips"]:
        good = (a in ("fail", "notrun")) and b == "pass"
        _rg.append(f'<tr><td class="rd">{g["from"]}→{g["to"]}</td>'
                   f'<td class="n">{html.escape(g["case"])}</td>'
                   f'<td>{k} {name}</td>'
                   f'<td class="{"ok" if good else "bad"}" style="text-align:left">'
                   f'{MARK[a][0]} → {MARK[b][0]}'
                   f'{"  修复生效" if good else ("  退化" if a == "pass" else "  状态变化")}</td></tr>')
regr_html = ("""<h2>回归 · 同一个 query 再跑一次</h2>
<div class="note">
<b>修完不等于验过。</b>一条缺陷只有在同一个 query 重跑、原来那批断言变绿之后才算关掉 ——
「我改了代码」和「它现在对了」是两句话。<br>
这张表只看<b>层的状态翻转</b>；具体哪条断言变了，把鼠标停在矩阵里那一格上。<br>
⚠️ <b>只在同一模式内比。</b>指名 skill 与不指名是两道题 —— 跨模式的两轮不产出结论，
只标「不可比」，否则一条「✗→✓」分不清是修复生效还是换了模式。
</div>
<div class="wrap"><table>
<thead><tr><th>轮次</th><th>案例</th><th>层</th><th>变化</th></tr></thead>
<tbody>""" + ("".join(_rg) or '<tr><td colspan="4" class="empty">还没有任何案例跑过第二次</td></tr>')
             + "</tbody></table></div>") if REGR else ""

# ⚠️ 原来这里有一整张「失败明细」表。去掉它有两个理由：
#    ① 它与矩阵格子的 tooltip 完全重复，而 tooltip 就在 ✗ 上，读者本来就在那儿；
#    ② 它按轮次排，最后一条停在 R5 —— 因为 R6 之后一条失败都没有。
#       但表自己不说这件事，看起来像「没更新到最新轮次」。**实测用户就是这么读的。**
#    留一句话把范围讲清楚，比留一张会被误读的表好。
_fr = sorted({r["round"] for r in rows for k, _ in LAYERS if r["res"][k][0] == "fail"},
             key=lambda x: int(x[1:]))
fail_line = (f'共 {len(fails)} 条断言失败，全部落在 {"、".join(_fr)}；'
             f'其余 {len(rows) - len(_fr)} 轮逐层全过。'
             if _fr else f'{len(rows)} 轮里没有一条断言失败。')

doc = f"""<title>Portfolio Watch · Eval</title>
<style>
:root {{ --bg:#fff; --fg:#16181d; --dim:#6b7280; --line:#e5e7eb;
        --ok:#0f7b56; --bad:#b42318; --skip:#9ca3af; }}
:root:not([data-theme="light"]) {{ }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#111317; --fg:#e6e8ec; --dim:#9aa1ad; --line:#272b33;
  --ok:#4ade80; --bad:#f87171; --skip:#6b7280; }} }}
:root[data-theme="dark"] {{ --bg:#111317; --fg:#e6e8ec; --dim:#9aa1ad; --line:#272b33;
  --ok:#4ade80; --bad:#f87171; --skip:#6b7280; }}
body {{ background:var(--bg); color:var(--fg); margin:0; padding:32px 28px 64px;
  font:14px/1.6 ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif; }}
h1 {{ font-size:19px; font-weight:500; margin:0 0 4px; }}
h2 {{ font-size:14px; font-weight:500; margin:32px 0 10px; }}
p.sub {{ color:var(--dim); margin:0 0 24px; }}
.wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; font-size:13px; min-width:100%; }}
th,td {{ border-bottom:1px solid var(--line); padding:7px 12px; text-align:left;
  white-space:nowrap; }}
thead th {{ color:var(--dim); font-weight:500; }}
tbody th {{ font-weight:500; }}
td.ok {{ color:var(--ok); text-align:center; }}
td.bad {{ color:var(--bad); text-align:center; font-weight:600; }}
td.skip,td.none {{ color:var(--skip); text-align:center; }}
td.n {{ color:var(--dim); }}
td.q,th.rd {{ white-space:normal; }}
th.rd {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px;
  vertical-align:top; }}
td.rd {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--dim); }}
td.q {{ min-width:20rem; max-width:30rem; line-height:1.45; vertical-align:top; }}
td.q .qt {{ color:var(--fg); }}
/* 后续行：持仓明细、用户线这些**同在一条消息里**的内容。只印第一行会让人
   以为持仓是从账户连进来的，而有几轮恰恰在测「写进 query」那条路。 */
td.q .qmore {{ color:var(--dim); font-size:11.5px; display:block; margin-top:2px; }}
td.q .nth {{ display:inline-block; margin-left:7px; font-size:11px;
  padding:1px 6px; border-radius:3px; background:var(--line); color:var(--dim); }}
td.q .mode-sel {{ background:var(--ok); color:var(--bg); }}
td.q .ext-hit {{ background:var(--warn); color:var(--bg); cursor:help; }}
td.declined {{ color:var(--fg); background:color-mix(in srgb, var(--dim) 14%, transparent);
  font-weight:600; }}
td.q .ext-unk {{ outline:1px dashed var(--line); cursor:help; }}
td.q .ts {{ color:var(--dim); font-size:11.5px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
a.lnk {{ color:var(--fg); text-decoration:none; border-bottom:1px solid var(--line); }}
a.lnk:hover,a.lnk:focus-visible {{ border-bottom-color:currentColor; }}
a.lnk:focus-visible {{ outline:2px solid currentColor; outline-offset:3px; border-radius:2px; }}
.note {{ border-left:2px solid var(--line); padding:2px 0 2px 14px; color:var(--dim);
  margin:14px 0; max-width:64ch; white-space:normal; }}
.empty {{ color:var(--dim); padding:14px 0; }}
</style>

<h1>Portfolio Watch · Eval</h1>
<p class="sub">{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · {len(rows)} 次真跑
  · <a class="lnk" href="{BADCASES}">Badcase 台账 →</a></p>

<div class="note">
不给总分。案例平均分会把「账目差 0.03」和「编造数字」折算成同一个扣分 ——
汇总不得把失败态折叠进正常态。<br>
矩阵里三种状态是分开的：<b>✓</b> 跑了通过 · <b>✗</b> 跑了失败 · <b>—</b> 没跑。
把「没跑」显示成通过，是这份报告最容易骗人的地方。
</div>

<h2>案例 × 层</h2>
<div class="wrap"><table>
<thead><tr><th>轮次</th><th>案例 · 投的那句话</th>{''.join(f'<th>{k}<br><span style="font-weight:400">{n}</span></th>' for k,n in LAYERS)}
<th>产物文件</th><th>credits</th><th>账号</th></tr></thead>
<tbody>{''.join(body) or '<tr><td colspan="11" class="empty">还没有任何一次真跑</td></tr>'}</tbody>
</table></div>

{regr_html}

<h2>逐条缺陷</h2>
<div class="note">
{fail_line}<br>
矩阵里的 <b>✗</b> 只说哪一层挂了，<b>鼠标停在那一格上能看到当时的期望与实际</b>。
挂的是什么、判官为什么没看见、修了没有 —— 在
<a class="lnk" href="{BADCASES}">Badcase 台账</a>。<br>
那一页真正要读的是「判官当时抓到没有」这一列:缺陷会被修掉,判官的盲区不修就会一直在。
</div>

<h2>这份报告测不到什么</h2>
<div class="note">
<b>一个安静的案例测不到告警那几层。</b>矩阵里 <b>—</b> 不是通过 ——
C-single 单只标的不触发时，L1 白名单一条断言都求值不了，因为那一层是对着 finding 判的。
要覆盖它得靠会触发的案例（R2 跑了 6 条）。<b>案例的覆盖边界与缺陷是两回事，但一样要说出来。</b><br><br>
阈值本身对不对（判据在 backtest/，eval 只判用没用对表里的数）·
回放测不到端点变更 · 真跑测不到稳定性 · L5 三次一致只说明稳定不说明正确 ·
组合层行为 · 港股与 A 股只覆盖措辞 · 真实券商账户需要一个多笔含空头非单一币种的账户 ·
推送到 IM 属发布后的手工验收。
</div>
"""
OUT.write_text(doc)
print(f"✅ {OUT}  ·  {len(rows)} 次真跑 · 失败明细 {len(fails)} 条")
# ⚠️ 生成 ≠ 发布。本文件重生成后，**已发布的 artifact 还是旧的** ——
#    2026-08-23 连着三次因此被用户指出「看不到新的那一轮」。
#    与 ALFS 写了但没 release 是同一个形状:验证停在了「文件对了」，
#    而用户看到的是「发布出去的那份」。
print("⚠️ 这只是重生成了本地文件。**artifact 是另一步** —— 不重新发布，"
      "用户看到的还是上一版。")
