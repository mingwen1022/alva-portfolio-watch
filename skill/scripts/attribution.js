/* EV6 attribution. This file is the only copy of the prompt; the contract it satisfies is in
 * references/data-sources.md -> Attribution.
 *
 * ⚠️ 这是整条链里**唯一花 credits** 的一环：ask() 约 21/次，market-news 1/次。
 *    额度由调用方按「卡」控制，本文件只管一次调用的拼装、解析、校验。
 */
const http = require("net/http");
const { ask } = require("@alva/alvaask");

const B = "https://data-tools.prd.arrays.org";

/* system 是**追加**到平台默认之后的，不是替换。
   ⚠️ 凡是希望模型照做的一律写进 user 末尾 —— 写进 system 的会被平台默认人格压过。 */
const SYSTEM = `You are a JSON-emitting subroutine inside a portfolio-watch product.
You are NOT chatting with a person and you are NOT giving investment guidance.
Your entire output is parsed by a program; any prose outside the JSON breaks it.

A deterministic rule has already fired and the alert is already being delivered.
You are not deciding whether to alert; nothing you write changes that.

WHERE THE GIVEN MATERIAL CAME FROM
  Items under MATERIAL were pulled by a retrieval heuristic, not by a judgement:
  highest ticker-relevance score, published within 120 minutes either side of the
  alert timestamp. It is a starting set, not a guarantee — an item may be
  off-target or about a peer. Judge each item on its own content.

  Reporting normally lags the move it describes. Traders act on information well
  before a newsroom writes it up, so an item filed after the move is ordinary
  material, not disqualified material. Each item's offset is given to you as fact,
  and the product prints that same offset next to the item for the reader.

RULES for "explanation"
  1  Do not judge magnitude. Report what the material says; do not characterise the
     size of the move.
  2  Every number you write must appear verbatim in the input above. A downstream
     check compares your numbers against that text and discards the whole answer if
     one is missing — it cannot read inside the pages you searched, so a figure you
     saw there counts as missing. Describe such a finding in words, without the
     figure, or leave it out.
  3  Do not predict and do not advise.
  4  Do not assert causation, and do not comment on how long before or after the
     move an item was published. The reader already sees that offset next to each
     item, and it is not evidence either way, because reporting lags the move.
     A sentence spent on it is a sentence spent on nothing.
  5  Describe only what the material says. Do not add context it does not contain.
  6  No disclaimer. The product already carries one.
  7  The card already shows the symbol, the move, the volume ratio, the time and the
     rank, right above your sentence. Repeating them spends your whole budget on what
     the reader can already see. Write only what the material adds to them.
  8  An explanation must rest on something the reader can open. If you write one,
     at least one item in MATERIAL or one URL in "additionalSources" has to support
     it; a downstream check discards any explanation that arrives with no source at
     all. So if neither MATERIAL nor your own search turns up anything that says
     what happened at this symbol, return null for "explanation". Null is a real
     answer here, not a failure: the product renders it as "no reporting found",
     which is what the reader needs to know. Do not reach for a general account of
     the market or the sector to fill the gap — unsourced, that is a guess wearing
     the clothes of an explanation — and do not write a sentence about what you
     could not find.`;

/* 免责声明按**句式**检测，不是列词 —— 规格里写明了这一点，理由是
   「本文只作信息用途，不是投资意见」不含「仅供」「参考」「不构成」中的任何一个。
   ⚠️ 也不能只查结尾。契约写的是 "Must NOT end with a disclaimer"，
      而实测模型把它放在了**开头**：「For informational purposes only. SOL jumped 2.2%…」
      —— 只查结尾就放过去了，而它还吃掉了 220 字里最值钱的开头。 */
const DISCLAIMER = [
  /\bfor (informational|educational|general information)\s+purposes\b[^.]*\.?/gi,
  /\b(this |it )?(is |does )?not (investment|financial|trading|legal|tax)\s+advice\b[^.]*\.?/gi,
  /\bdoes not constitute\b[^.]*\.?/gi,
  /\bnot a (recommendation|solicitation|offer)\b[^.]*\.?/gi,
  /\bdo your own research\b[^.]*\.?/gi,
  /\bpast performance\b[^.]*\.?/gi,
  /\bconsult (a|your|with)\b[^.]*\.?/gi,
];

const BANNED = ["significant", "sharp", "dramatic", "unusual", "extreme", "rare",
  "suggests", "implies", "expected to", "likely to", "investors should",
  "watch for", "not investment advice"];

