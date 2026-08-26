/* M 层与 S 层的口径，一处定死。

   ⚠️ 存在理由：这些量原来只有公式、没有代码，每个 agent 自己实现一遍。
   同一条公式有好几个合理但不同的写法，而每一个都不会报错，只会让
   「今天该不该响」在边界上换个答案：

     MAD 用样本还是总体          σ 差约 1%
     窗口含不含当日              极端日会把自己的分母撑大
     简单收益还是对数收益         实测 12 只标的上 26 天触发结果不同
     盘中量能取逐根还是累计       累计口径少 2/3–4/5 的盘中告警

   阈值 1.5 / 2.0 / 3.0 和判据都是在**下面这一份实现**上验出来的。
   换实现就等于换了一套没人验过的规则。 */

/** 简单收益。⚠️ 不是对数收益 —— 验证时用的是这个。 */
function returns(closes) {
  const r = [];
  for (let i = 1; i < closes.length; i++) r.push(closes[i] / closes[i - 1] - 1);
  return r;
}

function median(xs) {
  if (!xs.length) return NaN;
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** 稳健标准差 = 1.4826 × 中位绝对偏差。1.4826 是按正态校准的常数。 */
function robust(xs) {
  const med = median(xs);
  return { med, sigma: 1.4826 * median(xs.map(x => Math.abs(x - med))) };
}

/**
 * 一只标的今天的读数。
 * @param closes  收盘价，**时间正序**，最后一个是今天
 * @param volumes 成交量，与 closes 等长同序
 * @param W       基线窗口，默认 90
 *
 * ⚠️ 两个分母都取「前 W 期，不含当期」。把当期算进自己的基线，
 *    等于把要判它的那个分母撑大 —— 越极端的一天被压得越狠。
 */
function reading(closes, volumes, W = 90) {
  const r = returns(closes);
  if (r.length < W + 1) return null;              // 基线不够，不出读数
  const win = r.slice(-1 - W, -1);                // 前 W 个，不含今天
  const { med, sigma } = robust(win);
  const vmed = median(volumes.slice(-1 - W, -1));
  if (!(sigma > 0) || !(vmed > 0)) return null;
  const today = r[r.length - 1];
  return {
    move: today,
    z: (today - med) / sigma,
    rvol: volumes[volumes.length - 1] / vmed,
    sigma, vmed,
  };
}

/** PV1：两条腿必须同一天各自过线。只过一条不告警。 */
function firedPV1(reading, thetaZ, thetaV) {
  return !!reading && Math.abs(reading.z) >= thetaZ && reading.rvol >= thetaV;
}


/* 美股常规时段的 UTC 窗口。⚠️ 必须按日期算，不能写死常量 ——
   夏令时 09:30–16:00 ET = 13:30–20:00 UTC，标准时 = 14:30–21:00 UTC，
   写死任一个，另外半年整体错一小时：多吃一小时盘前，丢掉收盘前一小时。
   ⚠️「每天 25–26 根」查不出这件事 —— 两个窗口都是 6.5 小时，根数都对。

   平台 runtime 是否带完整 Intl 时区库不保证，所以按规则自己算：
   美国夏令时从三月第二个周日到十一月第一个周日。 */
function nthSundayUTC(year, month, n) {          // month 1-12，返回该月第 n 个周日的日
  const first = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  return 1 + ((7 - first) % 7) + (n - 1) * 7;
}
function isUsDst(dateStr) {                      // "YYYY-MM-DD"
  const [y, m, d] = dateStr.split("-").map(Number);
  if (m < 3 || m > 11) return false;
  if (m > 3 && m < 11) return true;
  return m === 3 ? d >= nthSundayUTC(y, 3, 2) : d < nthSundayUTC(y, 11, 1);
}
/** @returns ["HH:MM","HH:MM") —— 当天 RTH 在 UTC 上的半开区间 */
function rthWindowUTC(dateStr) {
  return isUsDst(dateStr) ? ["13:30", "20:00"] : ["14:30", "21:00"];
}

/** 把某个交易日的 ET 本地时刻拼成带偏移量的 ISO。
    ⚠️ 不要写死 -04:00 —— 标准时是 -05:00，写死的那半年整个时间轴偏一小时。 */
function etStamp(dateStr, hhmmss) {
  return `${dateStr}T${hhmmss}${isUsDst(dateStr) ? "-04:00" : "-05:00"}`;
}


/* ── 逐标的投递上限 ──────────────────────────────────────────────
   契约见 data-contract.md → signalGrades。这里是它的可执行版。

   ⚠️ 平台的 Math.random 不可播种，而契约要求「逐标的播种」——
      否则同一份数据两次运行会给出不同的档位，而档位决定推不推手机。
      所以自带一个 PRNG。mulberry32：32 位状态，周期足够，逐位可复现。 */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/** 逐标的 + 逐信号播种，与处理顺序无关 —— 共用一条随机流会让重排账本改变档位 */
function seedFor(symbol, signalId) {
  let h = 2166136261 >>> 0;
  for (const ch of `${symbol}:${signalId}`) {
    h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}

/** 总体标准差，先减这 F 个自己的均值 */
function pstdev(xs) {
  if (!xs.length) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) * (b - m), 0) / xs.length);
}

