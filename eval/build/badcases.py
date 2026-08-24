# -*- coding: utf-8 -*-
"""Badcase 台账的**唯一数据源**,渲染成 markdown 与 HTML 两份。

⚠️ 不要直接改 badcases.md / badcases.html —— 它们是这个文件生成的,改了会被覆盖。
   同一份事实存两处、然后各自漂移,是本项目第五类事故的形状。

用法:
    python3 eval/badcases.py            # 同时写 badcases.md 与 badcases.html
"""
import html
import pathlib

HERE = pathlib.Path(__file__).resolve().parents[1]      # eval/build/ → eval/

# ── 台账 ─────────────────────────────────────────────────────────────
# caught: 判官在**当时**抓到没有。修好判官之后也不要改这个字段 ——
#         它记的是「这条缺陷被发现时,判官处于什么状态」,是判官盲区的证据,不是当前状态。
# fixed:  缺陷本身修了没有。两个字段说的是两件事。

RUN = "C-1"
ROUND_OF = {
    "R3": "第 3 轮 · C-single 回归 ·「盯一下 NVDA」· 2026-08-23 · nvda-watch v1.0.1",  # 每条缺陷是哪一轮发现的
    "R1": "第 1 轮 · C-single ·「盯一下 NVDA」· 2026-08-23 · nvda-watch",
    "R2": "第 2 轮 · D-crypto ·「盯下 BTC、SOL、DOGE，有异动提醒我」· 2026-08-23 · btc-sol-doge-watch",
    "线上": "acct1 上正在跑的 portfolio-watch（15 只真实持仓，linked）",
    "审计": "改 R1 缺陷时顺着代码查出来的，不是某一轮真跑报的",
}
RUN_FULL = "案例 C-single 第 1 次真跑 · 2026-08-23 · acct2 mmgh5 · playbook `nvda-watch`"

GROUPS = [
    {
        "key": "render",
        "title": "一个异常吃掉整页",
        "lead": "最高优先级。数据全在文件里,页面上一片空白 —— "
                "而排查会被症状带去错误的一层。",
    },
    {
        "key": "placeholder",
        "title": "init.js 埋了占位符,此后没有任何 producer 填过",
        "lead": "同一个形状重复六次:字段在契约里、在文件里,值是 `[]` 或 `0` 或 `null`,"
                "页面照着渲染出空白 —— **而空白和「上游没给数」长得一模一样**。",
    },
    {
        "key": "wrongquantity",
        "title": "页面从错误的量推结论",
        "lead": "第六类:核对的量与以为在核对的量不是一个。"
                "修掉数据之后症状消失,而机制还在。",
    },
    {
        "key": "never",
        "title": "从来没有人取的数据",
        "lead": "不是算错,是这条链路压根不存在。",
    },
    {
        "key": "baseline",
        "title": "两本账用的不是同一把尺子",
        "lead": "同一个 skill 建出的两个 playbook，对同一天同一根 bar 给出不同判断。"
                "**引擎一个数都没算错** —— 基线不一样长。"
                "而可复用性正是这份作业的核心判据。",
    },
    {
        "key": "pipeline",
        "title": "四个 producer 在同一份文件上互相覆盖",
        "lead": "每个都是「开头读一份、跑一整段网络请求、最后写回」。"
                "窗口里别人写进去的东西被陈旧副本静默抹掉，"
                "**而症状指向被抹掉的那一方没跑过**。",
    },
    {
        "key": "selfcheck",
        "title": "检查跑了、通过了，而它没在查你以为的东西",
        "lead": "比缺陷本身更麻烦的一类：绿灯是假的。"
                "有的从一开始就没把对象收进来，有的数的是检查器自己写的字。",
    },
    {
        "key": "copy",
        "title": "数是对的，话说错了",
        "lead": "字段没算错，页面上那句话指的不是它。"
                "时区、单位、时刻的归属 —— 读者只能按字面理解。",
    },
    {
        "key": "accepted",
        "title": "可接受,但首轮体验差",
        "lead": "行为是刻意设计的,不是缺陷 —— 只是第一次打开的人看不出这一点。",
    },
]