/** 严链：±120 分钟内、相关度最高的三条。⚠️ start_time/end_time 必填，少了直接 400。 */
async function material(sym, atMs, headers) {
  const t0 = Math.floor(atMs / 1000) - 6 * 3600, t1 = Math.floor(atMs / 1000) + 2 * 3600;
  const r = await http.fetch(
    `${B}/api/v1/stocks/market-news?symbol=${sym}&start_time=${t0}&end_time=${t1}&limit=50`,
    { headers });
  if (!r.ok) return [];
  return ((await r.json()).data || [])
    .map(x => ({ t: Date.parse(x.time_published || x.published_at || x.time || 0),
                 title: x.title, url: x.url,
                 src: x.source || x.source_domain || "",
                 sum: String(x.summary || "").slice(0, 220),
                 rel: +(x.relevance_score || x.relevance || 0) }))
    .filter(x => x.t && x.title && Math.abs(x.t - atMs) <= 120 * 60000)
    .sort((a, b) => b.rel - a.rel).slice(0, 3);
}

/** 比较前规范化：去正负号 · 去千分位 · 去尾随零 · 剥百分号与倍号。 */
function normNum(x) {
  let s = String(x).replace(/,/g, "").replace(/^[+-]/, "").replace(/[%xX×]$/, "");
  if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

/**
 * 一张卡跑一次归因。
 * @returns { attribution, news, checks } —— checks 记录软违规，不拦
 */
async function attribute({ finding, symbol, name, assetClass, headers }) {
  const atMs = Date.parse(finding.triggeredAt);
  const items = await material(symbol, atMs, headers);

  /* ⚠️ 窗口对称，晚于移动的条目照收 —— 新闻天然滞后于它描述的那次移动，
     交易者拿到信息远早于媒体发稿。要求「报道必须早于移动」会把绝大多数真正的
     解释材料滤掉，加密尤其如此。
     （回测覆盖率统计里的 `publish_time ≤ alert_time` 是另一件事：那里要避免
       「涨了才写涨」的循环论证，目的不同，窗口也不同。）
     时差照给，因为它是事实；但规则 4 明令模型不得对它表态 ——
     页面已在每条来源旁印了同一个时差。 */
  const mins = x => {
    const d = Math.round((atMs - x.t) / 60000);
    return d >= 0 ? `${d} minutes before the move` : `${-d} minutes after the move`;
  };
  const MATERIAL = items.length
    ? "\nMATERIAL\n" + items.map((x, i) =>
        `  [${i}] ${new Date(x.t).toISOString().slice(11, 16)} UTC, ${mins(x)}, ${x.src}\n` +
        `      ${x.title}\n      ${x.sum}`).join("\n")
    : "\nMATERIAL none. Retrieval returned nothing for this symbol in the 120 " +
      "minutes either side of the move. Your own search is the only remaining source.";

  const m = finding.measured, tr = finding.trigger, sr = finding.context.sizeRank;
  const bar = tr.unit === "bar";
  /* ⚠️ RANK 的限定词写死在输入里，不指望模型保留它。
     实测：给「1 of 135 bars recorded at 00:30」，模型写回「the top-ranked bar in the sample」。 */
  const rank = !sr ? "not in the top 20 for this slot"
    : bar ? `${ordinal(sr.rank)} largest of the ${sr.of} bars recorded at ${tr.barSlot} UTC — this slot only, not across the day`
          : `${ordinal(sr.rank)} largest of the ${sr.of} sessions on record`;

  const user =
`SYMBOL   ${symbol} (${name}), ${assetClass === "crypto" ? "crypto" : assetClass === "other" ? "ETF" : "US equity"}
MOVE     ${(m.move * 100).toFixed(1)}% on the ${bar ? `${tr.barSlot} UTC 15-minute bar` : "session"}
FIRED    ${bar ? "Intraday price-volume move" : "Price-volume move"}   ${bar ? tr.barSlot + " UTC" : "the close"}   z ${m.z}, RVOL ${m.rvol}x
MARKET   ${assetClass === "crypto" ? "no market benchmark for crypto" : "not computed this run"}
RANK     ${rank}
${MATERIAL}

OUTPUT - read this twice before answering
Return exactly this object, all keys present, nothing before or after it:

{"explanation":"<English, 2 to 3 sentences, at most 220 characters>" or null,"additionalSources":[]}

  explanation  English, or null per rule 8. Must NOT contain any of:
               ${BANNED.join(" · ")}
               Must NOT end with a disclaimer or a follow-up-watchlist sentence.

  additionalSources  anything you searched up yourself. Each needs a real URL you
                     saw in the results. If you did not search, return [].

STEP 1 - SEARCH NOW. Do it before writing anything.

Your first character must be { and your last character must be }.`;

  /* ⚠️ 白名单从**渲染出来的 user 文本**里抓，不从源数据重新格式化。
     第一版是 `[m.move*100, m.z, …].map(v => v.toFixed(2))`，
     而提示词里 MOVE 那行渲染的是 `toFixed(1)` —— 同一个数两处各渲染一次，
     然后拿它们比相等。模型照抄它看到的 `2.2%`，我拿 `2.16` 去比，
     判为「数字不在输入集合内」，**整段解释被自己的硬门丢掉**。
     模型能看到的只有这段文本，所以能引用的也只有这段文本里的数。 */
  const inputNums = [...new Set((user.match(/\d+(?:\.\d+)?/g) || []).map(normNum))];

  let parsed = null, outcome = "ok", raw = "";
  try {
    const res = ask(user, { system: SYSTEM });
    raw = String((res && (res.text || res.output)) || "");
    const j = raw.match(/\{[\s\S]*\}/);        // 剥 ```json 包装
    parsed = j ? JSON.parse(j[0]) : null;
    /* ⚠️ null 是**合法答案**（规则 8），不是解析失败。挤进 parse_failed 就等于
       把「找过了，移动之前没有报道」记成「模型不行」，两件事从此分不开。 */
    if (!parsed || !(typeof parsed.explanation === "string" || parsed.explanation === null))
      outcome = "parse_failed";
    else if (parsed.explanation === null) outcome = "no_material";
  } catch (e) { outcome = "call_failed"; }

  /* ⚠️ 三种结局分开记：成功 · 解析失败 · 规则拦截。
     混进一个「失败」计数，就分不清是模型不行还是解析不行。 */
  const checks = { outcome, banned: [], numbersOutOfSet: [], length: null };
  let explanation = null;
  if (outcome === "no_material") { checks.length = 0; }
  else if (outcome === "ok") {
    const e = parsed.explanation;
    checks.length = e.length;
    checks.banned = BANNED.filter(w => e.toLowerCase().includes(w));
    /* 剥掉免责声明句，剩下的照常显示 —— 比整段丢掉好，也比原样显示诚实。
       ⚠️ 剥了要记下来（`strippedDisclaimer`），静默修改模型输出等于我们替它说话。 */
    let cleaned = e;
    for (const re of DISCLAIMER) cleaned = cleaned.replace(re, "");
    cleaned = cleaned.replace(/\s{2,}/g, " ").replace(/^[\s.;,]+/, "").trim();
    checks.strippedDisclaimer = cleaned !== e;
    if (checks.strippedDisclaimer) parsed.explanation = cleaned;

    /* ⚠️ 钟点时刻:契约明写 summary 里不得出现 —— 它是一个没有渲染层会转换的存储串，
       而卡头已经显示了触发时刻。**提示词里的规则不是保证**:2026-08-23 真跑，
       模型写出「The 05:00 drop came on heavy volume…」。
       剥掉而不是整段丢：时刻之外那句话可能仍然有信息，整段丢是过度反应。 */
    const clockHits = cleaned.match(/\b\d{1,2}:\d{2}\b/g) || [];
    if (clockHits.length) {
      checks.strippedClock = clockHits;
      cleaned = cleaned.replace(/\s*\b\d{1,2}:\d{2}\b\s*/g, " ")
                       .replace(/\s{2,}/g, " ").trim();
      parsed.explanation = cleaned;
    }

    const out = (cleaned.match(/\d+(?:\.\d+)?/g) || []).map(normNum);
    checks.numbersOutOfSet = out.filter(x => !inputNums.includes(x));
    /* 唯一的硬门。⚠️ 只有这一类错误用户自己发现不了 —— 措辞漂了他读得出来。 */
    if (checks.numbersOutOfSet.length) {
      outcome = checks.outcome = "blocked_numbers";
      /* ⚠️ 拦下来要留下拦的是什么。只记「哪几个数越界」而不记原文，
         事后无法判断是模型编了数、还是白名单的渲染口径又漂了 ——
         这两件事都发生过，而症状一模一样。 */
      checks.blockedText = cleaned;
    }
    else explanation = parsed.explanation;
  }

  const extra = ((outcome === "ok" || outcome === "no_material")
                 && parsed && Array.isArray(parsed.additionalSources))
    ? parsed.additionalSources.filter(u => typeof u === "string" && /^https?:\/\//.test(u)) : [];

  /* 来源合并：链路取回的打 chain，模型自搜的打 model。
     ⚠️ timing 只读 chain —— 自搜来源的发布时刻确认不了，不参与判定。 */
  const sources = [
    /* ⚠️ `summary` 与 `source` 必须写进去。端点两个都给了，这里原来只取标题和链接 ——
       页面渲染 .news-sum、自检也要求它存在，于是每一张真实归因卡都会被判
       「a source listed by headline only」。没被发现是因为本地没有归因数据，
       那条自检从来没跑到过：**「跑过」不等于「查了」**。
       对读者的实际后果是，想知道这条标题在说什么就只能离开页面。 */
    ...items.map(x => ({ title: x.title, url: x.url, publishedAt: new Date(x.t).toISOString(),
                         source: x.src || null, summary: x.sum || null, origin: "chain" })),
    ...extra.map(u => ({ title: null, url: u, publishedAt: null,
                         source: null, summary: null, origin: "model" })),
  ];
  /* ⚠️ 无源解释不出街 —— 这是硬门，不只是提示词里的规则。
     实测：材料为空时模型写出「The move came amid a broader crypto rally and short
     squeeze, making market-wide positioning the best available explanation」，
     而 sources 是空的。它读起来像解释，却没有任何读者能打开的东西支撑，
     比一句否定更坏。规则 8 与这道门说的是同一件事，两边都要有：
     只写在提示词里，模型偶尔不照做；只写在代码里，模型不知道为什么被丢。 */
  if (explanation && !sources.length) {
    outcome = checks.outcome = "blocked_unsourced";
    checks.blockedText = explanation;
    explanation = null;
  }

  /* ⚠️ 这里**曾经**有第二道门:`origin === "chain"` 的可核来源为 0 就把整段解释丢掉。
     加了一小时就撤了，理由是它经不起自己的目标案例:

       写它的案例   BTC 那条说「coverage tied it to weekend-thin liquidity and
                    Wintermute short positioning」，而唯一那条来源只讲「较历史高点低 41%」
       门的判据     可核来源条数 > 0
       结果         那条**有** 1 条 chain 来源 → **门放行**。它拦不住写它的理由
       它真能拦的   来源全是模型自搜的情况 —— 而页面每一行都标着「Alva 自行检索」，
                    卡上还印着「相关来源 · N 条」，读者本来就看得见

     一道既解决不了目标案例、又重复了页面已有信息的门，只剩副作用:
     **模型自搜是功能不是泄漏**，而它会把自搜出来的解释整段扔掉。

     ── 代码里留下的判据只有一条：**读者自己发现得了吗** ──

       编造的数字        发现不了（卡上没有那个数，它来自读者看不到的页面）→ 硬门，见上面 blocked_numbers
       交易建议/方向预测   不是质量问题，是边界                        → 提示词 + BANNED 词表
       解释里的钟点       卡头就印着触发时刻                          → 剥掉并留痕，不丢整段
       语气/时序/相关性    读者读得出来                               → 提示词，判在 L5
       说的和来源对不上    要点开链接读才知道                          → **L5 判**，代码判不了语义

     ⚠️ 最后一行是真正的难点，而它恰恰只有 LLM 判官做得了。写在这里，
        是为了让下一个想在这儿再加一道门的人先看到:那道门已经加过一次，
        它拦的不是它想拦的东西。 */

  const chain = sources.filter(x => x.origin === "chain");
  const timing = chain.length
    ? (chain.some(x => Date.parse(x.publishedAt) < atMs) ? "before" : "after")
    : (sources.length ? "untimed" : "none");

  return {
    attribution: { notRun: null, timing, summary: explanation, sources,
                   model: null,                    // ask() 不返回模型名，契约要求置 null
                   generatedAt: new Date().toISOString() },
    checks,
  };
}

function ordinal(n){ const s=["th","st","nd","rd"], v=n%100; return n+(s[(v-20)%10]||s[v]||s[0]); }

module.exports = { attribute, SYSTEM, BANNED, normNum };