/**
 * 判据六步。序列由调用方给定 —— PV1 传日线收盘，PV5 传盘中 bar 收盘。
 * @param closes  收盘序列（与 vols 等长、同序）
 * @param vols    成交量序列
 * @param fired   (i) => bool，第 i 个点触没触发。由调用方按该信号的阈值判定
 * @param W       基线窗
 * @param F       前瞻窗
 * @param B       自助次数
 * @param seed    逐标的逐信号的种子
 */
function grade(closes, vols, fired, { W = 90, F = 5, B = 20000, seed = 7 } = {}) {
  const r = returns(closes);                 // r[i] 是 closes[i+1] 相对 closes[i]
  const n = closes.length;
  const lo = W + 1, hi = n - F;              // 可评估区间：头 W 天没基线，尾 F 天没前瞻
  if (hi - lo < F * 5) return null;          // 连一个块都凑不出，不给结论

  const A = [];                              // 每个可评估日的后 F 日波动
  for (let t = lo; t < hi; t++) {
    const win = [];
    for (let k = 1; k <= F; k++) win.push(r[t + k - 1]);
    A.push({ t, a: pstdev(win) });
  }
  if (!A.length) return null;
  /* ⚠️ 分母是**全部可评估日**的中位，不是「非触发日」的中位 —— 后者会把效应算大 */
  const typ = median(A.map(x => x.a));
  if (!(typ > 0)) return null;

  const T = A.filter(x => fired(x.t));
  const m = T.map(x => x.a / typ);
  if (m.length < 2) return { maxDelivery: "L2", verdict: "insufficient_sample",
                             multiple: m.length ? +m[0].toFixed(3) : null,
                             ci: null, blocks: m.length, days: n };

  let blocks = 0, prev = -Infinity;
  for (const x of T) { if (x.t - prev >= F) blocks++; prev = x.t; }

  const rnd = mulberry32(seed);
  const meds = new Array(B);
  const buf = new Array(m.length);
  for (let b = 0; b < B; b++) {
    for (let i = 0; i < m.length; i++) buf[i] = m[(rnd() * m.length) | 0];
    meds[b] = median(buf);
  }
  meds.sort((a, b) => a - b);
  const q = p => meds[Math.min(meds.length - 1, Math.max(0, Math.floor(p * meds.length)))];
  const ci = [+q(0.025).toFixed(4), +q(0.975).toFixed(4)];
  const multiple = +median(m).toFixed(3);

  const verdict = blocks < 5 ? "insufficient_sample"
                : ci[0] > 1.0 ? "usable" : "effect_unclear";
  return { maxDelivery: verdict === "usable" ? "L1" : "L2",
           verdict, multiple, ci, blocks, days: n };
}

/**
 * 重读 — 合并 — 写回 `findings.json`。
 *
 * ⚠️ **三个 producer 在改同一份文件，而每个都是「开头读一份、跑一堆网络请求、
 *    最后写回」。** 读和写之间隔着整段取数，同分钟内跑的另一个 producer 写进去的
 *    东西会被这一份陈旧快照静默覆盖。
 *
 *    实测（R5 · C-single）：日线 producer 12:18 写了 `scan` 与自己的 `asOf`，
 *    上下文 producer 12:18:20 用它 200 行之前读到的副本写回 —— **`scan` 变回空数组，
 *    `asOf` 退回 init 的时刻**。产物上看是「1 只持仓、扫描 0 只」，
 *    而日线明明跑过（`producedSignals` 里有 PV1）。
 *    症状指向「日线没跑」，而真正的原因在另一个 producer 的写回。
 *
 *    `finally` 那一套在这里不适用：这不是同一进程里的临时状态，
 *    是四个 cronjob 各自的进程在同一份文件上。唯一可靠的做法是
 *    **把读—改—写的窗口压到一次 await 之内**。
 *
 * @param rd    producer 自己的读函数（相对 ROOT）
 * @param wr    producer 自己的写函数
 * @param owns  判断一条 finding 归不归我管；我的会被整批替换，别人的原样留下
 * @param mine  这一轮我产出的 findings
 * @param patch 我拥有的顶层字段（如日线的 asOf / scan / scanned）
 */