CASES = [
    dict(
        id="BC60", group="copy", sev="high", owner="页面",
        caught=False, fixed="已修 · v1.4.0 已发布",
        title="持仓表那一行的 no push 只读 PV1，盘中被封的标的完全看不出来",
        field="holdings 行徽标", actual="SOL 行干净，卡片却标着 no push",
        expect="行上写明是哪条规则不推", onpage="用户扫表格正是为了知道哪几只不会响",
        cause="行徽标判的是 `grades.PV1.maxDelivery !== 'L1'`，"
              "卡片判的是 `finding.delivery.level !== 'L1'` —— **两枚徽标读的不是同一个东西**。"
              "SOL 的 PV1 是 L1、PV5 被封，于是行上没有、卡上有。",
        why="⚠️ **是用户对着页面看出来的。** 持仓表那一行是「这只票会不会响」的唯一集中处，"
            "而它只替两条价量规则里的一条说话。\n\n"
            "⚠️ 还有一层:`deliveryOf` 里**评级缺失直接封 L2**，"
            "而行徽标只在 `maxDelivery && !== 'L1'` 时才显示 —— "
            "「L1，会推」和「从没评级过，永远不推」两种相反的状态**都不显示徽标**。\n\n"
            "⚠️ 范围**不能**跟表格上方那个 daily|intraday 切换走 —— "
            "那个切换管的是右侧读数列，徽标在左侧标的格里，两者不是一回事;"
            "卡片上更没有那个切换。所以范围写进徽标本身。",
        fix=["行徽标逐信号判（ETF 只有 PV1），文案带范围:`no push · daily` / `no push · intraday`",
             "两条都封时**合成一枚** `no push · price-volume` —— 并排两枚说的是同一件事，"
             "而标的格没有那个宽度",
             "⚠️ 合成的那一枚**不能写光秃秃的 `no push`**:用户线在 `deliveryOf` 里是豁免的，"
             "这只票照样会为你自己划的线响。精确到「价量告警」，不是「这只票」",
             "缺失评级给单独的浮窗:「从没被评级过 —— 没有评级不等于通过，我们向外失败」",
             "卡片的范围从 finding 自己的 `unit` 来（session/bar/line）"],
        assertion="⚠️ 查不了 —— 判据是「两处徽标说的是不是同一件事」，而它们在两段互不相干的代码里。",
        verified="acct1 线上 v1.4.0:美股五只 `NO PUSH · INTRADAY`，RIVN/SOFI 合成 "
                 "`NO PUSH · PRICE-VOLUME`，**加密三只干净**（补上 PV5 评级后拿到 L1）。",
    ),
    dict(
        id="BC61", group="placeholder", sev="critical", owner="数据",
        caught=False, fixed="已修 · v1.4.0 已发布",
        title="本地管线不算 PV5 评级，于是 demo 上所有盘中告警都不推手机",
        field="baselines[].signalGrades.PV5", actual="每只都缺", expect="逐标的评级",
        onpage="看不出来 —— 只有恰好触发的那一条卡片会露出 no push",
        cause="`pipeline/build_grades.py` 只算 PV1。而 `deliveryOf` 里 "
              "`const g = gr ? gr.maxDelivery : \"L2\"` —— **缺失直接封 L2**。",
        why="⚠️ **缺一个字段的后果是整族信号静默失效。** "
            "SKILL.md 自己写着「一个没有 grade 的标的永远不会推」，"
            "而本地管线灌进 acct1 的那份 baselines 从来没有 PV5 那一格。\n\n"
            "⚠️ skill 自己的 `init.js` 是算的 —— **两边不一致就是两把尺子**，"
            "跟 [[BC35]] 同源（那次是窗口长度，这次是有没有算）。",
        fix=["`build_grades.py` 补 PV5，判据与 PV1 完全同一套（区间下界 > 1.0 且独立块 ≥ 5），"
             "只是跑在 bar 上:W/F 单位换成「根」、阈值换 θ_bar、触发查同槽位基线",
             "ETF 直接 continue —— 它不启用 PV5，**没有评级是正确的缺席**，"
             "不能和「算不出」混在一个名单里"],
        assertion="`deliveryOf` 的失败关闭方向是对的（缺失就封），"
                  "所以真正要防的是「该算的没算」——那只能靠两边口径对齐。",
        verified="加密 BTC/SOL/DOGE **L1 usable**（区间下界 1.838 / 2.528 / 2.283，块 19/13/15）;"
                 "美股七只 L2 —— RTH 窗口里只触发 2–6 根，样本确实不足，"
                 "`insufficient_sample` 是诚实结论不是缺陷。mock 296 条断言仍全过。",
    ),
    dict(
        id="BC59", group="copy", sev="high", owner="页面",
        caught=False, fixed="已修",
        title="我给一个没有窗口的计数加了一句精确的窗口标签",
        field="alerts today", actual="4（含两条 8-21 的）", expect="0，另说明 5 条来自更早批次",
        onpage="副标题写「since Aug 22 20:00 ET」，卡片列着 Aug 21 20:00 ET",
        cause="`ACTIVE` 是**全部 findings 按时间排序，没有任何日期过滤**。"
              "[[BC37]] 我只加了「since … ET」这句标签，没有加对应的过滤。",
        why="⚠️ **把一句含糊的「today」换成一句精确的假话，比原来更糟。** "
            "原来读者只是不知道 today 指什么；现在他被告知了一个具体区间，"
            "而屏幕上就摆着不属于那个区间的卡。**是用户一眼看出来的，不是我的断言。**\n\n"
            "⚠️ 过期的 finding 不该静默消失 —— 「今天很安静」和「有东西被我筛掉了」必须分得开。"
            "而且它们的存在本身是个**诊断**:日线每轮整族替换 PV1、盘中整族替换 PV5，"
            "上一天的还在，就说明那个 producer 这一轮没跑。",
        fix=["`inWindow()` 真的按 UTC 日零点过滤，两处 `fresh` 计数都用它",
             "窗口外且非持续态的单独数出来，副标题里说「N 条来自更早的批次，未计入 —— "
             "某个 producer 自那之后没跑过」",
             "⚠️ 持续态（`novelty===0`）不受窗口约束 —— 它按定义就来自更早，"
             "自己带 since 日期，那一组本来就没进计数"],
        assertion="⚠️ 没有断言查得了它 —— 判据是「标签说的区间和被计数的集合是不是同一个」，"
                  "而两者一个在文案里一个在过滤器里。这类只能靠人看，或者靠用户。",
        verified="拿 acct1 那份数据把 `generatedAt` 推到 8-23 21:45Z 复现:"
                 "修之前 4 条（含两条 8-21 的日线告警）;"
                 "修之后 **0 条**，副标题读作「since Aug 22 20:00 ET · 3 still true from earlier · "
                 "5 from an earlier batch, not counted — a producer has not run since」。",
    ),
    dict(
        id="BC58", group="selfcheck", sev="critical", owner="eval",
        caught=False, fixed="已修 · 生产已还原",
        title="在主账号上跑 eval，agent 用了同一个名字，把生产那本原地覆盖了",
        symptom="acct2 额度用完切到主账号跑 K 的回归。"
                "agent 把 playbook 发布成 `portfolio-watch` —— **正是生产那本的名字**。"
                "15 只的账本被 9 只覆盖，`totalValue` 从 158,275 变成 106,507。",
        cause="主账号上只能放一本 playbook，agent 于是复用了已有的那个名字。",
        why="⚠️ **我在起跑前专门推理过这件事，而且推错了。** 我说的是"
            "「拆资源按 `args.root` 匹配，生产那本 root 对不上，不会被碰」——"
            "那句话只覆盖了 **teardown**，没覆盖 **agent 起名字**。\n\n"
            "两个动作的风险完全不同:teardown 是我的代码，我读过它;"
            "命名是 agent 的自由，我没有任何东西在约束它。"
            "**我把「我检查过的那一半」当成了整体。**\n\n"
            "⚠️ 更该记的是:cronjob **没有**被新建，还是原来那四个（id 与创建时间都对）——"
            "也就是说覆盖是无声的，账号上看不出发生过什么，"
            "只有比对 `portfolio.json` 才看得见。",
        fix=["collect 的闸门从「主账号一律拒绝」改成「收集照做，但 **teardown 禁用**」——"
             "生产那四个 cronjob 的 root 恰好等于本轮 root，`args.root` 那道判据在这里失效",
             "起跑前把整套还原素材备齐（本轮备了:portfolio · series · findings · meta 的当日快照 "
             "+ mock 的 baselines/signals/news/market/symbols + 手抄的 alerts.json）",
             "⚠️ 还原时**不要混批次**:第一次我拿当日快照的 findings 配 mock 的 baselines，"
             "`historicalTriggers` 与 `alertHistory` 四处对不上、一条投递上限也对不上。"
             "最后整套从 mock 重灌，296 条断言才全过"],
        assertion="⚠️ 没有断言拦得住 —— 判据是「agent 会不会选这个名字」，"
                  "而那在产物之外。真正的护栏只有:**别在生产账号上跑 eval**，"
                  "非跑不可就先备齐还原素材。",
        verified="acct1 已还原:15 只 · 15 份基线 · 502 点净值 · 原 userLines 与 enabled · "
                 "296 条断言全过。多出来的 KO.json 也清掉了。",
    ),
    dict(
        id="BC56", group="never", sev="critical", owner="脚本",
        caught=False, fixed="已修 · 造真触发验过",
        title="PV1 一旦真触发就把整个日线 producer 打挂 —— `move is not defined`",
        field="findings[].context", actual="ReferenceError，整轮 abort",
        expect="一条 PV1 finding", onpage="那一天所有日线产出全部消失",
        cause="`findings.push({...})` 里有三处裸的 `move`，作用域里没有这个变量 —— "
              "应该是 `rdg.move`。**这段代码只在 `fired` 为真时执行。**",
        why="⚠️ **它一直是坏的，而十六轮真跑没有一轮碰到过** —— "
            "因为没有一只标的真的触发过 PV1。分支从没被走过，所以从没报过错。\n\n"
            "⚠️ 后果不是「少一条告警」。`feed.run()` 吞异常，整个日线 producer 在那一行 abort，"
            "**它后面的 scan、portfolio、series、meta 全都不写** —— "
            "也就是说 **PV1 真触发的那一天，页面反而什么都没有**。\n"
            "而 PV1 是这套东西里唯一通过回测判据的告警信号。\n\n"
            "⚠️ 是「把阈值调到必然触发」这个动作把它逼出来的。"
            "任何只在罕见分支里的代码，**不造一次触发就等于没测过** —— "
            "而这条分支恰好是整个产品的主线。",
        fix=["三处 `move` → `rdg.move`",
             "⚠️ 更该记的是**怎么发现的**:把 θ 临时压到 0.05 让九只全触发，"
             "跑完再还原。罕见分支要用这种方式主动走一遍"],
        assertion="⚠️ 桩环境走不到 —— `producer.js` 在桩里只写得出 `data/meta.json`。"
                  "只能靠「造触发」这一招。",
        verified="θ 压到 0.05 后九只全 triggered:修之前 `ReferenceError: move is not defined` "
                 "整轮 failed;修之后 9 条 PV1 finding 全部产出，scan 九行读数俱在。还原后回到 quiet。",
    ),
    dict(
        id="BC57", group="never", sev="high", owner="脚本",
        caught=False, fixed="已修 · 开关两个方向都验过",
        title="设置面板写着「可以关掉的信号」，而六个开关里三个没接线",
        field="config/alerts.json enabled", actual="只有 US1–3 被读",
        expect="列出来的都关得掉", onpage="关掉 PV1 / PV5 / EV4 什么也不会发生",
        cause="全仓库只有 `userlines.js` 读 `enabled`，而它只管 US1/US2/US3。"
              "`producer.js`（PV1）· `producer-intraday.js`（PV5）· "
              "`producer-context.js`（EV4）三处一次都没查过。",
        why="⚠️ 面板那段注释自己就写着「面板在对读者撒谎」——"
            "指的是把没在算的显示成 on。**这里是同一句谎话的另一面**:"
            "显示成可关，而关不掉。\n\n"
            "⚠️ 顺带澄清一件我差点报错的事:EV1 是 `record` 型、DR1 是 `display` 型，"
            "两个 `pushable: false`。**skill 不把它们写进 `enabled` 是对的** —— "
            "给不会响的东西放开关才是错的。真正错的是 acct1 那份手写数据里有它们。",
        fix=["三个 producer 各加一道 `sigOn(id)`",
             "⚠️ 拦的位置是**产 finding**，不是**算读数**:"
             "「关掉」的意思是别再为它告警，持仓表那一行的读数照旧要出 —— "
             "它是引擎跑过的唯一证据",
             "配置要在产 finding 之前读 —— 原来 `cfg` 在 280/331 行才读，"
             "而 PV5/PV1 在 167/180 行就 push 了"],
        assertion="⚠️ 没有断言能查它 —— 要造一次真触发再开关各跑一遍。",
        verified="θ 压到 0.05 造出九次 PV1 触发后:\n"
                 "PV1 开 → `findings` 九条 PV1 + 一条 US3;\n"
                 "PV1 关 → 九条消失，只剩 US3，而 `scan` 九行仍然 `triggered`。\n"
                 "两个方向都验过，读数没被连坐。",
    ),
    dict(
        id="BC54", group="wrongquantity", sev="high", owner="脚本",
        caught=False, fixed="已修",
        title="「本周财报」把下周一也算进来了 —— end_time 是闭区间",
        field="market.earningsWeek", actual="6 天（含 2026-08-24）", expect="本周一至本周日",
        onpage="柱状图多出第六根，本周的财报量看起来比实际重",
        cause="`end_time = w0 + 7*86400` 正好是**下周一 00:00**，而端点的区间是闭的。"
              "该到本周日 23:59:59，也就是 `w0 + 7*86400 - 1`。",
        why="⚠️ 差一秒，多一天，而多出来的那天是**下一周的第一个交易日** —— "
            "美股周一发财报的公司不少，实测那天 41 家。\n\n"
            "这类错在页面上不报错、不缺字段，只是那根柱子比别人矮一点站在最右边，"
            "**看起来像本周的一部分**。是平台的巡检机器人先看出来的，不是我的断言。",
        fix=["`end_time` 改 `w0 + 7*86400 - 1`",
             "output-schema 写明「到本周日 23:59:59 为止」与闭区间这件事"],
        assertion="⚠️ 我没有断言在查这个 —— 契约只说了字段形状，没说窗口边界。"
                  "现在写进 schema 了，但仍然只有人（或巡检机器人）看得出来。",
    ),
    dict(
        id="BC55", group="wrongquantity", sev="high", owner="页面",
        caught=False, fixed="已修",
        title="财报日总数把「时间未知」那一列整个丢了，每天少 2–12 家",
        field="earningsWeek[].unknown", actual="总数 = beforeOpen + afterClose",
        expect="总数 = 三列之和", onpage="周五印 10，实际 15",
        cause="producer 分三类（bmo · amc · 时间未知），页面第 3802 行"
              "把总数算成 `(beforeOpen||0)+(afterClose||0)` —— **第三列没进任何计算，也没画出来**。",
        why="⚠️ **producer 那边分三类是对的**，注释写得很清楚:"
            "「盘前」与「不知道盘前还是盘后」是两件事，并进任一侧都是替它做判断。"
            "而消费方的模型只有两类，于是那一整列在页面上蒸发。\n\n"
            "⚠️ 偏差有方向:总是**偏低**，而偏低恰好让「本周财报压力」看起来更轻 —— "
            "这张卡存在的意义正是让人看出压力。\n\n"
            "⚠️ 页面上那段注释还写着「总数是这两半之和」。"
            "**注释与 producer 分叉了，而注释是我自己写的** —— "
            "它当时是对的，producer 后来分成三类，注释没跟着改（第八类:断言的主语变了）。\n\n"
            "⚠️ 还有一层:producer 原来 `unknown` 为 0 时**省掉这个键**。"
            "省掉之后消费方看不出「这天没有时间未知的」和「这份数据没有这个概念」的区别。"
            "**字段在不在，本身就是一句话。**",
        fix=["页面总数含三列;柱子画第三段（条纹，不是第三种颜色 —— "
             "它不是第三个时段，是「不知道是哪个时段」）;图例按需出第三项",
             "producer 永远带 `unknown` 这一列，哪怕是 0",
             "output-schema 写明三列都必填，并说清省掉零值的后果",
             "mock 的手写 fixture 补上这一列，否则页面走 `||0` 又静默为 0"],
        assertion="⚠️ 同样没有断言在查 —— 这是「两个数都对、加起来的口径不对」，"
                  "契约检查只看字段在不在。写进 schema 之后至少下一个读的人看得到。",
        verified="mock 上重新渲染:周一至周五 24 / 36 / 46 / 53 / **15**（原来 15 印成 10），"
                 "三段柱、三项图例（after close · before open · time not given），"
                 "tooltip 读作 `10 + 0 + 5 ?`。L4 12 条全过。",
    ),
    dict(
        id="BC52", group="selfcheck", sev="high", owner="检查器 + 数据",
        caught=False, fixed="已修",
        title="gap 文案检查查了两个方向，漏的正是用户真会看到的那一个",
        symptom="acct1 **线上这一刻**的 `meta.gaps` 里有 `attribution_time_zone_leak`，"
                "而它没有文案 —— 方法页印的是这个裸 id。"
                "outpool 那份 demo 里还有两条同样的:"
                "`unvalidated_asset_class_etf` 与 `insufficient_baseline_new_listings`。",
        cause="前两个方向扫的都是**脚本**（发出来的有没有文案 · 有文案的发不发得出）。"
              "而这三条是**手写进数据的** —— 一条是 eval 的已知失败样本，"
              "两条是 `build_outpool.py` 用了带下划线后缀的名字"
              "（页面按第一个 `:` 之前查表，`..._etf` 一个都查不到）。",
        why="⚠️ **两个方向都绿，而用户看到的是第三个。** "
            "判据应该是**产物里出现过什么**，不是代码里写了什么 —— "
            "手写的 fixture、别的脚本生成的数据，都绕过前两道。\n\n"
            "⚠️ 补上第三个方向的时候我又犯了同一类错:"
            "文件里 json 叫 `_json` 而我写了 `json.load`，NameError 被 `except: pass` 吞掉，"
            "检查印出「**0 种 gap 都有文案**」—— **零个也叫全过**。"
            "现在不吞异常，并且「一个文件都没读到」和「读到了但零条」各自直接失败。",
        fix=["检查器补第三个方向:扫 `mock/data*/meta.json` 里真实出现的 gap id",
             "`attribution_time_zone_leak` 补文案（它是真话:那句解释的时刻是拼出来的，"
             "可能差几个小时；读数本身不受影响）",
             "`build_outpool.py` 改用 canonical 名 + 冒号负载，"
             "不要 `..._etf` 这种同概念第二拼法"],
        assertion="三个方向合起来:脚本发的都有文案 · 有文案的都发得出 · **产物里有的都有文案**。"
                  "第三个方向在读不到文件或读到零条时直接失败，不再静默通过。",
        verified="acct1 线上那条现在有文案;outpool 重新生成后 gaps 变成 "
                 "`unvalidated_asset_class:3,2.0` · `insufficient_baseline:CHYM,FIG,KLAR` · "
                 "`no_intraday_for_this_book`，三条全部查得到表。检查器 23 条全绿。",
    ),
    dict(
        id="BC53", group="selfcheck", sev="med", owner="数据",
        caught=False, fixed="已修",
        title="生成器和它生成的数据早就分叉了，因为从来没人重跑过它",
        symptom="重跑 `build_outpool.py` 之后契约检查当场报错:"
                "`2025-10-15:GLD:PV1` 少了 `delivery`。"
                "而 committed 的 fixture 里一直有 `{level:L2, cappedBy:symbol_grade}`。",
        cause="脚本不写 `delivery`，也不填 `signalGrades` —— "
              "committed 的那份是后来手补的。数据被改过，生成它的脚本没跟着改。",
        why="⚠️ **这条只有在重跑生成器的那一刻才会暴露**，而重跑的理由是别的事"
            "（我在改 gap 名字）。在那之前，检查器天天对着手补过的数据说全过。\n\n"
            "⚠️ 补完 `delivery` 又立刻挂了两条:`cappedBy: symbol_grade` 指向的那一处"
            "在 `signalGrades` 里是空的 —— **契约要求 cappedBy 指向的那一处确实等于 level**。"
            "手补数据时只补了果，没补因。ETF 的阈值是兜底反解的，"
            "证据等级本来就该封顶 L2，把它写进 `signalGrades` 才是真的分档。",
        fix=["`build_outpool.py` 写 `delivery`，并给 ETF 一个真的 `signalGrades.PV1.maxDelivery = L2`",
             "⚠️ 「fixture 手补过」这件事本身要当成信号 —— 下次改数据先问生成器改了没"],
        assertion="契约的 finding 键集合检查 + 投递层三处上限取 max 的检查，"
                  "两条都是这次重跑才第一次真的作用在这份 fixture 上。",
    ),
    dict(
        id="BC51", group="pipeline", sev="critical", owner="脚本",
        caught=True, fixed="已修 · 直接验过",
        title="`meta.json` 上有和 findings 一模一样的读-改-写竞争，而我只修了 findings",
        field="meta.freshness", actual="缺 news · earningsCalendar",
        expect="五个键齐", onpage="方法页说上下文 producer 从没跑过",
        cause="四个 producer 都是「开头读 meta、跑一整段取数、最后整体写回」。"
              "上下文写进去的 `news` / `earningsCalendar` 被后一个 producer "
              "用更早读到的副本盖掉。",
        why="⚠️ **[[BC42]] 的同胞，而我修 BC42 时没想到这份文件。** "
            "findings.json 有三个写者，meta.json 有**四个** —— 更挤，"
            "我却只给前者加了重读。\n\n"
            "识别法本来就在手边:上一条的结论是「**多个进程改同一份文件**就要压窗口」，"
            "而不是「findings.json 要压窗口」。**我把结论记成了它的一个实例。**\n\n"
            "症状照旧指向错误的一方:产物上看是上下文 producer 从没跑过，"
            "而单独再跑一次它，两个键立刻就在。",
        fix=["`lib.commitMeta(rd, wr, local, owned)`:写前重读，"
             "只把自己认领的键盖上去",
             "认领分四类 —— 整键（attributionRuns）· freshness 下的哪几个 · "
             "并进 producedSignals 的信号 · 自己管的 gap 前缀（含删除）",
             "四个 producer 全部改用",
             "⚠️ `producer-market.js` 原本不 require lib —— 冒烟测试当场 "
             "`ReferenceError: L is not defined`。这次是检查器先抓到的"],
        assertion="冒烟测试跑四个 producer 并数各自写了哪几个文件。",
        verified="在 R13 的 playbook 上先把 `news` 与 `earningsCalendar` 从 freshness 里抹掉，"
                 "再依次跑四个 producer:五个键全部回来，"
                 "`producedSignals` 累积到 `[PV1, US1, US2, US3, PV5, EV1, EV4]` —— "
                 "三个 producer 各自声明的都在，没有互相覆盖。",
    ),
    dict(
        id="BC50", group="placeholder", sev="high", owner="SKILL.md",
        caught=False, fixed="已修（待 R13 验）",
        title="规格让 agent 填 logo，却没给能用的 URL —— 四轮下来每一只都是 null",
        field="holdings[].logo", actual="null（每一轮、每一只）",
        expect="股票与新股给真图标，ETF 与查不到的留空",
        onpage="每一行都画字母块",
        cause="SKILL.md §1.3 写「`theme` 和 `logo` 来自**你**，没有端点」，"
              "然后说「你知道 NVDA 是什么，填它跟填 `name` 是一回事」—— "
              "**但没给 URL pattern**。agent 拿不出能打开的地址，只能留空。",
        why="⚠️ **这不是知识，是三条不同规则加一个陷阱的查表。** 实测:\n\n"
            "美股与新股 `…/arrays-public-assets/logos/<SYM>.svg` —— "
            "NVDA · AAPL · MSFT · TSLA · AMD · KLAR · CHYM 全 200；\n"
            "**ETF 同一个 pattern 全 404** —— SPY · QQQ · GLD · TLT · XLE · IWM；\n"
            "加密要 CoinMarketCap 的数字 id，从代号推不出来。\n\n"
            "所以照 pattern 硬填会给每一行 ETF 配一张**碎图** —— "
            "**比字母块糟得多:字母块是设计，碎图是故障。**\n\n"
            "⚠️ 顺带发现本地 mock 一直就是这么干的:`book.py` 按 `US + OT` 拼，"
            "五只 ETF 各配了一张 404。规格里那句「你知道 NVDA 是什么」"
            "让这件机械的事看起来像判断题，于是两边各错各的。",
        fix=["`init.js` 先探再填:按类别拼候选 URL、HEAD 一次、只留 200 的。"
             "加密带一张 25 个代号的 CMC id 表",
             "一只都没解析出来时发 `logos_unavailable` gap —— "
             "「设定好的兜底」和「碎了」要在页面上分得开",
             "SKILL.md 改成「**别手填，init.js 会解析**」，只有 `theme` 还归 agent",
             "`pipeline/book.py` 的 LOGO 去掉 `OT`，mock 不再配碎图"],
        assertion="⚠️ 断言只能查「不是每一只都 null」，查不了「图标对不对」—— "
                  "后者要人看。真正挡住碎图的是那次 HEAD。",
    ),
    dict(
        id="BC49", group="never", sev="high", owner="SKILL.md",
        caught=True, fixed="已修（待回归验）",
        title="规格只写了「账户列表是空的」，没写「账户在但读不出来」",
        symptom="R10（A-mixed）:agent 查到一个已连接的 IBKR 模拟账户、授权已失效，"
                "规格里没有这一格。它外推到最近的分支（问用户），"
                "**动作对了**，但只跑了文档化链路三步中的第一步。",
        cause="§1.1 的取数链路表只列了 `accounts returns []` 一种失败态。"
              "「列出来了但 summary 读不出来」不在表上。",
        why="⚠️ **这条是 L5 判官挖出来的，不是断言。** 两轮拒绝它都判 pass，"
            "而在给 A-mixed 判 medium 的理由里指出:"
            "「授权已失效」这个诊断只有一次 `alva portfolio accounts` 支撑，"
            "agent 没拿 account-id 去打 `portfolio summary` 就命名了原因。\n\n"
            "后果是**给用户的话不可执行**:它说「请重新连接 IBKR 账户」，"
            "而没给账户 id、也没引端点自己的报错。用户手上要是连了三个账户，"
            "这句话等于没说。\n\n"
            "⚠️ 规格没写的分支，agent 会自己补 —— 补对了是运气，"
            "而**补的那一格从此不受任何检查约束**。",
        fix=["§1.1 的表补一行「账户列出来了但 summary 读不出来」",
             "要求先跑第二次调用再命名原因 —— 不跑就不知道是授权、是网络还是别的",
             "要求把账户 id 与端点原话交给用户:去修的是他们，"
             "转述一句「重新连接券商」在连了三个账户时不可执行"],
        assertion="⚠️ 代码查不了 —— 判据是 agent 跑了几次调用、说了什么。"
                  "这是 L5 的活，本轮由子 agent 判官读 transcript 得出。",
    ),
    dict(
        id="BC48", group="copy", sev="high", owner="SKILL.md",
        caught=False, fixed="已修（待回归验）",
        title="agent 把 SKILL.md 模板里的占位字母原样念给了用户",
        symptom="R11（H-probe · 40 只标的那一问）:"
                "「超过 30 个标的时，每天可能产生约 **N** 条提醒。"
                "……还是只监控按持仓权重排名前 **K** 只?」—— 字面的 N 和 K。",
        cause="SKILL.md §1.5 的追问表里那一行写着 "
              "`Watching all of them is roughly N alerts a day; watch the top K by weight instead?`。"
              "同一张表上一行的 `XXXX` **被正确替换成了 `NVDAA`** —— "
              "`XXXX` 一看就是槽位，而 `N` / `K` 读起来像正文。",
        why="⚠️ **不是 agent 不懂,是模板没把「这里要填」说清楚。** "
            "同一张表里两种写法，一种填了一种没填 —— 区别只在长得像不像槽位。\n\n"
            "更深一层:`N` 这个数**此时根本算不出来** —— 每天几条提醒取决于"
            "每只标的的基线，而基线要 init 跑完才有。"
            "模板承诺了一个当时拿不到的量，agent 只能要么编一个、要么念字母。"
            "**它选了念字母,已经是两害相权取轻的那个。**",
        fix=["那一行改成不含数字的说法:「超过这个数，手机大多数日子都会响」"
             "+ 一个具体默认值（权重最大的十只），不再留 N / K",
             "补一条通则:**说话之前把所有槽位填掉**;"
             "算不出来的数就不要承诺，用话说清楚会发生什么"],
        assertion="⚠️ 这条代码查不了 —— 它是 agent 说出口的话，不在产物里。"
                  "只能靠 L5 读 transcript，或者像这次一样人工读到。"
                  "顺带把 SKILL.md 里所有裸的单大写字母扫了一遍，只有这一处是用户可见的模板。",
    ),
    dict(
        id="BC47", group="selfcheck", sev="high", owner="判官",
        caught=False, fixed="已修 · R9 就是那一轮",
        title="「正确地拒绝」被记成失败，「没建」和「建了没跑完」挤在一句话里",
        cause="判官只有 ✓ / ✗ / – 三档，没有产物就落进 ✗；"
              "落定检查又假定「没有产物 = 还没跑完」，于是发「再等等」。",
        symptom="R9（`盯下 0700.HK`）:agent 探到端点返回 "
                "`400 stock symbol not found`，引 skill 自己的规则拒绝建一个全空的面板，"
                "并给出替代（美股 OTC `TCEHY`）。"
                "判官把它记成 **L0 ✗**，收集器还印「这几个 producer 还没落地，等下一轮重抓」。",
        why="⚠️ **两处都把一个已经完成且正确的结局说成了没做完或做砸了。**\n\n"
            "「不建一个全是空数据的面板」正是 SKILL.md 写死的规则之一。"
            "把它记成 ✗，等于让这条规则每生效一次就在报告里显示为一次退步 —— "
            "**而看报告的人会去『修』它**。\n\n"
            "收集器那句更具体地错:它说的是「再等等」，"
            "而这一轮根本没有 playbook，等多久都不会落地。"
            "「压根没建」和「建了还没跑完」是两种状态，挤进同一句提示就丢掉了区别。",
        fix=["collect 认第三种结局 `outcome: declined`，并把 agent 最后说的理由原样存进 manifest —— "
             "判「拒绝得对不对」要看那段，不是看有没有产物",
             "report 加 ⊘ 一档，与 ✗ 分开",
             "落定检查在没有产物时不发「再等等」"],
        assertion="⚠️ 判据是 **agent 说了什么**，不是产物在不在 —— "
                  "一次静默的、什么都没说的空跑仍然是 ✗。两者的产物目录长得一模一样。",
        verified="R9 现在在报告里是 ⊘，鼠标悬停能看到它拒绝的理由全文。"
                 "它确实去探了端点（transcript 里三次 `symbol=0700.HK`，"
                 "拿到 `INVALID_PARAMETER · stock symbol not found`），不是猜的。",
    ),
    dict(
        id="BC46", group="selfcheck", sev="critical", owner="脚本",
        caught=False, fixed="已修 · R8 直接验过",
        title="页面备好了 22 条「我不知道什么」的文案，skill 只发得出 13 条",
        symptom="R8:三只 ETF 跑在没人验证过的兜底阈值上，两只新股被高波降级 —— "
                "**页面一个字都没说**。`meta.gaps` 里只有一条与本账无关的加密备注。",
        cause="`unvalidated_asset_class` · `pv1_highvol_downgrade_undecided` · "
              "`attribution_daily_cap` · `m23_not_run` · `pv5_not_computed` · "
              "`no_intraday_for_this_book` · `earnings_next_out_of_calendar_window` "
              "八条 gap 有文案、有键表项，而**没有任何脚本发得出**。"
              "它们只在本地 `pipeline/` 里被发过 —— 那份数据喂的是 mock，不是 skill。",
        why="⚠️ **检查器只查一个方向。** 「发出来的都有文案」年年绿灯，"
            "而「有文案的都发得出」从来没人问过。\n\n"
            "gap 恰恰是这个产品**承认自己不知道什么**的地方。"
            "发不出来不是少了一句提示 —— 它让页面看起来像「这本账没有这些问题」。"
            "ETF 那条尤其要命:契约白纸黑字写着这类标的的证据等级不得显示为绿，"
            "而不发 gap 的话读者根本不知道该打折。\n\n"
            "⚠️ 修的过程里检测器又栽了两次:先是按 `gaps.push(` 的**形状**认，"
            "三元表达式和局部变量名全躲过去 —— **方向反了，会催我去加已经加过的代码**；"
            "改成扫所有字符串字面量之后又太宽，把 `attributed` `calendar` 都当成 gap。"
            "最后分开问:正向枚举发送点，反向对已知的 22 个键逐个做成员判断。",
        fix=["init 发 `unvalidated_asset_class:<n>,<θv>` · "
             "`pv1_highvol_downgrade_undecided` · `m23_not_run` · "
             "`pv5_not_computed` / `no_intraday_for_this_book`（后两者要分开:"
             "「这本账没有盘中」是账本构成决定的，「这一轮没算」是出了状况）",
             "盘中发 `attribution_daily_cap:<cap>`，并且第二天要撕掉",
             "上下文发 `earnings_next_out_of_calendar_window`（没有美股就不发 —— "
             "那是另一种空）",
             "检查器补反方向，界面自判的键走白名单并写明理由"],
        assertion="`check_consistency.py`「有文案但没有任何脚本发得出的 gap」。"
                  "`m23_not_run` 名字像欠条其实是基线的持久事实，给了例外并写清理由 —— "
                  "比为了让检查器闭嘴去加一个假的 delete 好。",
        verified="R8 重跑 init + 四个 producer:"
                 "`gaps` 从 `[crypto_market_totals_unavailable]` 变成 "
                 "`[unvalidated_asset_class:3,2 · pv1_highvol_downgrade_undecided · "
                 "crypto_market_totals_unavailable]`。"
                 "`pv5_not_computed` 正确地没有发 —— 三只新股确实算出了槽位基线。"
                 "L0–L3 63 条全过，L4 12 条全过。",
    ),
    dict(
        id="BC45", group="placeholder", sev="critical", owner="脚本",
        caught=True, fixed="已修 · R7 直接验过",
        title="净值曲线整条路从没被走过 —— `series.points` 是空数组",
        field="series.points", actual="[]", expect="回推 345 点",
        onpage="组合净值图整块空白；`todayPnl` 与 `fromHigh` 两格破折号",
        cause="`init.js` 写 `{points: [], benchmark: null, high: null}` 占位，"
              "**没有任何 producer 填过它**。`basis` / `basisNote` 两个契约必填字段也不存在。",
        why="⚠️ **这是 init 埋占位符的第七次**（[[BC2]] kline · [[BC3]] spark …），"
            "但前六次都在此前的轮次里暴露过，这一条没有 —— "
            "**因为在 R7 之前没有一轮 query 带持仓**。\n\n"
            "没连账户时 `linked:false`，净值那一整块本来就该空，"
            "断言走「对象不存在」分支不求值。于是这条路**在六轮里一次都没被执行过**，"
            "而它是有持仓用户看到的第一屏。\n\n"
            "⚠️ 教训不在这个 bug 本身，在**覆盖的形状**:"
            "案例集里 8 个 query 只有 1 个带持仓，而带持仓才是主场景。"
            "断言数会说话 —— R5 求值 19 条、R6 52 条、R7 **77 条**。",
        fix=["`init.js` 按**当前股数不变**回推净值:日期轴取各标的 kline 的交集"
             "（混合账本里加密有周末而美股没有，取并集会让周末缺一半持仓，"
             "净值凭空掉一块，看起来像回撤）",
             "照契约自报家门:`basis:\"backcast\"` · `basisNote` · `nav_series_backcast` gap",
             "`benchmark` 与净值同一条日期轴，含加密时 `coverage:\"us_equity_only\"`",
             "`producer.js` 每个交易日把今天这一点接上去（按日期去重，同一天重跑覆盖），"
             "并从这条曲线读 `fromHigh` 与 `todayPnl` —— 另算一份必然对不上",
             "`fromHigh` 第三个键是 `sessionsAgo`（交易日个数），不是 `at`"],
        assertion="L2「连了账户则净值曲线非空」—— 这条断言一直在，"
                  "只是在 R7 之前从没有一轮走到过它。",
        verified="R7 真跑（I-holdings 指名模式，5 只 + 3000 现金）:\n"
                 "`points` 345 → 日线接上后 346 · `basis: backcast` · "
                 "`high {2025-10-08, 53949.87}` · benchmark SPY 345 点 `us_equity_only`；\n"
                 "`kpi.todayPnl {-147.07, -0.0032}` · `fromHigh {-0.1562, 53949.87, 219 sessions}`；\n"
                 "L0–L3 **47 条全过**，L4 渲染 **12 条全过**，四个 tab 21 张卡零空卡。\n"
                 "页面上净值图读作「60 sessions · First 46.81K 2026-05-29 · Last 45.52K 2026-08-22」。",
    ),
    dict(
        id="BC44", group="pipeline", sev="high", owner="脚本",
        caught=True, fixed="已修 · R6 直接验过",
        title="`scan` 这一行有两个主人，日线整体覆盖时把盘中那一格抹成 null",
        field="scan[].bar", actual="null（三只全是）", expect='{"state":"triggered", …}',
        onpage="持仓表「盘中」那一栏整列破折号",
        cause="日线写会话级读数并**整体替换** `scan`，盘中往同一行里塞 `bar`。"
              "日线后跑就把 `bar` 一起冲掉。",
        why="⚠️ **症状指向盘中 producer 没跑**，而它跑过，"
            "而且同一份文件里就躺着它产出的 PV5 finding —— "
            "「一格空着」和「那一层没运行」在页面上分不开。\n\n"
            "⚠️ **改的过程里我自己又把它复现了一遍，原因换了一个:**\n"
            "上一条（[[BC42]]）的修法是「写前重读」，而盘中把 `bar` 写在"
            "开头读的那份陈旧副本上 —— 重读一次全没了。"
            "两次的产物一模一样（`bar: null` + PV5 finding 还在），"
            "**同一个症状对应两个完全不同的根因**。",
        fix=["`commitFindings` 加 `scanBar` 参数:按 symbol 把这一格贴到**重读后**的行上",
             "日线那一侧反过来:`patch.scan` 里没带 `bar` 的行，从重读的副本里接过来",
             "谁拥有哪个字段要写下来 —— 整行归日线，`bar` 这一格归盘中"],
        assertion="L3「PV5 触发的标的，对应粒度的 scan 应为 triggered」。",
        verified="R6 真跑，三个 producer 依次执行:\n"
                 "盘中 → `bar {BTC:quiet, SOL:triggered, DOGE:quiet}`；\n"
                 "日线 → `bar` 三格全在，`scan` 3 行，`asOf` 保持 00:00Z；\n"
                 "上下文 → 全部不变。\n"
                 "**修之前这一串跑完 `scan` 会变成空数组。** 断言 34 条全过。",
    ),
    dict(
        id="BC43", group="selfcheck", sev="high", owner="判官",
        caught=False, fixed="已修",
        title="台账页面声称 41 条，实际只渲染了 34 条",
        symptom="新加的 BC35–42 里有 7 条在 `badcases.html` 与 `badcases.md` 里"
                "**一条都找不到**，而页脚照常印「41 条」。",
        cause="页面按 `GROUPS` 逐组筛 `CASES`。四个新组名"
              "（baseline · pipeline · selfcheck · copy）不在 `GROUPS` 里，"
              "于是那些条目不属于任何一组，一组都不渲染。"
              "而顶部那句「共 N 条」数的是 `CASES` 本身。",
        why="⚠️ **两个数字之间没有任何东西在比。** 计数走一条路（`len(CASES)`），"
            "渲染走另一条（逐组筛），谁也不知道对方少了什么。\n\n"
            "这条特别难看的地方在于:**这是记录缺陷的那个页面自己在漏记缺陷**，"
            "而且它漏的正是刚发现的那一批。"
            "「跑了 · 通过了 · 而它没在查你以为的东西」在这里退化成"
            "「印了 · 数对了 · 而内容不在页面上」。",
        fix=["补上四个分组",
             "加闸门:`{c['group'] for c in CASES} - {g['key'] for g in GROUPS}` 非空就退出",
             "顺带修一个 `sev=\"medium\"` —— `SEV_LABEL` 里的键是 `med`，"
             "整个脚本 KeyError 崩掉，而崩之前 html 已经写出去了旧的一版"],
        assertion="孤儿分组闸门。做过破坏性测试:把一条改成 `group=\"nosuchgroup\"`，"
                  "脚本退出码 1 并点名。\n"
                  "⚠️ 第一次破坏性测试用 `sed -i '' '0,/…/s//…/'` **静默没生效**，"
                  "看起来像「闸门没响」。改用带计数断言的替换才真的注入进去 —— "
                  "**破坏性测试本身也要先确认它真的破坏了**。",
    ),
    dict(
        id="BC42", group="pipeline", sev="critical", owner="脚本",
        caught=True, fixed="已修 · R6 直接验过",
        title="三个 producer 读-改-写同一份 findings.json，同分钟跑的会互相抹掉",
        symptom="R5:1 只持仓，`scan` 是空数组，`asOf` 停在 init 的时刻。"
                "而日线明明跑过 —— `producedSignals` 里有 PV1、US1–3。",
        cause="每个 producer 都是**开头读一份、跑一整段网络请求、最后写回**。"
              "`producer-context.js` 第 43 行读 `findings.json`，第 262 行写回，"
              "中间隔着新闻 · 财报 · 内部人 · 资金费率四类取数。"
              "日线 12:18 写了 `scan` 与自己的 `asOf`，上下文 12:18:20 用 200 行之前"
              "读到的副本写回 —— 两个字段一起退回 init 的值。",
        why="⚠️ **症状指向错误的那一方。** 页面上看是「日线没跑」，"
            "而日线跑得好好的，问题在另一个 producer 的写回。"
            "R2 的「scan 0/3」很可能是同一件事，当时被记成「抓早了」。\n\n"
            "⚠️ `finally` 那一套在这里不适用 —— 这不是同一进程里的临时状态，"
            "是四个 cronjob 各自的进程在同一份文件上。"
            "唯一可靠的做法是**把读—改—写压到一次 await 之内**。\n\n"
            "四个 cronjob 里有三个写这份文件，而它们的 cron 表达式"
            "（`*/15` · `5 * * * *` · `0 12 * * 1-5` · `15 22 * * 1-5`）"
            "本来就会在整点附近撞上。**这不是偶发，是每天都会发生几次。**",
        fix=["`lib.js` 加 `commitFindings(rd, wr, {owns, mine, patch})`:"
             "写之前重读，只替换自己那一族，别人的原样留下",
             "三个 producer 全部改用它 —— 日线 PV1、盘中 PV5+US、上下文 EV4",
             "顶层字段也要认领:`asOf` / `scan` / `scanned` 归日线"],
        assertion="⚠️ 桩环境跑不到这条路 —— `producer.js` 在桩里只写出 `data/meta.json`，"
                  "findings 的写入分支根本没被执行过。**这条只能靠真跑验。**",
        verified="R6 真跑:盘中 → 日线 → 上下文 依次执行完，`scan` 仍是 3 行、"
                 "`asOf` 仍是日线的 00:00Z、PV5 finding 仍在。修之前 `scan` 会变成空数组。",
        repro="同一分钟内先跑日线再跑上下文，看 `scan` 是否被清空。",
    ),
    dict(
        id="BC41", group="selfcheck", sev="high", owner="判官",
        caught=False, fixed="已修",
        title="「有没有参考竞品实现」的检测器，数的是我们自己写的警告",
        symptom="第一版按整篇 transcript 计数，R5 报出 4 处 skillhub 痕迹。"
                "逐条看全是假的。",
        cause="1 处是 agent 在读我们自己 SKILL.md 里那段「不要切过去」的警告，"
              "3 处是 `alva release playbook --help` 的输出里提到 `alva skillhub list`。"
              "SKILL.md 自己就含全部四个探针串（×1 / ×2 / ×2 / ×1），加起来正好对上。",
        why="⚠️ **这个检测器报的方向是反的：警告写得越细，命中越多。**\n\n"
            "而它要判的恰恰是「警告有没有起作用」—— "
            "于是一次成功的防守会被读成一次失守。\n\n"
            "同一类还有第三种来源:CLI 自己的帮助文本。"
            "凡是「在一大团文本里找关键词」的检查，都要先问"
            "**这个词还会从哪儿来** —— 被测对象、检查器自己、以及工具的输出。",
        fix=["只在执行过的命令行里数（transcript 里以 `/bin/zsh -lc` 开头的行）",
             "「撞订阅墙」是返回值不是命令，单独从全文找，并减掉 SKILL.md 自己那一处"],
        assertion="做过破坏性测试:往 transcript 尾部注入一条 "
                  "`/bin/zsh -lc \"alva skillhub get …\"`，检测器从 0 变 1。"
                  "R5 真实值是 0 —— 边界声明确实挡住了。",
    ),
    dict(
        id="BC39", group="copy", sev="high", owner="脚本",
        caught=False, fixed="已修",
        title="gap 只并不清，欠条变成永久事实",
        symptom="R5 的 `market.json` 里躺着 4 个指数，而方法页照旧写着"
                "「市场数据尚未取过」（`market_not_yet_fetched`）。",
        cause="每个 producer 都写 `new Set([...meta.gaps, ...新增])` —— **只并不清**。"
              "`market_not_yet_fetched` 是 init 立的一张欠条，市场 producer 跑完把它兑现了，"
              "却没人去撕。",
        why="gap 有两种，混在一个集合里:\n\n"
            "**永久边界**（加密无市值总量 · 判据只测波动放大）—— 只并不清是对的。\n"
            "**欠条**（「这一步还没做」）—— 做完了还在，页面就在说一件"
            "**当时为真、现在为假**的事。\n\n"
            "而 gap 恰恰是这个产品里「我们承认自己不知道什么」的地方。"
            "一条假的 gap 比没有 gap 更糟 —— 它把可信度花在了一件已经不成立的事上。",
        fix=["市场 producer 写完 market.json 后 `gaps.delete(\"market_not_yet_fetched\")`",
             "检查器补一条:id 里带 not_yet / not_run / pending 的一律要求有人 delete"],
        assertion="`check_consistency.py`「欠条必须有人撕」。"
                  "做过破坏性测试:拿掉那行 delete，检查器当场报出 market_not_yet_fetched。",
    ),
    dict(
        id="BC40", group="never", sev="high", owner="SKILL.md",
        caught=True, fixed="已修（待 R6 验）",
        title="建了 cronjob 不等于跑过，首屏带着洞发布",
        symptom="R5 建齐四个 cronjob，却只手工跑了三个。`freshness` 只有四个键，"
                "缺 `intraday` —— 页面发布时没有 PV5、没有用户线。",
        cause="SKILL.md 只要求「四个 cronjob 都要建」，没要求**建完各跑一次**。",
        why="⚠️ **这条是 BC34 的下一层。** BC34 是「少建了」，这条是「建了没跑」，"
            "而两者在页面上长得一模一样 —— 都是那一块空着。\n\n"
            "时间差不对等:盘中 15 分钟就补上了，**日线要等到 22:15 UTC**，"
            "中间二十小时里持仓表整个告警基准栏是空的。"
            "而第一个打开这一页的人，通常就是刚刚要它的那个人。",
        fix=["SKILL.md 在「数一遍」之后补一步:四个 producer 各手工跑一次，"
             "再读回 `freshness` 数五个键",
             "把三道闸门分开写 —— **建了四个 · 跑了四个 · 五个键**，它们会各自失败"],
        assertion="`freshness` 五键断言已在 assertions.py 与 collect.py 的落定检查里。",
    ),
    dict(
        id="BC35", group="baseline", sev="critical", owner="脚本",
        caught=False, fixed="已修 · R5（美股）与 R6（加密）都验过",
        title="同一个 skill 给加密账本一把一个月的尺子，给美股账本五个月的",
        symptom="两本都盯 BTC/SOL/DOGE 的 playbook，同一天同一根 bar，"
                "一本报三条 PV5 告警，另一本一条都不报。",
        cause="`init.js` 的盘中取数请求 150 天，却带着 `limit=3000`。"
              "**`limit` 是行数上限**，加密一天 96 根十五分钟 bar，"
              "一次请求最多装 31.25 天；美股一天约 26 根 RTH，150 天才 2,700 行，"
              "同一个请求装得下。于是资产类别决定了窗口长度，而代码和注释都写着 150 天。",
        why="窗口短不是「精度差一点」，是**换了一个读数**。"
            "实测同三根 bar：31 天窗口下 |z| = 15.9 / 16.6 / 10.3，全部越过 θz=10；"
            "90 天窗口下是 11.8 / 7.3 / 7.0，只剩一根越线。"
            "σ 之比与 z 之比逐根吻合（1.337 / 2.278 / 1.461），"
            "**引擎没错，尺子不是同一把**。\n"
            "这是可复用性缺陷里最难看的一类：它不报错、不缺字段，"
            "`n: 31` 还诚实地写在文件里 —— **只有把两本账并排看才看得见**。",
        fix=["`intraday()` 分段取：加密 25 天一段、美股 45 天一段，按 bar 时间戳去重合并",
             "窗口定为 **90 天**，不是代码原来写的 150 —— spec §PV5 是 90，"
             "θz_bar 就是在 90 天同槽位基线上反解的。第一版修成 150 只是把分歧挪了个位置",
             "落 `barCoverage {askedDays, chunks, failedChunks, spanDays}` 进 baselines",
             "`get()` 返回 [] 时把该段计为失败 —— 「这段真没数据」在 150 天窗口里不是真状态，"
             "和「请求挂了」折叠在一起就是半长基线冒充满长基线",
             "取短了推 `intraday_history_short` gap，页面上说出来"],
        assertion="`barCoverage.spanDays` 与 `askedDays` 的差进 gap；"
                  "output-schema §slotBaselines 记下这个字段的存在理由。",
        verified="R6 真跑（2026-08-23，指名模式）：BTC/SOL/DOGE 三只全部 **96 槽 · 每槽整 90 样本** ·\n4 段 0 失败。同三个槽位的 σ 与本地 90 天口径之比 1.02 / 1.04 / 1.17 ——\n修之前两本账是 1.37 / 2.37 / 1.71。**两本独立建出来的账现在对同一根 bar 给同一个判断。**\nR5（NVDA，美股路径）：25 槽 · 每槽整 90 样本 · spanDays 137.3。",
        repro="两本账都建在 BTC/SOL/DOGE 上，比 `baselines.BTC.slotBaselines['05:00'].n`。",
    ),
    dict(
        id="BC38", group="baseline", sev="high", owner="脚本",
        caught=False, fixed="已修 · R6 验过（96 槽，不再是 95）",
        title="加密 00:00 那根永远评不出读数，而且静默",
        symptom="init 建出来的加密标的只有 **95** 个槽位，不是 96。缺的那个是 `00:00`。",
        cause="`init.js` 无条件跳过跨日收益，而运行期 `producer-intraday.js` 的守卫是 "
              "`cls !== \"crypto\"`。加密 24 小时连续，23:45→00:00 是一段真实收益不是跳空；"
              "init 把它全部丢掉，于是 00:00 槽一个样本都攒不到，落不进 `slotBaselines`。",
        why="**两边不一致的后果是静默的。** 运行期照常算 00:00 那根的收益，"
            "然后 `sb['00:00']` 取不到、`continue` —— 和「那根没触发」在产物里"
            "长得一模一样。加密一天 96 根，有 1/96 的时刻是结构性盲区，"
            "而它恰好是 UTC 日的第一根,也就是「今天」的开头。",
        fix=["`init.js` 的守卫改成 `cls !== \"crypto\" && …`，与运行期同一个条件"],
        assertion="加密标的的 `slotBaselines` 槽位数应为 96；95 就是这条又回来了。",
        repro="比 `Object.keys(baselines.BTC.slotBaselines).length` 与 96。",
    ),
    dict(
        id="BC36", group="selfcheck", sev="high", owner="检查器",
        caught=False, fixed="已修",
        title="gap 文案检查器只认双引号，于是从没查过任何带参数的 gap",
        symptom="`check_consistency.py` 每次都印「脚本写出的 8 种 gap 全部有文案」。"
                "放开引号后立刻浮出三条没有文案的。",
        cause="正则只匹配双引号字面量（`gaps.push(\"...\"` 那一种），"
              "而**带参数的 gap 一律写成模板串**。"
              "字符类 `[a-z_]+` 又断在数字上，`pv5_grade_unavailable` 被读成 `pv`；"
              "键表那一侧用的是同一个字符类，所以两边都把它读成 `pv`，"
              "**错得一致，于是对上了**。",
        why="它不是判错了，是**根本没把这些 gap 收进来**。"
            "「8 种全部有文案」这句话为真，而它没说的是分母只有 8。"
            "两条被它藏了很久的真缺陷：`pv5_grade_unavailable` 从来没有文案，"
            "`scan_empty_with_3_holdings` 里没有冒号、整串当键、永远查不到 —— "
            "两条都会把裸 id 印给用户，而那句话的意思是「这个页面比管线旧」。",
        fix=["正则认三种引号，字符类改 `[a-z][a-z0-9_]*`",
             "键表侧用同一个字符类 —— 两侧不同就不是在比同一批名字",
             "`scan_empty_with_${n}_holdings` 改成 `scan_empty_with_holdings:${n}`",
             "补 `gapIntraShort` · `gapPV5Grade` · `gapScanEmpty` 中英文案"],
        assertion="放开后计数从 8 升到 12，且三条新键都要有文案才通过。",
    ),
    dict(
        id="BC37", group="copy", sev="med", owner="页面",
        caught=False, fixed="已修",
        title="「N alerts today」的 today 是 UTC 日，而卡片时间是 ET",
        symptom="07:31 ET 打开，「2 alerts today」里躺着一条 "
                "`Aug 22 22:00 ET` —— 看起来像昨天的告警混进了今天。",
        cause="两个 producer 都按最后一根 bar 的 **UTC 日期**取当天 bar，每轮整族替换，"
              "所以桶是 UTC 日。加密 24 小时交易，UTC 日的头四小时落在 ET 的昨天。"
              "两个数都对，错的是 today 这个词。",
        why="又一次「有收盘的市场」的默认词被套到 24 小时市场上（第九类）。"
            "美股不受影响 —— RTH 永远不跨 UTC 午夜，那边 UTC 日与 ET 交易日重合。",
        fix=["副标题补一段 `since <日期> <时刻> ET`，起点按 UTC 日零点算再格式化成 ET",
             "⚠️ 不写死 20:00 ET —— 冬令时是 19:00",
             "⚠️ 不 `slice(0,10)` 取 META.now 的日期 —— 它带偏移，切出来是 ET 的那天",
             "只在账本里有加密时印；纯美股账本印它会让人以为盘后也在看"],
        assertion="L4 已过；中英双语与「US only」账本三种情况人工核过（US 账本该句消失）。",
    ),
    dict(
        id="BC1", group="render", sev="critical", owner="页面 + 数据",
        caught=False, fixed="数据侧已修 · 页面侧未修",
        title="二级页六块卡片全空,而数据都在文件里",
        symptom="「标的详情与告警历史」页:告警历史图 · 价格与幅度 · 覆盖状态 · "
                "内部人申报 · 财报日历 · 近期新闻 —— 六块全是空壳。",
        code="Uncaught TypeError: Cannot read properties of null (reading 'toLocaleString')\n"
             "    money2 → lab → rangeBar → renderP2Blocks → renderP2 → renderActivePanel",
        cause="`range52w.low` 是 `null`,`money2(null)` 抛出,**renderP2 整个中断**,"
              "它后面的每一张卡都没来得及渲染。",
        why="这条的严重性不在于它错,在于它**撒谎的方向**。"
            "`symbols/NVDA.json` 里财报数据是全的(下次 `2026-08-26`,四次历史),"
            "而页面上财报卡是空的 —— 看上去像「端点没给财报」,"
            "于是排查会去查财报端点,而真正的原因在另一张卡的一个 null 上。",
        fix=["数据侧:`range52w.low` 要有值(见 BC4)",
             "页面侧 ①:`rangeBar` 收到 null 边界时不画,给一句话说明,而不是抛",
             "页面侧 ②:每张卡独立 try —— 一张卡渲染失败只该让那张卡显示错误,"
             "不该让它后面的卡集体消失"],
        assertion="新增 L4 渲染层:把产物喂进模板无头跑一遍,断言控制台零异常,"
                  "且四个 tab 的卡片数量与 mock 基线一致。",
        repro="把产物拷进 scratchpad/repro 起静态服,点第二个 tab,控制台一条异常。",
    ),
    dict(
        id="BC2", group="placeholder", sev="high", owner="脚本", caught=True, fixed="已修",
        title="`symbols/<SYM>.kline` 是空数组",
        field="kline", actual="[]", expect="502 根", onpage="蜡烛图整块空白",
        cause="`init.js` 写 `kline: []` 占位,此后没有任何 producer 填过。",
        fix=["`init.js` 的 `daily()` 尾部追加 OHL(前三位不动,现有 `r[0..2]` 全部照旧)",
             "`producer.js` 每日续:读改写、按日期去重 —— 不续的话图冻在建库日,"
             "而冻住的走势图和真实横盘长得一模一样"],
        assertion="已补 L0 断言并做过破坏性测试(置空 → 真的挂了一次)。",
    ),
    dict(
        id="BC3", group="placeholder", sev="high", owner="脚本", caught=True, fixed="已修",
        title="`holdings[].spark` 是空数组",
        field="spark", actual="[]", expect="30 个收盘价", onpage="行内走势图空白",
        cause="同 BC2。spark 是**纯价格**序列,不需要持仓数 —— "
              "空着不是「没连账户」,是没填。",
        fix=["`init.js` 建库时切最后 30 根", "`producer.js` 每日重切"],
        assertion="已补 L0 断言并做过破坏性测试。",
    ),
    dict(
        id="BC4", group="placeholder", sev="critical", owner="脚本", caught=False, fixed="已修",
        title="`range52w.low` 是 null",
        field="range52w.low", actual="null", expect="近 252 根最低价",
        onpage="**抛异常,整页阵亡 —— 见 BC1**",
        cause="`init.js` 写死 `low: null`,只填了 `high`。",
        fix=["`init.js` 从已取的日线算 `Math.min` over 252",
             "`producer.js` 每日用合并后的 kline 重算 low/high/asOf"],
        assertion="⚠️ **判官漏了这一条,而它正是抛异常的那个值。** "
                  "我的区间断言写成「low 和 high 都非空才比」,null 走 MISS 分支,"
                  "而 MISS 不算失败 —— 一个能被 null 绕过的空值检查。",
    ),
    dict(
        id="BC5", group="placeholder", sev="high", owner="脚本", caught=False, fixed="已修",
        title="`historicalTriggers` 恒为 0",
        field="historicalTriggers", actual="{PV1: 0, PV5: 0}", expect="{PV1: 8, PV5: 3}（mock 同期）",
        onpage="持仓行「过去两年 0│0」",
        cause="`init.js` 写死 0,从不计算。",
        why="**这组里唯一会撒谎的一条。** 空图看起来像没数据,而「过去两年 0│0」"
            "是一个**具体的数字断言** —— 它在说 NVDA 两年里一次都没触发过。"
            "2171 根历史的 NVDA 不可能如此。空白是缺席,0 是错误答案。",
        fix=["`init.js` 里回放历史:逐日算 `firedPV1` / `firedBar`,数出触发日",
             "⚠️ 回放用的判据必须复用运行时那个函数(`L.firedPV1`)。"
             "另写一份就会出现「历史说触发过、今天同样的读数说没有」"],
        assertion="无。要补:`historicalTriggers.PV1` 与 `alertHistory` 里 PV1 的条数必须相等。",
    ),
    dict(
        id="BC8", group="placeholder", sev="med", owner="脚本", caught=False, fixed="已修",
        title="`symbols/<SYM>.alertHistory` 是空数组",
        field="alertHistory", actual="[]", expect="11 条（mock 同期）", onpage="告警历史图上一个标记都没有",
        cause="同 BC2,占位从不填。",
        fix=["与 BC5 同一次回放产出 —— 数触发日和记录触发日是同一件事,分开做必然对不上"],
        assertion="无。与 BC5 那条合并。",
    ),
    dict(
        id="BC9", group="placeholder", sev="low", owner="脚本", caught=False, fixed="已修",
        title="`coverage.pv5From` 是 null",
        field="coverage.pv5From", actual="null", expect="分钟线第一天", onpage="覆盖状态卡无内容",
        cause="`init.js` 写死 null。分钟线已经取到了(52 根),只是没记下起点。",
        fix=["取分钟线时顺手记第一根的日期"],
        assertion="无。",
    ),
    dict(
        id="BC6", group="wrongquantity", sev="high", owner="页面", caught=False, fixed="已修（前端）",
        title="「0 根历史,仍处于 PV4 状态」—— 而基线有 2171 天",
        symptom="二级页底部:「0 根历史。基线需要 60 根,所以这只票仍处于 PV4 状态,"
                "图上每一天都还没有被判定过。」",
        truth="`baselines.NVDA.baselineDays = 2171`,`usable = true`,PV1/PV5 两个等级都算出来了。",
        cause="同一页的持仓行用 `p.base = baselineDays`(2171,渲染正常),"
              "而这句话用的是**图上的 K 线根数**(0)。"
              "两个量都叫「历史」,页面拿后者去断言前者的性质。",
        why="修掉 kline 之后症状消失,**但机制还在** —— "
            "图表数据缺失时,它还会把「画不出图」说成「不够做基线」。",
        fix=["基线充足性一律读 `baselineDays`,不从任何图表序列推",
             "图表为空时说「这段区间没有可画的 K 线」,那是另一句话"],
        assertion="L4:页面上印出的基线天数必须等于 `baselines` 里的值。",
    ),
    dict(
        id="BC7", group="wrongquantity", sev="med", owner="页面", caught=False, fixed="已修（前端）",
        title="标题渲染成 `undefined 年 NaN 月 NaN 日`",
        symptom="`undefined 年 NaN 月 NaN 日 – undefined 年 NaN 月 NaN 日 · 0 个交易日`",
        cause="空 kline 上取首尾元素再格式化。",
        fix=["与 BC6 同一处:序列为空时不画区间标题"],
        assertion="L4:页面文本里不得出现 `NaN` / `undefined` / `[object Object]`。"
                  "**这条极便宜,而它能挡住一整类。**",
    ),
    dict(
        id="BC13", group="wrongquantity", sev="low", owner="页面文案", caught=False, fixed="已修（前端）",
        title="组合净值是个空框,没有一句话",
        symptom="「组合净值」卡有档位切换,下面一片空白。",
        truth="`series.points` 为空是**对的** —— 未连接账户就没有净值曲线。",
        cause="数据对,缺的是空态文案。空框读起来像加载失败。",
        fix=["未连账户时直接说「未连接账户,没有净值曲线」,并说明告警不依赖它",
             "首页顶部已经写了这句,曲线卡自己也要说 —— 用户不会往回读"],
        assertion="归到 L4。",
    ),
    dict(
        id="BC14", group="wrongquantity", sev="none", owner="判官（我）", caught=None,
        fixed="⚠️ 撤回 —— 这不是缺陷，是我的判官误报",
        title="〔撤回〕美股页面上有一张空的「资金费率」卡",
        symptom="我报的是:Tab 2 的 `w-p2-fund` 在 NVDA 上是个空壳,标题在、正文 0 字。",
        truth="**页面本来就是对的。** `p2Scope(p)` 按「键存不存在」隐藏卡片"
              "(`insider`/`earnings`/`funding` 三张各按各的键),而契约说的正是这个:"
              "「不适用就整个省掉这个键」。美股上那张卡是**藏起来的**,不是空的。",
        cause="⚠️ **隐藏元素的 `innerText` 是空串。** 我的 L4「每张卡都有正文」"
              "把藏起来的卡数成了空的卡。\n\n"
              "而且这是同一个坑的第二次:我在 **panel** 那一层修过它"
              "（隐藏 panel 的 innerText 也是空串，当时报出 18 张假空卡），"
              "却没想到**卡片**这一层还有一次。修一层不等于修了这一类。",
        why="与 BC13 同一族:**合法的空被画成了空白**。"
            "而空白读起来是「这里本该有东西,但没取到」—— 契约特意区分的"
            "「不适用」与「暂时没有」,到页面上又合成了一个样子。",
        fix=["✅ 判官已修:不可见的卡不计入正文断言,并单独报「有 N 张按适用范围隐藏」——"
             "静默跳过的话,「这本账用不到」和「这张卡没了」在计数上又长得一样",
             "判据用 `offsetParent`/`hidden`,不用 `style.display` —— 卡可能是被**祖先**藏的,"
             "问它自己的 display 得到的是「我没被藏」"],
        assertion="⚠️ **这条留在台账里不是为了记缺陷,是为了记判官的一次误报。** "
                  "我当时把它当成「L4 上线后自己找出来的第一条」,还写进了给前端的工单。"
                  "判官报出来的东西同样要复核 —— 这一条本可以靠读一遍 `p2Scope` 十秒钟排除。",
    ),
    dict(
        id="BC10", group="never", sev="high", owner="脚本", caught=False, fixed="已修",
        title="新闻链路没有被搬进 Skill",
        symptom="`news.json.items` 是 `[]`,symbol 文件连 `news` 键都没有。"
                "**Tab 1 底部「今日相关新闻」**永远是「0 条扫描中 0 条通过筛选」,"
                "**Tab 2「该标的近期新闻」**永远空。",
        cause="九个脚本里只有 `attribution.js` 打 `market-news`,而归因只在**有 L1 卡**时才调 ——"
              "没有告警的日子等于没有任何新闻。",
        why="**mock 里之所以有新闻,是另一条管线填的。** `pipeline/build_enrich.py` 从 "
            "`raw/news_market.json` 取,写 12 条进 `mock/data/news.json`。"
            "它自己的注释就写着:「这三块原来都没有生产者,重跑 build.py 就会丢」——"
            "三块指新闻 · 资金费率 · 用户线。**用户线搬进 Skill 了,新闻和资金费率没有。**"
            "所以这不是「链路不存在」,是**链路存在于 `pipeline/`,没被搬进 `skill/scripts/`**。",
        cost="`market-news` 1 credit/次/只。每天每只一次,10 只组合 = 10/天。",
        fix=["新增一个 producer,或并进 context producer(它已经是盘前跑一次)",
             "两个消费点数据形状不同:`news.json`(全组合宽链,带 `chain`/`minRelevance` 筛选)"
             "与 `symbols/<SYM>.news`(逐标的)。一次取数落两处",
             "⚠️ 与归因共用取数结果,别为同一只标的在同一天打两次"],
        assertion="要补:持仓里每只美股在 `symbols/<SYM>.json` 里都要有 `news` 键"
                  "(可以是空数组 —— 空数组是「找过没有」,缺键是「没找过」)。",
    ),
    dict(
        id="BC15", group="never", sev="high", owner="脚本", caught=False, fixed="已修",
        title="资金费率也没被搬进来 —— DR1 在加密组合上永远不会触发",
        symptom="九个脚本里 `funding` 一次都没出现。`symbols/<SYM>.json` 没有 `funding` 键,"
                "而 DR1「费率极端」在信号目录里是**已定案的 13 条之一**。",
        cause="与 BC10 同源:`pipeline/build_enrich.py` 里有资金费率那一步,Skill 的 producer 里没有。",
        why="⚠️ **比 BC10 严重,而且更没道理。** 输入拿不到就等于这条信号被静默停用 ——"
            "而目录里它还在,页面上还给它留着一张卡。"
            "`/crypto/funding-rate` 是**免费**端点,不取没有任何成本上的理由。\n\n"
            "⚠️ 前端指出的一点更要紧:**一条信号从不触发,和一条信号不存在,在页面上长得一模一样**"
            " —— 资金费率卡照常渲染(它读 `funding.points`,画得出图),只是永远没有告警。"
            "这是「安静的一天」与「系统坏了」那对老问题的第三种形态。"
            "所以 `extremeDays: []` 必须落盘:空数组是「找过,这段时间没有极端」,缺键是「没找过」。",
        cost="免费。",
        fix=["在 context producer 里加一步,加密标的取 `/crypto/funding-rate`",
             "落 `symbols/<SYM>.funding = {asOf, unit, threshold, normalized, points, extremeDays}`",
             "⚠️ 契约:股票**整个省掉这个键**,不要写 null(见 BC14)"],
        assertion="要补:每只加密标的必须有 `funding` 键,每只美股必须**没有**这个键。"
                  "两个方向都要断言 —— 只断一边的话,「全都有」和「全都没有」会各过一半。",
    ),
    dict(
        id="BC16", group="never", sev="med", owner="脚本", caught=False, fixed="已修",
        title="`allocation.byTheme` 恒空 —— PF3 拿不到输入",
        symptom="`portfolio.json` 的 `allocation.byTheme` 是 `[]`。`init.js:357` 写死。",
        cause="主题要从 `get_company_themes` 之类的来源取,Skill 里没有这一步。",
        why="PF3 输入为空等于它从不出现。"
            "⚠️ 与 BC10/BC15 不同的是,**这个是要花 credits 的**(MCP 调用计费为 `ask`),"
            "所以先要决定值不值,再谈怎么做。",
        fix=["先定值不值得为主题集中度花 credits,再谈怎么做"],
        assertion="无 —— 待定的东西不设断言,否则断言会逼着人去实现一个还没决定要做的功能。",
    ),
    dict(
        id="BC11", group="never", sev="low", owner="脚本", caught=False, fixed="已修",
        title="`market.earningsWeek` 恒为空",
        symptom="市场页「本周财报」卡永远空。",
        cause="`producer-market.js` 里写死 `earningsWeek: []`,从不取。",
        why="⚠️ `/stocks/earnings-calendar` 是**免费**端点 —— 不取没有成本上的理由。",
        fix=["取全市场本周财报,不限于持仓"],
        assertion="无。",
    ),
    dict(
        id="BC17", group="placeholder", sev="high", owner="脚本", caught=False, fixed="已修",
        title="信号目录与 spec 的投递上限漂了两处",
        field="maxDelivery", actual="EV1 → L3 · PF3 → L2",
        expect="EV1 → L4 · PF3 → L3（spec）", onpage="EV1 出现在持仓页 · PF3 进概览信号流",
        cause="`init.js` 的 CATALOG 是 `signal-spec.md` 的可执行副本 —— "
              "**同一事实存两处,必然漂**。",
        why="⚠️ **不是显示错位而已。** `maxDelivery` 是**三道投递上限之一**"
            "(另两道是 `symbol_grade` 与 `degraded`),它决定这条信号实际投到哪一层。"
            "PF3 目录写 L2 而 spec 说 L3 —— 那意味着它会进概览信号流,而 spec 说它不进。\n\n"
            "这跟 CLAUDE.md 记的「`degraded` 上限在管线里是 L3、页面自检里是 L2、"
            "eval 断言里又是 L3,而 spec 说的是第四件事」**是同一个形状**。"
            "上一次的结论是「写第二份的时候就该把它挪进契约」,这次同样。",
        fix=["CATALOG 跟 spec 对齐(spec 是已定案信号的唯一定义处)",
             "`check_consistency.py` 逐条比对类型与投递上限,漂了就红",
             "EV6 明写豁免 —— spec 写的是「attached to PV1/PV5 cards」,不是投递层。"
             "**豁免要写出来**,不能靠 regex 匹配不上而静默跳过:那两者长得一模一样"],
        assertion="已补,并做过破坏性测试(把 PF3 改回 L2 → 检查器真的红了)。",
    ),
    dict(
        id="BC19", group="never", sev="high", owner="脚本", caught=True, fixed="已修",
        title="加密的新闻取回 61 条，过筛后 0 条",
        symptom="`scanned` = `{newsItems: 61, newsPassed: 0}`,而 `news` 键是**有的** ——"
                "于是页面显示成「找过了,今天没有相关新闻」。",
        cause="端点给加密的 ticker 是 `CRYPTO:BTC`,不是 `BTC`。"
              "相关度按裸符号查 → 恒为 0 → 全部被 `≥ 0.80` 的门槛筛掉。",
        why="⚠️ **CLAUDE.md 那条实测原话就是**「`symbol=BTC` 返回 100 条,**`CRYPTO:BTC`** "
            "相关度最高 0.9999」,并专门标注了「此前记的『端点只覆盖美股』作废」。"
            "我读了那一行,还是拿裸符号去比 —— **把一条已作废的记载又实现了一遍**。\n\n"
            "后果不是空白,是**一句因为筛错而说出的实话**:「找过了,没有」。"
            "它比空白更难查,因为它看起来像已经处理过了。",
        fix=["两边都剥掉 `^[A-Z]+:` 前缀再比,不在任何一边写死格式"],
        assertion="L0 抓到了(`news` 键在但 items 为 0,与 `newsItems: 61` 矛盾)。"
                  "要补一条:`newsItems > 0 且 newsPassed == 0` 时必须记进 gaps —— "
                  "「取回了但全被筛掉」是一个需要说出来的状态。",
    ),
    dict(
        id="BC20", group="never", sev="critical", owner="SKILL.md", caught=True, fixed="已修",
        title="第二轮的 agent 根本没建 `config/alerts.json`",
        symptom="页面 fetch `config/alerts.json` → **404**。第一轮的 agent 建了,第二轮没建。",
        cause="SKILL.md 里这一步的指令强度不够,agent 可以跳过而不自知。",
        why="⚠️ **这是唯一一条「同一份 SKILL.md、两次跑出不同结果」的缺陷,"
            "而复用性正是这份作业的核心判据。** 其余缺陷都是稳定复现的,这条不是。\n\n"
            "后果:`dailyCap` 取不到(回落 10)、推送渠道与静默时段读不到、"
            "用户线配置无处可存 —— **US1/US2/US3 三条用户亲手设的线没有落点**。",
        fix=["SKILL.md 里把它列进第八步的必查清单,并要求发布前 stat 一次",
             "页面对 404 要说「配置文件缺失」,而不是静默用默认值 —— "
             "静默回落让「没建」和「建了但用默认」长得一样"],
        assertion="L4 的「没有 404」抓到了。这条断言原本只是顺手加的。",
    ),
    dict(
        id="BC21", group="wrongquantity", sev="high", owner="脚本", caught=False, fixed="已修",
        title="日线 producer 每晚把新闻计数抹成 0",
        symptom="页面一边从 `news.json` 读出 12 条、一边从 `findings.scanned` 读到「扫描 0 条」。"
                "平台机器人原话:「12 stories passed the filter out of zero scanned」。",
        cause="`producer.js` 写 `findings.json` 时无条件写 "
              "`scanned: {newsItems: 0, newsPassed: 0}` —— 而**新闻不是它取的**,"
              "是 context producer 取的。每晚覆盖一次。",
        why="⚠️ 与 BC11(earningsWeek 被写死 `[]`)**完全同形**:"
            "一个 producer 拿常量覆盖另一个 producer 的真实值。"
            "两条都不是算错,是**写了一个自己不知道的量**。\n\n"
            "自己不知道的量应该搬上一轮的,不能写 0 —— `0` 是一个主张,「不知道」不是。"
            "同一处的 `gaps: []` 也一样,整体清空会抹掉别的 producer 记下的缺口。",
        fix=["`producer.js` 搬上一轮的 newsItems / newsPassed / gaps,只更新自己知道的 holdings",
             "`init.js` 建库时写 `null` 而不是 `0` —— 那时新闻确实还没扫过"],
        assertion="无。要补:同一份产物里 `news.json.items` 的条数与 `scanned.newsPassed` 必须一致。",
    ),
    dict(
        id="BC22", group="wrongquantity", sev="med", owner="脚本 + 页面", caught=False, fixed="已修",
        title="加密的隔夜告警落在错误的一天",
        symptom="平台机器人:「An Aug 22 SOL alert is counted as \"today\" on Aug 23」。"
                "`2026-08-23:SOL:PV5:00:30` · `triggeredAt = 2026-08-23T00:30:00Z` "
                "= **8-22 20:30 ET**。",
        cause="加密按 **UTC** 切日(日线 bar 就是这么切的),页面按 **ET** 算「今天」。"
              "两套日历,各自都自洽,摆在同一个「今日告警」计数里就错位。",
        why="⚠️ 第九类。CLAUDE.md 已经记过同源的一次:"
            "「一个来自有收盘的市场的默认值(16:00 ET)被套到 24 小时市场上」。\n\n"
            "⚠️ 另外查出一个**更硬的**问题:id 用的是 `day`(序列里**最后一根** bar 的日期),"
            "而 `triggeredAt` 用的是**这根** bar 的时刻。序列跨 UTC 午夜时两者不一致 ——"
            "23:45Z 那根会被写成次日的 id,同一条 finding 的两个日期互相矛盾,去重键跟着错位。",
        fix=["✅ id 与 episodeId 改用这根 bar 自己的日期,不用 `day`",
             "✅ 约定已定:**页面统一 ET,日线日期出现的地方标出它属于哪套日历**。\n\n"
             "⚠️ 我原本想的是「逐资产类别分桶」——那会让页面上出现**两个「今天」**,对读者更糟。"
             "读者只该面对一个时钟。\n\n"
             "会有一个看起来别扭但**是真的**的效果:一条卡标着「8月22日 20:30 ET」,"
             "而它属于的日线 bar 写着「2026-08-23 UTC」。**别扭正是事实本身,"
             "标注让它可读;不标才是把矛盾藏起来。**\n\n"
             "⚠️ 标注要**每处都有** —— 加密日线日期至少出现在四处(K 线 x 轴 · 告警历史 · "
             "scan 的 asOf · 覆盖状态)。少标一处,那一处就变成「另一个没说清是哪套历的日期」",
             "已加 `dailyZone` / `dateWithZone` / `onDateZ` 三个 helper,K 线区间标题先接上"],
        assertion="要补:`id` 的日期前缀必须等于 `triggeredAt` 的日期(同一时区下比)。"
                  "**这一条不需要任何统计,是纯自洽检查。**\n\n"
                  "⚠️ 改这条时被页面自己的 `auditHardTimes` 抓了一次:我把解释写成"
                  "「UTC 午夜 = 20:00 ET」—— **那是夏令时**,冬令时是 19:00 ET,"
                  "半年后这句就是错的。改成「傍晚」,不写具体钟点。"
                  "**一条写死的钟点在半年后自己变成假话,而没有任何运行时错误。**",
    ),
    dict(
        id="BC23", group="wrongquantity", sev="high", owner="脚本", caught=True, fixed="已修 · 已上线",
        title="产物里有还没发生的事：告警时刻晚于 generatedAt",
        symptom="`2026-08-23:SOL:PV5:00:30` 触发于 `00:30Z`、`02:00Z`、`05:00Z`,"
                "而 `meta.generatedAt` 是 `00:05Z`。三条都比产出它们的那一轮晚。",
        cause="`generatedAt` 由**日线** producer 写(00:05Z 那一轮),"
              "而盘中 producer 此后每 15 分钟往 findings 里加卡,却不更新 `generatedAt`。",
        why="⚠️ 第九类。CLAUDE.md 记过同源的一次:「16:05 跑的那一轮里出现 17:30 的告警」。"
            "当时的结论就是这一条断言 ——「任何 finding 都不能晚于 generatedAt,"
            "一行断言,不需要任何统计」。**断言加了,产生它的那个 bug 没修。**\n\n"
            "后果:页面上「行情更新于」的时刻早于它下面列着的告警,读者无从判断哪个是真的。",
        fix=["每个 producer 写完自己那部分就把 `generatedAt` 推到本轮时刻",
             "或者:`generatedAt` 改成 per-block(各块各记各的),"
             "**而不是一个全局时刻替四个 producer 说话**"],
        assertion="L0 抓到了 —— 这条断言是 R1 时加的,R2 第一次真的响。",
    ),
    dict(
        id="BC24", group="wrongquantity", sev="critical", owner="脚本", caught=True, fixed="已修",
        title="`findings.scan` 被抹空 —— 持仓表右半边整个是白的",
        symptom="`scan` 集合为空,持仓 `['BTC','DOGE','SOL']` 三只都不在里面。\n\n"
                "⚠️ **页面上的后果比判官报的严重得多**:持仓表「告警依据」那半边"
                "(日常波动 · 价格 vs 线 · 量能 vs 线 · 触发 · 近 7 天 · 过去两年)"
                "**六列全部空白** —— 因为它们全从 `scan` 取数"
                "(`const rd = SCAN ? readingsOf(p) : null`)。"
                "读者看到的是一张只有价格、没有任何判断依据的表。",
        cause="盘中 producer 重写 `findings.json` 时没有把日线 producer 写的 `scan` 搬过来。",
        why="⚠️ 与 BC21(新闻计数被抹平)**同形**,只是换了个字段:"
            "**一个 producer 整体重写一个共享文件,把别人写的那部分丢掉。**"
            "而 `scan` 正是「补零告警态」的数据来源 —— 没有它,"
            "「今天扫过了,三只都安静」就退化成「今天什么都没发生」,"
            "而后者跟「系统没跑」长得一模一样。",
        fix=["盘中 producer 读改写,不整体重建",
             "⚠️ 更根本的:`findings.json` 现在被两个 producer 写。"
             "要么拆成两个文件,要么定一条「谁拥有哪几个键」的规矩并做成检查"],
        assertion="L3覆盖 抓到了(scan 集合 vs 持仓集合)。",
    ),
    dict(
        id="BC25", group="never", sev="none", owner="判官（我）", caught=None,
        fixed="⚠️ 撤回 —— 判官的第二次误报",
        title="〔撤回〕归因的 timing 字段与纯函数重算不一致",
        symptom="我报的是:两条 PV5 的 `timing` 写 `after`,而「纯函数重算」得 `before`。",
        truth="**producer 算对了。** BTC 那条唯一的 chain 来源发布于 `05:45Z`,"
              "触发在 `05:00Z` —— 发布在**后**,`after` 是对的。",
        cause="⚠️ 逐字对比就看得出来:\n\n"
              "· producer  `chain.some(x => Date.parse(x.publishedAt) < atMs)` —— **比时刻**\n"
              "· 我的断言  `any(x.get('publishedAt') for x in chain)` —— "
              "只看这个字段**存不存在**\n\n"
              "只要有 publishedAt 就判 before,于是每一条 `after` 都被报成错。",
        why="⚠️ **这是判官的第二次误报**(第一次是 BC14 把隐藏的卡数成空的卡)。"
            "两次形状一样:**断言看起来在核对某个量,实际核的是另一个量**。"
            "我在 CLAUDE.md 里管这叫第六类,而我在写判官时又犯了两次。\n\n"
            "共同的可操作教训:**「重算」必须逐字照抄被测那一侧的算式**。"
            "凭印象重写一遍,写出来的就是另一个函数,而它照样会给出一个看起来合理的答案。",
        fix=["✅ 断言改为解析成真实时刻再比,并复述 producer 那一行的算式",
             "时刻缺一个就报「未跑」,不拿「字段在不在」凑一个答案"],
        assertion="改完后同一份产物上那两条误报消失(10 → 9 条),剩下的全部是真的。",
    ),
    dict(
        id="BC26", group="never", sev="med", owner="归因", caught=True, fixed="已修",
        title="归因文案里出现了时刻",
        symptom="`The 05:00 drop came on heavy volume amid …`",
        cause="提示词明确禁止在 summary 里写时刻,模型没照做。",
        why="禁止的理由是「消息天然延迟,时刻说明不了因果」—— 这条规则本身是对的,"
            "R1 时因为一句「tokenization story arrived 47 minutes later」定下来的。\n\n"
            "⚠️ **提示词里的规则不是保证。** 能用代码判的就别只写进提示词 —— "
            "这条正是「用代码硬门,不只用提示词规则」那条经验的又一个实例。",
        fix=["✅ 已修:在 attribution.js 的解析环节**剥掉**钟点,并记 `strippedClock`。"
             "剥而不是整段丢 —— 时刻之外那句话可能仍有信息,整段丢是过度反应"],
        assertion="L3归因 抓到了(正则扫 summary)。",
    ),
    dict(
        id="BC27", group="wrongquantity", sev="med", owner="页面", caught=False, fixed="已修",
        title="空卡片下面挂着一段解释它内容的脚注",
        symptom="市场页「本周财报」:图区一片空白,下面写着"
                "「Every company reporting this week, not only your holdings. "
                "BMO reports before the open, AMC after the close.」"
                "—— 图例还画着 after close / before open 两个色块,而上面一个都没有。",
        cause="脚注与图例是静态 markup,不看数据在不在。",
        why="⚠️ **这是同一个毛病的第四个实例。** 前三个是 BC13(净值空框没有一句话)、"
            "BC14(美股上的空资金费率卡)、BC18(内部人卡说「共 2 条」而一行都没有)。\n\n"
            "四条合起来是一条规则:**页面为不存在的内容渲染了外壳** —— "
            "标题 · 图例 · 脚注 · 计数。外壳在,内容不在,读者读到的是「加载失败」。\n\n"
            "而这四条的正确答案各不相同,不能一刀切:\n"
            "· BC13 合法的空 → **要**一句话说明为什么空\n"
            "· BC14 不适用   → 整张卡**不该出现**\n"
            "· BC18 有数但不够格 → 说明规则,**去掉那个没有落点的数字**\n"
            "· BC27 暂时没数 → 脚注与图例跟着内容一起隐藏\n\n"
            "共同点是:**外壳的出现与否，要由内容决定**，不能写死在 markup 里。",
        fix=["✅ 已修两处:市场页「本周财报」与 Tab 1 财报流,空态时图例与脚注跟着内容一起不出",
             "⚠️ 空态本身再分两种,判据是 `freshness.market` 在不在,**不是数组空不空** ——"
             "后者两种情况都为真:「这一轮还没取到」是本轮的状态,「本周没有公司发财报」是一个事实",
             "空态该说什么按四种分别定,不要用同一句「暂无数据」盖过去"],
        assertion="L4 的「每张卡都有正文」抓不到这条 —— **它有正文,只是正文说的是不存在的东西**。"
                  "要补:图例/脚注里出现的类别,必须在同一张卡的内容里出现过至少一次。",
    ),
    dict(
        id="BC28", group="never", sev="high", owner="SKILL.md", caught=False, fixed="已修",
        title="发布时把出处标成了 Alva 自己的 skill",
        symptom="`nvda-watch` 的公开页面上写着「Built with: **Portfolio Watch Setup** · "
                "Created by **Alva**」。那是 Alva 官方 32 天前发布的一个 skill,"
                "不是我们这个。",
        cause="agent 执行 `alva release playbook-draft --skill-id …` 时,"
              "**SKILL.md 全篇没提过这个参数**,于是它去 CLI 的 `--help` 里找例子,"
              "又在平台上挑了一个名字最像的。",
        why="⚠️ 这是一句**用户可见的、公开的、假的出处声明**。\n\n"
            "⚠️ 而且它和 BC20 同形:**同一份 SKILL.md,两轮不同结果** —— "
            "第一轮填了 `alva/portfolio-watch-setup`,第二轮压根没填。"
            "凡是 SKILL.md 没规定的地方,agent 会自己找一个看起来合理的答案,"
            "而「看起来合理」和「对」是两件事。\n\n"
            "顺带一个值得知道的事实:**平台上确实已经有一个 Alva 官方的 "
            "`portfolio-watch-setup`**,做的事跟我们高度重叠。这不是缺陷,是背景。",
        fix=["SKILL.md 第八步明写:`--skill-id` **省掉** —— "
             "声明没有出处，好过声明成别人的",
             "同处补了 `--tags` 的说明(纯描述,不放信号 ID 与阈值)"],
        assertion="要补:发布参数里不得出现不属于本 skill 的 `--skill-id`。"
                  "⚠️ 这条得从 transcript 里查,不是从产物里 —— 产物上看不出发布时传了什么。",
    ),
    dict(
        id="BC29", group="wrongquantity", sev="high", owner="页面", caught=False, fixed="已修",
        title="同一页上两个数都叫「基线」，一个 3000 一个 502",
        field="基线", actual="覆盖状态卡 3000 · 持仓行 502",
        expect="同一个词只对应一个量", onpage="读者无从判断哪个是这只标的的基线长度",
        cause="`baselineDays` 是 3000(日线取数 `limit=3000` 拿满),"
              "而 `historicalTriggers.windowSessions` 与 `kline` 都是 502(我切的)。"
              "页面两处各取一个,标签都写「基线」。",
        why="⚠️ 与 BC6 同族,但更难发现:BC6 是「一个对一个错」,"
            "**这次两个数都是对的** —— 它们只是不同的量。"
            "「基线长度」(算 σ 用了多少天)与「回放窗口」(数触发日看了多少天)"
            "本来就是两回事,而页面把它们叫成了同一个名字。",
        fix=["两个量各给各的名字:「基线 3000 个交易日」与「回放窗口 502 个交易日」",
             "⚠️ 别的做法是把它们统一成一个数 —— **不要**。"
             "统一等于丢掉一个真实存在的区分"],
        assertion="要补:页面上出现的每一个基线相关数字,必须能对上 baselines 里的**某一个具体字段**,"
                  "而不是「对上其中之一」。",
    ),
    dict(
        id="BC30", group="never", sev="critical", owner="归因", caught=True, fixed="定案:代码拦发现不了的，L5 判需要判断的",
        title="归因说出了来源里没有的内容",
        symptom="BTC 那张卡的解释:「coverage tied it to **weekend-thin liquidity and "
                "Wintermute short positioning**」。而 `sources` 只有 1 条 —— "
                "Motley Fool 的《Got $500? 1 Cryptocurrency to Buy Hand Over Fist》,"
                "里面没有这两个说法。**它自己还在同一句里承认那条 "
                "「was generic, not a trigger」。**",
        cause="硬门只查「解释里的数字是否都在输入集合内」,不查**说法**有没有来源支撑。"
              "数字全对(它一个数都没引),所以门放行了。",
        why="⚠️ **这是最早那条 badcase 的复发。** 当初「归因不再拿事后报道凑话,"
            "没找到就说没找到」正是为此加的硬门 —— 而它拦的是编造的**数字**,"
            "不是编造的**归因**。\n\n"
            "⚠️ 现在这个形状更糟:它一边声明唯一的来源不是触发因素,"
            "一边给出了一个无来源的解释。**读者读到的是一个有把握的因果判断,"
            "而它背后什么都没有。**\n\n"
            "顺带:这段解释是英文,而页面是中文 —— 归因没有跟随界面语言。",
        fix=["⚠️ **我加过一道门,一小时后撤掉了。** 那道门查「`origin === \"chain\"` 的条数为 0 就丢」——"
             "而 BTC 这条**有** 1 条 chain 来源,门放行。**它拦不住写它的理由。**"
             "它真能拦的(来源全是自搜)页面早就标着「Alva 自行检索」,读者本来就看得见。"
             "一道既解决不了目标案例、又重复了页面已有信息的门,只剩副作用:"
             "**模型自搜是功能不是泄漏**,而它会把自搜出来的解释整段扔掉",
             "✅ 留下的判据只有一条:**读者自己发现得了吗**。"
             "编造的数字发现不了 → 代码硬门;语气、时序、相关性读得出来 → 提示词 + L5;"
             "「说的和来源对不上」要点开链接才知道 → **L5 判,代码判不了语义**",
             "✅ 分界写进 `eval/PLAN.md` §五,附一张表"],
        assertion="✅ **L5 三个角度全部判不过**,而且各判各的:\n\n"
                  "· A 来源支撑:四处说法在唯一那条来源里零匹配,"
                  "「点名 Wintermute 是把一个真实机构写进了无源叙述」\n"
                  "· B 措辞越界:五处 —— 钟点时刻 · 复述卡片 · `heavy` 评量级 · "
                  "因果账 · 评论发布时序\n"
                  "· C 与数据一致:它说「amid a broader crypto pullback」,而**同一轮的 "
                  "`meta.gaps` 里挂着 `market_not_yet_fetched`** —— 产物自己声明没有市场面数据;"
                  "同批 SOL 那条还明写「no crypto benchmark in the supplied data」,两条互相矛盾\n\n"
                  "⚠️ 代码侧补了「可核来源」门(`origin === \"chain\"` 的条数为 0 就丢),"
                  "**但它拦不住 BTC 这条** —— 它确实有 1 条 chain 来源。"
                  "两道门各拦各的:**代码拦「压根没有可核来源」,L5 拦「有来源但说的不是它」**。"
                  "把拦不住的那部分写出来,比假装拦住了强。",
    ),
    dict(
        id="BC31", group="wrongquantity", sev="med", owner="页面", caught=False, fixed="已修",
        title="自选清单上不该有「组合净值」这张卡",
        symptom="`btc-sol-doge-watch` 的净值卡:`期初 NaN undefined  期末 NaN undefined`,"
                "下面还挂着「净值轴单位: $」和「当日盈亏 · $」两个空标签。",
        cause="未连接账户 → `series.points` 为空 → 取首尾元素格式化出 NaN/undefined。",
        why="⚠️ **这条的答案与 BC13 不同,而我一开始给错了。** BC13 我说「加一句空态文案」——"
            "但用户指出:没连账户就**永远**不会有净值曲线,那是**不适用**,不是暂时没有。"
            "不适用的卡整张不该出现,跟 BC14(美股上的资金费率卡)一个答案。\n\n"
            "佐证:同一份页面在市场页**已经会这么做**了 —— "
            "「本页只有加密,因此没有指数和本周财报两块」。能力是有的,净值卡没用上。",
        fix=["`linked: false` 时整张净值卡不渲染",
             "顶部那句「市值、盈亏、回撤需要连接账户」已经把话说清楚了,不需要第二处空态"],
        assertion="L4 的「每张卡都有正文」抓不到 —— 它有正文,正文是 `NaN undefined`。"
                  "禁词那条能抓到 NaN,但抓不到「这张卡整个不该在」。",
    ),
    dict(
        id="BC32", group="never", sev="low", owner="脚本", caught=False, fixed="已修",
        title="标的没有 logo，全是灰底字母块",
        field="holdings[].logo", actual="null（三只全是）", expect="币种/公司图标 URL",
        onpage="B · S · D 三个灰底字母块",
        cause="`init.js` 写 `logo: h.logo || null`,从账本取 —— 而 agent 建的账本里没有 logo,"
              "**也没有任何 producer 去取过**。",
        why="与新闻、资金费率同源:`pipeline/book.py`(mock 用的账本)里 logo 是手写死的,"
            "Skill 里没有对应的取数步骤。**又一处「mock 比真产物富」。**",
        fix=["✅ SKILL.md §1.3 写明:`logo` 可选,不填时页面画字母块 —— "
             "**那是一个真实的设计,不是失败态**。不可接受的是一个永远为 null 的键:"
             "一个从不带值的字段是一条没人会走到的分支",
             "同处还写了 `theme`(BC16)—— 两者都是「没有接口能给,只能建账本时填」"],
        assertion="要补:`logo` 要么全部有值,要么这个字段整个不在契约里。"
                  "一个恒为 null 的字段等于一个永远走空态的分支。",
    ),
    dict(
        id="BC33", group="never", sev="critical", owner="SKILL.md", caught=True,
        fixed="已修 · R5 干净（0 条执行过的 skillhub 命令）",
        title="agent 会去 skillhub 拉一个竞品实现，然后照着它写",
        symptom="R3 的 agent 自己跑了 `alva skillhub get alva/portfolio-watch-setup`,"
                "读完照着写 `require(\"@alva/portfolio-watch\")`,撞上 "
                "`module … (category: pro_automation) requires a Pro subscription`,"
                "在那个形状上反复重写了四五遍才绕回我们的脚本。",
        cause="平台有 skill hub,`alva skillhub get / file` 能拉任意第三方 skill。"
              "而 Alva 官方有一个 `portfolio-watch-setup`,名字与用途都和我们高度重叠。",
        why="⚠️ **这条同时是两件事,要分开看。**\n\n"
            "**对 eval**:我以为的三重隔离(空目录 · CODEX_HOME · alva 账号)是不完整的 ——"
            "我隔离了文件系统和账号,**没有隔离平台的 skill 注册表**。"
            "`.agents/skills/` 里确实只有两个 skill,而 agent 用 CLI 又拉进来第三个。"
            "此前每一轮都是「两个 portfolio-watch skill 同场」,不是我们这一个单独的测量。\n\n"
            "**对产品**:这不是污染,这是**现实**。用户的 agent 手上本来就会同时有这两个。"
            "BC28(发布时把出处标成 Alva 的 skill)因此不是瞎猜 —— **它真的在用那一个**。\n\n"
            "⚠️ 后果不止是「用错实现」:绕回来之后它只补齐了「能让告警跑起来」的最小集,"
            "**四个 producer 只建了两个**(见 BC34)。",
        fix=["SKILL.md 开头明写自己的边界:这个 skill **自带** producer 实现,"
             "**不**通过 `@alva/portfolio-watch` 代跑;看到同名平台模块时不要切过去",
             "⚠️ 不要在 eval 里屏蔽 skillhub —— 那样测出来的是一个不存在的环境。"
             "**要测的恰恰是「两个都在时我们这个赢不赢」**",
             "一页纸里如实写:平台已有官方同类实现,我们与它的关系要讲清楚"],
        assertion="要补:transcript 里出现 `skillhub` 或 `@alva/portfolio-watch` 时,"
                  "报一条「本轮参考了外部实现」——**不判对错,但必须可见**。"
                  "⚠️ 这条只能从 transcript 查,产物上看不出来。",
    ),
    dict(
        id="BC34", group="never", sev="critical", owner="SKILL.md", caught=True,
        fixed="已修 · R4 与 R5 都建了 4 个",
        title="同一句 query，R1 建了 4 个自动化，R3 只建了 2 个",
        field="cronjob 数", actual="R1 = 4 · R3 = 2",
        expect="4（daily · intraday · context · market）",
        onpage="R3 的产物里 `freshness` 只有 prices 与 intraday",
        cause="context 与 market 两个 producer 从未被建成 cronjob,也从未被跑过。",
        why="⚠️ **这是第二条「同一份 SKILL.md 两次跑出不同结果」**(第一条是 BC20 "
            "`config/alerts.json`)。而复用性是这份作业的核心判据 ——"
            "**不稳定比做错更难交代**:做错能改,不稳定说明规格没把话说死。\n\n"
            "后果是静默的:少建两个 cronjob 不报任何错,页面照常渲染,"
            "只是新闻永远空、财报日历永远空、资金费率永远没有、市场页永远是建库时的骨架。"
            "**每一处看起来都像「这一轮没数据」。**\n\n"
            "⚠️ `scanned.newsItems: null`（本轮刚改的）在这里立了功:"
            "它说的是「没扫过」而不是「扫了 0 条」—— 靠这一个字段就把"
            "「producer 没跑」和「跑了没找到」分开了。",
        fix=["SKILL.md 第七步给出**四个 cronjob 的清单**,并要求发布前 "
             "`alva deploy list` 数一遍:少一个就是没配完",
             "⚠️ 与 BC20 同一处:那一步现在只说「配自动化」,没说**配几个、各是什么**。"
             "凡是 agent 可以少做而不报错的地方，规格就得把数量写死"],
        assertion="要补:产物的 `meta.freshness` 必须同时有 prices · intraday · news · "
                  "earningsCalendar · market 五个键。少一个 = 对应的 producer 没跑过。",
    ),
    dict(
        id="BC12", group="accepted", sev="none", owner="设计", caught=None, fixed="不修",
        title="指数与商品全部显示「未提供涨跌」",
        cause="实时端点只返回一个点,涨跌要靠文件里存的前收去差。首轮没有前收 → null。",
        truth="这是**刻意**的:「未变」是一个主张,「不知道」不是,不能拿 0 顶替。"
              "第二轮起自动正常。",
        why="不是缺陷。但首轮就是用户第一眼看到的那一轮 —— "
            "四个指数五个商品全灰,页面看起来像坏了。",
        fix=["建议:首轮多取一根日线拿前收,而不是等下一轮 —— 涨跌是可算的,只是这一版选了不算"],
        assertion="不判对错。L4 可以记一条「首轮观感」。",
    ),
    dict(
        id="BC62", group="copy", sev="high", owner="页面",
        caught=False, fixed="已修 · v1.5.2 已发布",
        title="持仓表右半边没有时钟，于是页面诱导出一个错误且合理的推断",
        field="Alert basis 那一组列", actual="读数无日期，头上顶着 checked <今天> ET",
        expect="这一组报出自己的读数来自哪一根 bar",
        onpage="周日打开：右侧「0 alerts today」，左侧 SOL 与 DOGE 两个绿色触发标记",
        cause="表头的 `checked … ET` 来自 prices/intraday，每 15 分钟刷；"
              "而 Alert basis 那几列来自日线 producer 最后一根 bar。"
              "两者在周末差好几天，页面只印了前者。",
        why="⚠️ **是用户对着线上页面推出来的，而且推得完全合理。** "
            "他看到 0 与两个触发标记同屏，问「右边 alert 没了，说明最新的数据是不达标的吧」——"
            "按页面给出的信息，这是唯一说得通的解释。而真相是最新数据**根本没算过**。\n\n"
            "⚠️ 这一条与既有的几类都不同。它不是数错了，也不是话说错了 ——"
            "**每一个数都对，每一句话都没撒谎，缺的是一个时刻。**"
            "缺了它，「算过了没过线」与「没算过」在画面上长得一模一样，"
            "而这两种状态的含义正好相反。\n\n"
            "⚠️ 告警流那一侧**是**说了的（「2 from an earlier batch, not counted」），"
            "持仓表这一侧没说 —— 同一批数据在同一屏上被两种口径处理。"
            "一处说清楚不等于说清楚了。",
        fix=["分组名后跟这一组的读数日期，Fired 标记的浮窗也带上",
             "⚠️ 取**逐行**的 `scan[].asOf`，不取顶层那个 —— 混合账本在周末有两个"
             "「最近收盘」，美股停在周五、加密每天都有；顶层那个只是较晚的一个",
             "跨日时显示区间（`readings from Aug 21–Aug 23`）",
             "⚠️ 裸日期走 `onDate`（只切字符）不走 `etDate`（先解析成瞬时再转 ET）——"
             "后者把 `2026-08-21` 当成 UTC 零点，转出来是 8月20日",
             "⚠️ **不在页面上算「落后几根」**：美股要交易日历才知道中间有没有开市，"
             "周末的「上一根是周五」是正常的，把它说成落后就是造一个假故障。"
             "落后与否由 producer 发 gap，那一侧有日历也有真值"],
        assertion="要补：页面上任何一组读数，其时刻必须可从产物里追到某一根 bar；"
                  "同一屏出现两个时刻时两个都要印。⚠️ 现有断言查不到这一类 ——"
                  "它们逐个字段比对数值，而这里每个数值都是对的。",
        verified="acct1 线上 v1.5.2：手工触发日线 producer 后，逐行 asOf 从 0 变 15，"
                 "美股 12 只停在 08-21、加密 3 只推进到 08-23，页面显示 "
                 "`readings from Aug 21–Aug 23`。DOGE 与 SOL 那两条 PV1 消失 ——"
                 "用周日收完的 bar 重算后没过线，状态这才真正变成「算过了，没过线」。",
    ),
    dict(
        id="BC63", group="pipeline", sev="med", owner="数据",
        caught=False, fixed="已修",
        title="本地管线不写 scan[].asOf，于是逐行那条路从来没被走过",
        field="findings.scan[].asOf", actual="15 行全缺", expect="每行带自己那根 bar 的日期",
        onpage="看不出来 —— 页面的回退分支退到顶层 asOf，画面上完全正常",
        cause="`pipeline/build/build.py` 只写顶层 `asOf`。而契约 §findings.scan 明写这个字段，"
              "`skill/scripts/producer.js` 也一直在写。",
        why="⚠️ **两个实现对同一份契约不一致，而不一致的那一侧恰好是 mock。** "
            "于是 BC62 的修复在本地看起来是对的，走的却是回退分支 ——"
            "真正的逐行逻辑一次都没被执行过。\n\n"
            "⚠️ 更隐蔽的是：即使补上字段，这批数据 15 只同一天，"
            "**跨日那条分支仍然不会被走到**。必须造反例。",
        fix=["build.py 补 `asOf: x['d'][-1]`",
             "跨日 gap `holdings_span_multiple_sessions` 同样补上，与 producer 同键",
             "⚠️ 造反例验证：运行时把三个加密标的的 asOf 推到周日，"
             "确认组标签变区间、逐行浮窗各说各的日期，再还原"],
        assertion="`check_schema_drift` 反向查一次：契约里写了的字段，两个实现都要产出。"
                  "现在它只查「数据里有的字段契约里要有」，反向不查。",
        verified="重跑 build_all 后 15 行全带 asOf；acct1 线上 12 : 3 分裂。",
    ),
    dict(
        id="BC64", group="never", sev="high", owner="SKILL.md",
        caught=False, fixed="已修 · acct1 已改",
        title="日线 cron 限定工作日，加密周末两根 bar 永远不会被扫",
        field="cronjob portfolio-watch-daily", actual="`30 22 * * 1-5`",
        expect="`10 0 * * *`",
        onpage="周末读数停在周五，而表头写着今天 —— 即 BC62 的数据侧成因",
        cause="SKILL.md 只写「Daily：once after the close」，没给表达式，"
              "建 playbook 的 agent 自己选了 `1-5`。",
        why="⚠️ **两处都错，而且都不报错。** 一是 `1-5`：对纯股票账本这是自然选择，"
            "账本里只要有一个代币就错了。二是 `30 22`：加密 D 日的 bar 收在 D+1 的 "
            "00:00 UTC，22:30 去读那根还差 90 分钟，量能不足一整天、量比偏低，"
            "**加密于是系统性地少触发**，同样无声。\n\n"
            "⚠️ 这是可复用性缺陷，不是这一本的配置问题 ——"
            "任何新建的带加密账本都会复现。",
        fix=["`10 0 * * *`：在加密收盘之后，同时是前一日 20:10 ET，美股收盘后四小时",
             "⚠️ **不拆成两个 cron。** producer 是整本账一起扫的，"
             "拆开要给它加资产类别参数，且两个 producer 并发写同一个 findings.json ——"
             "那正是 commitFindings 在防的读-改-写竞争。一个表达式覆盖两套日历，"
             "不是说它们一样，而是这个时刻在两边都已收盘",
             "SKILL.md 把表达式写死并说明这两个坑"],
        assertion="要补：产物里若有 crypto 持仓，日线 cron 的表达式不得含 `1-5`，"
                  "且分钟位对应的时刻必须晚于 00:00 UTC。",
        verified="acct1 已改并手工触发一次（此前 run_count=0，从没跑过）："
                 "completed 5.9s，四条用户线告警完好，加密三只推进到 08-23。",
    ),
    dict(
        id="BC65", group="pipeline", sev="high", owner="脚本",
        caught=False, fixed="已修",
        title="目录重组把 build_all 的 cwd 少算了一层，十个阶段里六个当场失败",
        field="pipeline/build/build_all.py", actual="cwd = pipeline/", expect="cwd = 仓库根",
        onpage="不上页面 —— 但整条管线重跑不出来，数据无法从仓库再生",
        cause="本文件从 `pipeline/` 移到 `pipeline/build/` 之后，"
              "`os.path.dirname(HERE)` 从仓库根变成了 `pipeline/`。各阶段脚本用的是"
              "相对仓库根的路径。",
        why="⚠️ **一致性检查跑不到 build_all，所以上一个提交里它是坏的而检查全绿。** "
            "重组那次改了约十五处引用，改对的是被检查覆盖的那些。\n\n"
            "⚠️ 同一次重组还留下 12 处陈旧路径引用（CLAUDE.md · registry · "
            "eval/PLAN.md · newrun.sh · assertions.py），同样没有检查覆盖。",
        fix=["改成按标记目录 `mock/data` 往上找根，再移动目录也不会错",
             "顺带修掉 12 处陈旧路径引用"],
        assertion="要补：一致性检查里加一步 `build_all --dry-run`，"
                  "确认每个阶段脚本存在且 cwd 下的输入路径可解析。",
        verified="重跑十个阶段全过。",
    ),
    dict(
        id="BC66", group="selfcheck", sev="med", owner="检查器",
        caught=False, fixed="已修",
        title="交付仓库里跑 README 写的检查命令会直接崩",
        field="check_js_parity.py", actual="FileNotFoundError: pipeline/raw/daily.json",
        expect="干净跳过并说明为什么",
        onpage="不上页面 —— 但这是评审 clone 之后第一条会跑的命令",
        cause="原始数据 54 MB 含第三方帖子全文，按设计不进 git。检查器直接 open()。",
        why="⚠️ **崩溃和通过都不是「没跑到」。** 这一条与本册反复出现的那一类同形："
            "执行统计必须能区分「跑完没发现」「早返回」「没跑到」，"
            "而 traceback 把第三种伪装成了第一种的反面。\n\n"
            "⚠️ 交付面向的读者会照 README 跑 —— 第一印象是这个仓库跑不起来。",
        fix=["缺原始数据时打印一行说明并 `sys.exit(2)`",
             "⚠️ 退出码 2 与失败的 1 分开；运行器 `if returncode not in (0, 2)` 才算失败"],
        assertion="⚠️ 这一条本身就是断言层的缺口：没有任何检查在验「检查器在缺输入时的行为」。",
        verified="交付仓库跑：打印跳过说明，退出码 0；工作仓库跑：15 只 × 4 个量逐位相同。",
    ),
    dict(
        id="BC67", group="render", sev="low", owner="页面",
        caught=False, fixed="已修 · v1.5.2 已发布",
        title="七个 no push 点共用同一个可访问名",
        field="cap-dot aria-label", actual="五个都叫 `no push · intraday`",
        expect="名字带上标的",
        onpage="视觉上看不出 —— 屏幕阅读器按名字列控件时那张列表读不出这是哪一只",
        cause="BC60 把徽标改成点时，`aria-label` 沿用了 `capMarkS(scope)`，"
              "而 scope 只有 daily/intraday/price-volume 三种取值。",
        why="⚠️ **位置是视力读者免费拿到的信息，名字是替代它的唯一渠道。** "
            "同一行里 `rowFiredAria` 一直是带标的的，改点的时候没有对齐它。\n\n"
            "⚠️ 页面自检 `auditAriaNames` **当时就在报**，我做 BC60 时没跑它。",
        fix=["`capMarkRow(sym, scope)`，与 rowFiredAria 同一做法"],
        assertion="`auditAriaNames` 已有，够用 —— 缺的是「改完跑一遍」。",
        verified="45 条页面自检全过（此前它报 2 条）。",
    ),
]

