# -*- coding: utf-8 -*-
"""从判官代码里抽出「每一层实际断言了什么」，生成 eval/judges.md。

⚠️ **不要手写这份清单。** 断言有 50 多条、分散在四个文件里，手写的版本第二天就会
   和代码分叉 —— 而分叉的方向恰好是最坏的那个:文档说查了，代码没查。
   本项目已经在「同一事实两个副本」上栽过很多次（见 notes/ 第五类根因）。

抽法是解析 AST 找 `A(layer, name, ...)` 与 `AS(...)`，把第一个参数（层）和
第二个参数（这条断言说什么）取出来。f-string 里的变量还原成占位符。
"""
import ast, pathlib, re, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]      # eval/build/ → eval/

def lit(node):
    """把断言名还原成可读的字符串；f-string 里的表达式写成 ⟨变量⟩。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                src = ast.unparse(v.value) if hasattr(v, "value") else "?"
                out.append("⟨" + src.split("(")[0].strip() + "⟩")
        return "".join(out)
    return None

def from_py(path, fname="A"):
    rows = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fname):
            continue
        if len(n.args) < 2:
            continue
        layer, name = lit(n.args[0]), lit(n.args[1])
        if layer and name:
            rows.append((layer, name, n.lineno))
    return rows

def from_js(path):
    """l4_render.js 用的是 `A("名字", 条件, "细节")` —— 层固定是 L4。"""
    rows = []
    txt = path.read_text(encoding="utf-8")
    for m in re.finditer(r'\bA\(\s*(["`])(.+?)\1', txt):
        rows.append(("L4", m.group(2), txt[:m.start()].count("\n") + 1))
    return rows

SRC = [
    ("eval/judges/assertions.py", lambda: from_py(ROOT / "judges" / "assertions.py")),
    ("eval/judges/l4_render.js",  lambda: from_js(ROOT / "judges" / "l4_render.js")),
]

by_layer = collections.OrderedDict()
for label, fn in SRC:
    for layer, name, ln in fn():
        by_layer.setdefault(layer, []).append((name, label, ln))

LAYER_DESC = {
    "L0":      ("结构与内容",
                "八个必需文件在不在、能不能解析，以及**该有值的地方是不是空的**。"
                "空值和缺字段是两回事 —— 前者页面渲染成破折号，看起来像上游没给数，"
                "排查会被带去错误的一层。"),
    "L1":      ("白名单",
                "`signalId` 只能来自 `signals.json` 的 13 条；证据等级被证伪（red）的不得出现。"),
    "L2":      ("参数",
                "阈值来源必须在枚举内；兜底反解（`fallback_solved`）的标的证据等级不得显示为绿 —— "
                "阈值是解出来的，不是验证过的。"),
    "L2账目":   ("账目",
                "持仓 + 现金 = 总额、权重和 + 现金占比 = 1、Σ 单只盈亏 = 总盈亏。"
                "连了账户就每只都要有 shares/avgCost/value，没连就整块不出。容限 0.02。"),
    "L3覆盖":   ("跨文件 · 覆盖",
                "scan 集合必须等于持仓集合 —— 少一只就是那只票今天根本没被扫过，"
                "而页面上它只是安静地待着。触发了的标的，对应粒度的 scan 必须是 `triggered`。"),
    "L3量纲":   ("跨文件 · 量纲",
                "`unit` 与信号必须对上（PV1=session · PV5=bar），(unit, 资产类别) 要有对应的 θ；"
                "线值只存一处，findings 里不得另存一份。"),
    "L3同源":   ("跨文件 · 同源",
                "同一个事实在两个文件里必须相等 —— 历史触发次数 vs 告警历史条数。"),
    "L3投递":   ("跨文件 · 投递",
                "每条 finding 都要有 `delivery`；level 必须是三道上限里最严的那个；"
                "`cappedBy` 指向的那一处**确实等于** level —— 否则理由和结果对不上。"),
    "L3基准":   ("跨文件 · 基准",
                "benchmark 两支形状必须一致，不适用时三个值同时为 null。"
                "一个键两种形状，下一个读它的人会挑错一支。"),
    "L3归因":   ("跨文件 · 归因",
                "`timing` 要等于纯函数重算的结果、`origin` 在枚举内、url 可解析；"
                "用户线与财报日历**从不做归因** —— 它们自带原因。"),
    "L3自洽":   ("跨文件 · 自洽",
                "基线不足 60 日时不得有名次；证据等级不是绿也不是「不适用」时，不得可推送。"),
    "L4":      ("渲染",
                "无头浏览器真加载一遍：零未捕获异常、无 404、四个 tab 的卡片都有正文、"
                "页面文本里没有 NaN / undefined / [object Object]、"
                "**页面上印的数字与产物里的值逐个对得上**。"),
}


out = ["# 判官逐条 · 每一层实际断言了什么", "",
       "> ⚠️ **本文件由 `eval/build/gen_judges.py` 从判官代码生成，不要手写。**",
       "> 断言分散在四个文件里，手写的清单会和代码分叉 —— 而分叉的方向恰好最坏:",
       "> 文档说查了，代码没查。改了断言就重跑一次这个脚本。", "",
       "L5 不在这里 —— 它是子 agent 判的「这句话站不站得住」，题目由 "
       "[`l5_extract.py`](l5_extract.py) 抽、判决由 [`l5_collect.py`](l5_collect.py) 收（全票制，"
       "任一角度 fail 即 fail）。为什么不用多数决，见 [PLAN.md §五](PLAN.md)。", ""]

total = 0
for layer in sorted(by_layer, key=lambda x: (x[:2], x)):
    rows = by_layer[layer]
    total += len(rows)
    title, desc = LAYER_DESC.get(layer, (layer, ""))
    out += [f"## {layer} · {title}", "", desc, "",
            "| # | 断言 | 出处 |", "|---|---|---|"]
    for i, (name, f, ln) in enumerate(rows, 1):
        out.append(f"| {i} | {name} | [`{f}:{ln}`]({f.split('/')[-1]}#L{ln}) |")
    out.append("")

out += ["---", "",
        f"共 **{total}** 条可求值断言，覆盖 {len(by_layer)} 层。", "",
        "⚠️ **「求值过」不等于「通过」。** 判官报三种结局:跑了通过 · 跑了失败 · "
        "**断言的对象不存在所以没求值**。第三种被折进第一种的话，"
        "一份空产物会被报成「全过」—— 这个坑本项目踩过（见 "
        "[badcases.md](badcases.md) 里判官自己的那几条）。"]

(ROOT / "judges.md").write_text("\n".join(out), encoding="utf-8")
print(f"✅ eval/judges.md · {total} 条断言 · {len(by_layer)} 层")
for layer in sorted(by_layer, key=lambda x: (x[:2], x)):
    print(f"   {layer:8s} {len(by_layer[layer]):3d} 条")