async function commitFindings(rd, wr, { owns, mine, patch, scanBar }) {
  const fresh = await rd("data/findings.json").catch(() => ({ findings: [] }));
  const kept = (fresh.findings || []).filter(f => !owns(f));
  fresh.findings = [...kept, ...(mine || [])]
    .sort((a, b) => a.triggeredAt < b.triggeredAt ? -1 : 1);
  /* ⚠️ `scan` 这一行有**两个主人**：日线写会话级读数，盘中往同一行里塞 `bar`。
     日线整体替换 `scan` 会把 `bar` 一起抹成 null —— 表现是持仓表「盘中」那一栏
     整列破折号，看起来像盘中 producer 没跑，而它跑过而且产出了 PV5 finding。
     实测 R6：三只全 `bar: null`，同时 findings 里躺着 SOL 的 PV5。
     按 symbol 把旧的 `bar` 接过来，除非这一轮自己带了新的。 */
  if (patch && Array.isArray(patch.scan)) {
    const prevBar = {};
    for (const r of (fresh.scan || [])) if (r && r.bar != null) prevBar[r.symbol] = r.bar;
    patch.scan = patch.scan.map(r =>
      r.bar === undefined && prevBar[r.symbol] ? { ...r, bar: prevBar[r.symbol] } : r);
  }
  /* 盘中只拥有 `scan[].bar` 这一格，不拥有整行。它必须把这一格贴到**重读后**的行上 ——
     贴在自己开头读的那份副本上，重读一次就全没了（实测:改用重读之后 bar 又变回 null，
     而 PV5 finding 还在，症状和原来的 bug 长得一模一样，只是原因换了一个）。 */
  if (scanBar) {
    for (const r of (fresh.scan || []))
      if (Object.prototype.hasOwnProperty.call(scanBar, r.symbol)) r.bar = scanBar[r.symbol];
  }
  if (patch) Object.assign(fresh, patch);
  await wr("data/findings.json", fresh);
  return fresh;
}

/**
 * 重读 — 合并 — 写回 `meta.json`。与 `commitFindings` 同一个道理，
 * 只是这份文件**四个 producer 全都在改**，比 findings 还挤。
 *
 * ⚠️ 实测（R13 · D-crypto 回归轮）:agent 顺序跑完四个 producer 之后，
 *    `freshness` 里缺 `news` 与 `earningsCalendar` —— 上下文 producer 明明跑过。
 *    单独再跑一次它，两个键立刻就在。也就是说它写进去了，又被后一个 producer
 *    用更早读到的副本盖掉了。
 *    产物上看是「上下文 producer 从没跑过」，而它跑过 —— **症状指向错误的一方**。
 *
 * @param local  producer 自己那份改过的 meta（照旧随便改）
 * @param owned  这个 producer 认领了什么:
 *               keys        整键覆盖（如 attributionRuns）
 *               freshness   认领 freshness 下的哪几个键
 *               signals     并进 producedSignals
 *               gapPrefixes 这些前缀下的 gap 以 local 为准（含删除）；其余原样保留
 */
async function commitMeta(rd, wr, local, owned = {}) {
  const fresh = await rd("data/meta.json").catch(() => ({}));
  for (const k of owned.keys || []) if (local[k] !== undefined) fresh[k] = local[k];
  if ((owned.freshness || []).length) {
    fresh.freshness = Object.assign({}, fresh.freshness);
    for (const k of owned.freshness)
      if ((local.freshness || {})[k]) fresh.freshness[k] = local.freshness[k];
  }
  if ((owned.signals || []).length)
    fresh.producedSignals = [...new Set([...(fresh.producedSignals || []), ...owned.signals])];
  if ((owned.gapPrefixes || []).length) {
    const mine = (pfx, g) => g === pfx || String(g).startsWith(pfx + ":");
    const kept = (fresh.gaps || []).filter(g => !owned.gapPrefixes.some(pfx => mine(pfx, g)));
    const add = (local.gaps || []).filter(g => owned.gapPrefixes.some(pfx => mine(pfx, g)));
    fresh.gaps = [...new Set([...kept, ...add])];
  }
  /* ⚠️ 谁往这份产物里加东西，谁就把 `generatedAt` 推到现在 ——
     契约要求任何 finding 都不能晚于它。 */
  fresh.generatedAt = new Date().toISOString();
  await wr("data/meta.json", fresh);
  return fresh;
}