BLIND = {
    "have": [("L0", "文件与字段"), ("L1", "白名单"), ("L2", "参数与账目"),
             ("L3", "跨文件自洽"), ("L4", "渲染 · 已上线")],
    "missing": ("L5", "需要判断的 —— 文案是否准确、解释是否站得住（默认关,要花 credits）"),
    "why": "**L4 补上了缺口最大的一层。** 它拦的是数据全对、L0–L3 全过、页面上一片空白 —— "
           "BC1 BC6 BC7 BC13 BC14 全在这一层,"
           "而 BC1 那条把六张卡一起吃掉的异常,靠任何数据层断言都发现不了。",
    "minimal": [
        "无头加载模板 + 产物,四个 tab 逐个切过去,断言零未捕获异常 —— "
        "⚠️ 只收 `console.error` 抓不到 BC1,它是 `Uncaught TypeError`,走 `Runtime.exceptionThrown`",
        "页面文本不得出现 `NaN` / `undefined` / `[object Object]` —— "
        "⚠️ 要排除 `script`/`style`/`pre`/`code`,否则内联 JS 的注释会被当成页面文本",
        "页面上印出的基线天数 == `baselines` 里的值 —— 待前端加 `data-base=\"<SYMBOL>\"` 锚点,"
        "按 symbol 键配对,不按下标",
        "每张卡:**卡片数**与**正文非空**分开报 —— 合成一条的话「卡数对但全空」会算通过,"
        "而那恰好就是 BC1 的症状",
    ],
    "last": "⚠️ **第 4 条我第一版写错了。** 原本只数卡片数,而四个 tab 的 21 张卡是**静态 markup** —— "
            "renderP2 抛异常时一张不少,连标题都在,空的只是挂载点。"
            "那是一条永远不会失败的断言。信号线指出后改成「结构 + 正文分开报」,"
            "才在同一份产物上真的响了。\n\n"
            "L4 上线当天就自己找出一条新的:BC14,在**健康的** mock 主账本上,L0–L3 全过。",
}