/* ── 触发记录：一天一族一条 ────────────────────────────────────────────
   ⚠️ 这份记录此前**只有 init 写过**，运行期没有任何 producer 更新它。
      后果实测：DOGE 的 kline 走到 2026-08-25，而 alertHistory 停在 08-21，
      中间至少 4 次 PV5 触发一条都不在里面 —— Tab 2 的历史标记因此系统性少报。

   ⚠️ 一天一条，不是一次一条。图上一天只有一个位置，同一天两条会叠在一起。

   ⚠️ **整天替换，不是增量追加。** 两个 producer 每轮都重新评估当天全部的 bar，
      手里本来就是当天的完整名单 —— 整天替换是幂等的，追加不是：
      盘中每 15 分钟跑一次，追加会让同一根 bar 被记 96 遍。

   ⚠️ `n` 与 `bars.length` 常态就不相等，这是**声明出来的**，不是缺陷：
      加密一天最多响 96 次，明细不可能全存。
        n     = 当天真实触发次数
        bars  = 其中最强的 BARS_KEPT 根（按 |z| 取）
      让两个数不等这件事写在契约里，比留给读者自己发现好。 */
const BARS_KEPT = 8;

/** 把一天的记录并进 doc.alertHistory，并按 kline 的窗口裁掉过老的条目。 */
function upsertAlertHistory(doc, entry) {
  if (!doc || !entry || !entry.d || !entry.signalId) return doc;
  const rest = (doc.alertHistory || [])
    .filter(h => !(h && h.d === entry.d && h.signalId === entry.signalId));
  /* 只保留画得出来的那一段：页面本来就会丢掉 kline 里没有的日期，
     留着它们既没用，又会让「记录里有几条」和「图上标了几个」对不上。 */
  const first = (doc.kline || []).length ? doc.kline[0].d : null;
  const all = [...rest, entry]
    .filter(h => !first || h.d >= first)
    .sort((x, y) => x.d < y.d ? -1 : x.d > y.d ? 1 : (x.signalId < y.signalId ? -1 : 1));
  doc.alertHistory = all;
  return doc;
}

/** 当天所有触发的 bar → 一条 PV5 记录。传进来的必须是**当天的完整名单**。 */
function pv5DayEntry(day, bars) {
  if (!bars || !bars.length) return null;
  const sorted = [...bars].sort((a, b) => Math.abs(b.z) - Math.abs(a.z));
  const top = sorted[0];
  return { d: day, signalId: "PV5", n: bars.length,
           z: top.z, rvol: top.rvol,
           bars: sorted.slice(0, BARS_KEPT)
                       .sort((a, b) => String(a.slot) < String(b.slot) ? -1 : 1) };
}

/** alertHistory → 计数。⚠️ 计数不再单独存 —— 同一件事存两份，
    其中一份被补过、另一份没补，就是自检报「对不上」的那个根因。 */
function countTriggers(doc, windowSessions) {
  const ah = (doc && doc.alertHistory) || [];
  const kl = (doc && doc.kline) || [];
  const last7 = new Set(kl.slice(-7).map(k => k.d));
  const of = id => ah.filter(h => h.signalId === id);
  return { PV1: of("PV1").length, PV5: of("PV5").length,
           windowSessions: windowSessions != null ? windowSessions : (kl.length || null),
           last7: { PV1: of("PV1").filter(h => last7.has(h.d)).length,
                    PV5: of("PV5").filter(h => last7.has(h.d)).length } };
}

module.exports = { grade, pstdev, mulberry32, seedFor, etStamp, rthWindowUTC, isUsDst, returns, median, robust, pstdev, reading, firedPV1, commitFindings, commitMeta, upsertAlertHistory, pv5DayEntry, countTriggers, BARS_KEPT };