# ⚠️ **分组表里没有的组名会被静默丢掉。** 页面按 GROUPS 逐组筛 CASES，
#    组名对不上的一条都不会进任何一组 —— 而顶部那句「共 N 条」数的是 CASES，
#    于是页面**声称自己是全的**。实测漏过 7 条（baseline · pipeline · selfcheck · copy 四个新组），
#    而两个数字之间没有任何东西在比。这里补上那个比较。
_known = {g["key"] for g in GROUPS}
# ⚠️ 必填键缺一个就是 KeyError，而它是在**渲染到一半**时抛的 ——
#    html 已经写出去半份，md 停在上一版，两个文件互相不一致而且都不完整。
#    实测 BC47 少写一个 `cause`，两份产物停在 45 条而脚本报 46 条。
#    先整体检查，再开始写任何文件。
_REQ = ("id", "group", "sev", "owner", "fixed", "title", "cause", "fix", "assertion")
for _c in CASES:
    _miss = [k for k in _REQ if k not in _c]
    if _miss:
        raise SystemExit(f"❌ {_c.get('id', '?')} 缺必填键：{_miss}")
_orphan = sorted({c["group"] for c in CASES} - _known)
if _orphan:
    raise SystemExit(f"❌ 这些 group 不在 GROUPS 里，会被静默丢掉：{_orphan}")
_sevs = sorted({c["sev"] for c in CASES})

SEV_LABEL = {"critical": "阻断", "high": "高", "med": "中", "low": "低", "none": "—"}


# ── markdown ─────────────────────────────────────────────────────────
def to_md():
    o = ["# Badcase 台账 · 真跑发现的缺陷", "",
         f"⚠️ **本文件由 `eval/badcases.py` 生成,不要直接改。**", "",
         f"`{RUN}` = {RUN_FULL}", "",
         f"共 {len(CASES)} 条,判官当时抓到 "
         f"{sum(1 for c in CASES if c.get('caught'))} 条。", "", "---", ""]
    for g in GROUPS:
        rows = [c for c in CASES if c["group"] == g["key"]]
        if not rows:
            continue
        o += [f"## {g['title']}", "", g["lead"], ""]
        for c in rows:
            o += [f"### {c['id']} · {c['title']}", ""]
            meta = f"归属 **{c['owner']}** · 严重度 **{SEV_LABEL[c['sev']]}** · " \
                   f"判官当时 **{ {True:'抓到了', False:'没抓到', None:'不判'}[c.get('caught')] }** · 状态 **{c['fixed']}**"
            o += [meta, ""]
            if c.get("field"):
                o += [f"```\n{c['field']:24s} 真跑 {c['actual']:22s} 该是 {c['expect']}\n"
                      f"{'页面上':24s} {c['onpage']}\n```", ""]
            if c.get("symptom"):
                o += [f"**现象** {c['symptom']}", ""]
            if c.get("code"):
                o += [f"```\n{c['code']}\n```", ""]
            if c.get("truth"):
                o += [f"**事实** {c['truth']}", ""]
            o += [f"**根因** {c['cause']}", ""]
            if c.get("why"):
                o += [c["why"], ""]
            if c.get("cost"):
                o += [f"**代价** {c['cost']}", ""]
            o += ["**修法**", ""] + [f"- {x}" for x in c["fix"]] + [""]
            o += [f"**断言** {c['assertion']}", ""]
            # ⚠️ 「修了」和「验过」是两件事。修完不重跑，等于把「我以为对了」
            #    写成了结论 —— 本项目已经在这上面栽过（Phase 1 三条里两条被撤回）。
            if c.get("verified"):
                o += [f"**已验** {c['verified']}", ""]
            if c.get("repro"):
                o += [f"**复现** {c['repro']}", ""]
        o += ["---", ""]
    o += ["## 判官的盲区", "",
          "现在有的:" + " · ".join(f"{k} {v}" for k, v in BLIND["have"]), "",
          f"完全没有的:**{BLIND['missing'][0]} {BLIND['missing'][1]}**", "",
          BLIND["why"], "", "L4 的最小可用版本(不需要 LLM,不花 credits):", ""]
    o += [f"{i}. {x}" for i, x in enumerate(BLIND["minimal"], 1)]
    o += ["", BLIND["last"], ""]
    return "\n".join(o)


# ── html ─────────────────────────────────────────────────────────────
def rich(t):
    """把 `code` 与 **bold** 转成标签。先转义,所以顺序不能反。"""
    t = html.escape(t)
    out, parts = [], t.split("`")
    for i, p in enumerate(parts):
        out.append(f"<code>{p}</code>" if i % 2 else p)
    t = "".join(out)
    parts, out = t.split("**"), []
    for i, p in enumerate(parts):
        out.append(f"<strong>{p}</strong>" if i % 2 else p)
    return "".join(out).replace("\n\n", "<br><br>")


REPORT_URL = "https://claude.ai/code/artifact/0ef93da7-253e-4160-a2c1-2cb56a232321"


def to_html(report_url=REPORT_URL):
    cards = []
    for g in GROUPS:
        rows = [c for c in CASES if c["group"] == g["key"]]
        if not rows:
            continue
        cards.append(f'<section class="grp"><header class="grp-h">'
                     f'<h2>{html.escape(g["title"])}</h2>'
                     f'<p class="lead">{rich(g["lead"])}</p></header>')
        for c in rows:
            caught = c.get("caught")
            stripe = "ok" if caught else ("na" if caught is None else "miss")
            jl = "抓到了" if caught else ("不判" if caught is None else "没抓到")
            body = []
            if c.get("field"):
                body.append(
                    '<div class="fieldbox">'
                    f'<div><span class="k">字段</span><code>{html.escape(c["field"])}</code></div>'
                    f'<div><span class="k">真跑</span><code class="bad">{html.escape(c["actual"])}</code></div>'
                    f'<div><span class="k">该是</span><code>{html.escape(c["expect"])}</code></div>'
                    f'<div class="wide"><span class="k">页面上</span>{rich(c["onpage"])}</div></div>')
            if c.get("symptom"):
                body.append(f'<p><span class="k">现象</span>{rich(c["symptom"])}</p>')
            if c.get("code"):
                body.append(f'<pre class="trace">{html.escape(c["code"])}</pre>')
            if c.get("truth"):
                body.append(f'<p><span class="k">事实</span>{rich(c["truth"])}</p>')
            body.append(f'<p><span class="k">根因</span>{rich(c["cause"])}</p>')
            if c.get("why"):
                body.append(f'<p class="why">{rich(c["why"])}</p>')
            if c.get("cost"):
                body.append(f'<p><span class="k">代价</span>{rich(c["cost"])}</p>')
            body.append('<p class="k solo">修法</p><ul>'
                        + "".join(f"<li>{rich(x)}</li>" for x in c["fix"]) + "</ul>")
            body.append(f'<p class="assert"><span class="k">断言</span>{rich(c["assertion"])}</p>')
            if c.get("verified"):
                body.append(f'<p class="verified"><span class="k">已验</span>{rich(c["verified"])}</p>')
            if c.get("repro"):
                body.append(f'<p class="repro"><span class="k">复现</span>{rich(c["repro"])}</p>')
            cards.append(f'''<article class="bc {stripe}" id="{c["id"]}">
  <div class="bc-h">
    <a class="bc-id" href="#{c["id"]}">{c["id"]}</a>
    <h3>{rich(c["title"])}</h3>
  </div>
  <div class="tags">
    <span class="tag">{html.escape(c["owner"])}</span>
    <span class="tag sev-{c["sev"]}">严重度 {SEV_LABEL[c["sev"]]}</span>
    <span class="tag j-{stripe}">判官当时 {jl}</span>
    <span class="tag st">{html.escape(c["fixed"])}</span>
  </div>
  {"".join(body)}
</article>''')
        cards.append("</section>")

    caught_n = sum(1 for c in CASES if c.get("caught"))
    scored = [c for c in CASES if c.get("caught") is not None]
    tri = {True: "ok", False: "miss", None: "na"}
    nav = "".join(
        f'<a class="nv {tri[c.get("caught")]}" href="#{c["id"]}" '
        f'title="{html.escape(c["title"])}">{c["id"]}</a>' for c in CASES)

    return f'''<meta charset="utf-8">
<title>Badcase 台账</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root {{
  --paper:#f5f6f9; --card:#ffffff; --ink:#161a21; --dim:#616b7a; --rule:#dee2e9;
  --amber:#9a6200; --amber-bg:#fdf3e0;
  --ok:#0d6a4e; --ok-bg:#e6f4ee;
  --miss:#a32e46; --miss-bg:#fbe9ec;
  --na:#6b7280; --na-bg:#eef0f3;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --paper:#0e1116; --card:#161a21; --ink:#e6eaf0; --dim:#8994a3; --rule:#252b35;
  --amber:#e3a950; --amber-bg:#2b2113;
  --ok:#46c391; --ok-bg:#102b22;
  --miss:#f0798f; --miss-bg:#2e1620;
  --na:#8994a3; --na-bg:#1c212a;
}} }}
:root[data-theme="dark"] {{
  --paper:#0e1116; --card:#161a21; --ink:#e6eaf0; --dim:#8994a3; --rule:#252b35;
  --amber:#e3a950; --amber-bg:#2b2113;
  --ok:#46c391; --ok-bg:#102b22;
  --miss:#f0798f; --miss-bg:#2e1620;
  --na:#8994a3; --na-bg:#1c212a;
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink); margin:0;
  padding:40px 24px 96px;
  font:400 15px/1.72 "IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}}
.page {{ max-width:52rem; margin:0 auto; }}
code,pre,.num {{ font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace; }}

/* ── 抬头 ── */
.top {{ display:flex; flex-direction:column; gap:6px; margin-bottom:28px; }}
h1 {{ font-size:24px; font-weight:600; letter-spacing:-.015em; margin:0; text-wrap:balance; }}
.sub {{ color:var(--dim); font-size:13.5px; margin:0; }}
.sub code {{ font-size:12.5px; }}
.back {{ display:inline-flex; align-items:center; gap:6px; align-self:flex-start;
  margin-top:10px; font-size:13px; color:var(--amber); text-decoration:none;
  border-bottom:1px solid transparent; }}
.back:hover,.back:focus-visible {{ border-bottom-color:var(--amber); }}
.back:focus-visible {{ outline:2px solid var(--amber); outline-offset:3px; border-radius:2px; }}

/* ── 计分条:这一页的论点 ── */
.thesis {{ background:var(--card); border:1px solid var(--rule); border-radius:8px;
  padding:18px 20px; margin:0 0 30px; display:flex; flex-wrap:wrap;
  align-items:baseline; gap:8px 26px; }}
.big {{ font-family:"IBM Plex Mono",monospace; font-size:32px; font-weight:500;
  line-height:1; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }}
.big.miss {{ color:var(--miss); }}
.big.ok {{ color:var(--ok); }}
.stat {{ display:flex; flex-direction:column; gap:3px; }}
.stat .cap {{ font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--dim); }}
.thesis .note {{ flex:1 1 20rem; color:var(--dim); font-size:13.5px; line-height:1.6; min-width:16rem; }}

/* ── 索引 ── */
.nav {{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 34px; }}
.nv {{ font-family:"IBM Plex Mono",monospace; font-size:12px; padding:3px 9px;
  border-radius:4px; text-decoration:none; border:1px solid var(--rule); }}
.nv.ok {{ color:var(--ok); background:var(--ok-bg); border-color:transparent; }}
.nv.miss {{ color:var(--miss); background:var(--miss-bg); border-color:transparent; }}
.nv.na {{ color:var(--na); background:var(--na-bg); border-color:transparent; }}
.nv:focus-visible {{ outline:2px solid var(--amber); outline-offset:2px; }}

/* ── 分组 ── */
.grp {{ margin:0 0 40px; }}
.grp-h {{ border-top:2px solid var(--ink); padding-top:12px; margin-bottom:18px; }}
.grp-h h2 {{ font-size:17px; font-weight:600; margin:0 0 6px; letter-spacing:-.01em; }}
.lead {{ margin:0; color:var(--dim); font-size:14px; max-width:60ch; }}

/* ── 卡片 ── */
.bc {{ background:var(--card); border:1px solid var(--rule); border-left-width:3px;
  border-radius:7px; padding:18px 20px; margin:0 0 14px; }}
.bc.miss {{ border-left-color:var(--miss); }}
.bc.ok   {{ border-left-color:var(--ok); }}
.bc.na   {{ border-left-color:var(--na); }}
.bc-h {{ display:flex; align-items:baseline; gap:11px; margin-bottom:9px; }}
.bc-id {{ font-family:"IBM Plex Mono",monospace; font-size:12.5px; font-weight:500;
  color:var(--dim); text-decoration:none; flex:none; padding-top:1px; }}
.bc-id:hover {{ color:var(--amber); }}
.bc-id:focus-visible {{ outline:2px solid var(--amber); outline-offset:2px; border-radius:2px; }}
.bc h3 {{ font-size:15.5px; font-weight:600; margin:0; line-height:1.45; text-wrap:balance; }}

.tags {{ display:flex; flex-wrap:wrap; gap:5px; margin:0 0 14px; }}
.tag {{ font-size:11.5px; padding:2px 8px; border-radius:3px;
  background:var(--na-bg); color:var(--dim); white-space:nowrap; }}
.tag.sev-critical {{ background:var(--miss-bg); color:var(--miss); font-weight:500; }}
.tag.sev-high {{ background:var(--amber-bg); color:var(--amber); }}
.tag.j-miss {{ background:var(--miss-bg); color:var(--miss); }}
.tag.j-ok {{ background:var(--ok-bg); color:var(--ok); }}

.bc p {{ margin:0 0 9px; }}
.bc p:last-child {{ margin-bottom:0; }}
.k {{ font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:var(--dim);
  margin-right:9px; white-space:nowrap; }}
.k.solo {{ display:block; margin:13px 0 5px; }}
.why {{ border-left:2px solid var(--amber); padding-left:13px; color:var(--ink);
  background:var(--amber-bg); padding:9px 13px; border-radius:0 4px 4px 0; font-size:14px; }}
.assert {{ padding-top:10px; border-top:1px dashed var(--rule); font-size:14px; }}
.verified {{ margin-top:8px; padding:8px 11px; border-radius:5px; font-size:14px;
  background:color-mix(in srgb, var(--ok) 11%, transparent);
  border-left:3px solid var(--ok); }}
.repro {{ font-size:13px; color:var(--dim); }}
.bc ul {{ margin:0; padding-left:19px; }}
.bc li {{ margin-bottom:4px; }}
.bc code {{ font-size:12.5px; background:var(--na-bg); padding:1px 5px; border-radius:3px; }}
.bc code.bad {{ background:var(--miss-bg); color:var(--miss); }}

.fieldbox {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));
  gap:7px 18px; background:var(--paper); border-radius:5px; padding:12px 14px;
  margin:0 0 12px; overflow-x:auto; }}
.fieldbox .wide {{ grid-column:1/-1; font-size:14px; }}
.trace {{ background:var(--paper); border-radius:5px; padding:12px 14px; margin:0 0 11px;
  font-size:12.5px; line-height:1.62; overflow-x:auto; color:var(--miss); }}

/* ── 收尾 ── */
.blind {{ background:var(--card); border:1px solid var(--rule); border-radius:8px;
  padding:22px 24px; }}
.blind h2 {{ font-size:17px; font-weight:600; margin:0 0 14px; }}
.layers {{ display:flex; flex-wrap:wrap; gap:7px; margin:0 0 15px; }}
.ly {{ font-size:12.5px; padding:4px 11px; border-radius:4px; background:var(--ok-bg);
  color:var(--ok); }}
.ly.gap {{ background:var(--miss-bg); color:var(--miss); font-weight:500; }}
.blind ol {{ margin:12px 0 0; padding-left:21px; }}
.blind li {{ margin-bottom:6px; }}
.blind code {{ font-size:12.5px; background:var(--na-bg); padding:1px 5px; border-radius:3px; }}
.tail {{ margin-top:14px; color:var(--dim); font-size:13.5px; }}

@media (max-width:640px) {{
  body {{ padding:26px 15px 64px; }}
  .thesis {{ gap:14px 20px; }}
}}
</style>

<div class="page">
  <div class="top">
    <h1>Badcase 台账</h1>
    <p class="sub">{rich(RUN_FULL)}</p>
    <a class="back" href="{html.escape(report_url)}">← 回到 eval 报告</a>
  </div>

  <div class="thesis">
    <div class="stat"><span class="big">{len(CASES)}</span><span class="cap">条缺陷</span></div>
    <div class="stat"><span class="big miss">{len(scored) - caught_n}</span><span class="cap">判官当时没抓到</span></div>
    <div class="stat"><span class="big ok">{caught_n}</span><span class="cap">抓到了</span></div>
    <p class="note"><strong>「判官当时抓到没有」才是这份台账的价值。</strong>
    缺陷会被修掉,判官的盲区不修就会一直在 ——
    下一个缺陷从同一个洞里漏过去,而报告照样满屏 ✓。
    这一列记的是缺陷被发现时判官的状态,修好判官之后也不改。</p>
  </div>

  <nav class="nav">{nav}</nav>

  {"".join(cards)}

  <section class="blind">
    <h2>判官的盲区</h2>
    <div class="layers">
      {"".join(f'<span class="ly">{k} {v}</span>' for k, v in BLIND["have"])}
      <span class="ly gap">{BLIND["missing"][0]} {BLIND["missing"][1]}</span>
    </div>
    <p>{rich(BLIND["why"])}</p>
    <p class="k solo">L4 的最小可用版本 · 不需要 LLM,不花 credits</p>
    <ol>{"".join(f"<li>{rich(x)}</li>" for x in BLIND["minimal"])}</ol>
    <p class="tail">{rich(BLIND["last"])}</p>
  </section>
</div>
'''


if __name__ == "__main__":
    import sys
    url = sys.argv[sys.argv.index("--report") + 1] if "--report" in sys.argv else REPORT_URL
    (HERE / "badcases.md").write_text(to_md())
    (HERE / "badcases.html").write_text(to_html(url))
    n_miss = sum(1 for c in CASES if c.get("caught") is False)
    print(f"✅ badcases.md · badcases.html  ·  {len(CASES)} 条,判官当时漏了 {n_miss} 条")
