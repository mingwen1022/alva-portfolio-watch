/* 在桩环境里真的执行每个 producer。
   ⚠️ 这里的 feed.run **不吞异常** —— 平台上它吞，于是抛错的那一轮报 completed、
      日志为空、一个字都没写，而看状态永远发现不了。本 session 因此撞了三次
      暂时性死区（attrLog · spyMove · SIGDEF），每次都是靠事后查产物才发现的。
   跑一遍就能抓到：加载期错误、声明前使用、字段名写错、空数据路径上的崩溃。 */
const path = require("path"), fs = require("fs");
/* 把交付脚本拷到桩旁边再跑 —— node 按「被 require 的模块所在目录」解析依赖，
   而且这样顺带验了它们相互之间是自包含的（只依赖同目录的兄弟文件）。 */
const SRC = path.resolve(__dirname, "../../../skill/scripts");
const SK = path.join(__dirname, "_scripts");
fs.rmSync(SK, { recursive: true, force: true }); fs.mkdirSync(SK, { recursive: true });
for (const f of fs.readdirSync(SRC)) if (f.endsWith(".js")) fs.copyFileSync(path.join(SRC, f), path.join(SK, f));
fs.symlinkSync(path.join(__dirname, "node_modules"), path.join(SK, "node_modules"), "dir");

/* 最小但结构合法的账本 —— 走「没有行情数据」那条路径，
   任何一个 producer 在这条路径上崩，都是真 bug（取数失败是常态，不是异常）。 */
const seed = () => ({
  "data/portfolio.json": JSON.stringify({ linked: true, cash: 100, asOf: "2026-08-23T16:00:00-04:00",
    kpi: { totalValue: 100, totalPnl: null, todayPnl: null, fromHigh: null },
    holdings: [{ symbol: "AAA", name: "AAA", assetClass: "us_equity", last: 10,
                 shares: 5, avgCost: 8, value: 50, weight: 0.5, lifetimePnl: 10,
                 fromHighPct: -0.1, spark: [], notes: [] },
               { symbol: "BBB", name: "BBB", assetClass: "crypto", last: 2,
                 shares: 10, avgCost: 1, value: 20, weight: 0.2, lifetimePnl: 10,
                 fromHighPct: -0.2, spark: [], notes: [] }],
    allocation: { byHolding: [], byAssetClass: [], byTheme: [] }, checks: [] }),
  "data/baselines.json": JSON.stringify({
    AAA: { sigmaRobust: 0.02, sigmaAnn: 0.3, baselineDays: 500, usable: true,
           m23: { rho: 0.15, verdict: "pass", n: 504 },
           thresholds: { theta_z: 1.5, theta_v: 2.0, theta_z_bar: 4.75, theta_v_bar: 2.0, source: "validated" },
           signalGrades: { PV1: { maxDelivery: "L1", verdict: "usable" } },
           /* ⚠️ 两个槽位。盘中的循环从 i=1 起（第一根没有前收，算不出收益率），
              所以**被判定的是第二根** —— 只给 13:30 一个基线时，
              喂进去的第二根 13:45 查不到线，整轮静默跳过。 */
           slotBaselines: { "13:30": { med: 0, sigma: 0.003, vmed: 1000, n: 90 },
                            "13:45": { med: 0, sigma: 0.003, vmed: 1000, n: 90 } },
           distributionBar: { slots: {} }, triggerLine: {}, historicalTriggers: {}, degraded: null },
    BBB: { sigmaRobust: 0.05, sigmaAnn: 0.9, baselineDays: 500, usable: true,
           m23: { rho: 0.18, verdict: "pass", n: 504 },
           thresholds: { theta_z: 1.5, theta_v: 3.0, theta_z_bar: 10.0, theta_v_bar: 3.0, source: "validated" },
           signalGrades: {}, slotBaselines: {}, distributionBar: { slots: {} },
           triggerLine: {}, historicalTriggers: {}, degraded: null } }),
  "data/findings.json": JSON.stringify({ asOf: "2026-08-23T16:00:00-04:00", findings: [], scan: [] }),
  "data/meta.json": JSON.stringify({ generatedAt: "2026-08-23T16:00:00-04:00", gaps: [], freshness: {} }),
  "data/state.json": JSON.stringify({ keys: {} }),
  "data/signals.json": JSON.stringify({ signals: {
    PV1: { maxDelivery: "L1" }, PV5: { maxDelivery: "L1" }, US1: { maxDelivery: "L1" },
    US2: { maxDelivery: "L1" }, US3: { maxDelivery: "L1" }, EV1: { maxDelivery: "L3" },
    EV4: { maxDelivery: "L1" }, DR1: { maxDelivery: "L3" } } }),
  "config/alerts.json": JSON.stringify({ userLines: { AAA: { US1: 20 } },
    enabled: {}, channels: { push: true }, attribution: { dailyCap: 10 } }),
  "data/market.json": JSON.stringify({ indices: [], commodities: [], treasury: null,
    crypto: {}, earningsWeek: [] }),
  "symbols/AAA.json": JSON.stringify({ symbol: "AAA" }),
  "symbols/BBB.json": JSON.stringify({ symbol: "BBB" }),
});

const KV = { load: async () => "{}", put: async () => {} };
/* ⚠️ `append` 原来是空函数 —— **推送正文从来没被任何检查看过**，
   而推送是唯一会打断用户的出口。实测 2026-08-25：EV4 的推送把端点的内部码
   直接拼了进去，手机上印出「NVDA 2026-08-26 amc」。页面早有对应文案
   （before open / after close），只有这一路没有。截获下来才查得了。 */
let PUSHED = [];
const CTX = { kv: KV, self: { ts: () => ({ append: async xs => { PUSHED.push(...xs); } }) } };

const targets = ["producer.js", "producer-intraday.js", "producer-context.js", "producer-market.js"];
let bad = 0;
(async () => {
  for (const t of targets) {
    global.__FS__ = seed(); global.__WROTE__ = []; PUSHED = [];
    global.__ARGS__ = { root: "/alva/home/u/playbooks/p", playbookUrl: "https://x/y" };
    global.__CTX__ = CTX;
    /* 取数默认返回空（常态路径）。⚠️ 唯独财报日历给一条**明天**的记录 ——
       否则 EV4 永远不推，下面那条推送文案检查就是个不会失败的断言。
       `time` 故意用端点的原始码 `amc`：要测的正是「它有没有被翻成人话」。 */
    /* ⚠️ 从**种子自己的 asOf** 推，不用真实的今天。种子把 asOf 钉在 2026-08-23，
       第一版用 `Date.now()+1d` 拿到的是真实的明天，两者差好几天，
       EV4 的「≤1 个交易日」当场不成立 —— 于是这条推送检查静默地没求值。
       日期只有一处来源，就不会再错开。 */
    const _seedAsOf = JSON.parse(global.__FS__["data/portfolio.json"]).asOf.slice(0, 10);
    const _tmr = new Date(Date.parse(_seedAsOf + "T00:00:00Z") + 86400000)
      .toISOString().slice(0, 10);
    /* ⚠️ 盘中也要喂 —— 否则 PV5 永不触发，`alertHistory` 的写入路径
       在桩里一次都走不到。实测 2026-08-26：线上那一轮评估了 68 根、全部 quiet，
       「没写」和「写不了」长得一模一样，只能在这里分开。
       AAA 的槽位基线是 13:30（σ=0.003 · vmed=1000），θz_bar=4.75 · θv_bar=2.0，
       所以第二根给 +3%（z=10）和 5000 手（rvol=5）—— 两条腿都过。 */
    const _d0 = _seedAsOf;
    global.__HTTP__ = url => {
      const u = String(url);
      if (/earnings-calendar/.test(u)) return [{ date: _tmr, time: "amc" }];
      if (/interval=15min/.test(u)) return [
        { time_period_start: _d0 + "T13:30:00", price_close: 100, volume_traded: 1000 },
        { time_period_start: _d0 + "T13:45:00", price_close: 103, volume_traded: 5000 },
      ];
      return [];
    };
    for (const k of Object.keys(require.cache)) delete require.cache[k];
    try {
      await require(path.join(SK, t));
      await new Promise(r => setTimeout(r, 30));
      console.log(`  ✅ ${t.padEnd(24)} 写了 ${global.__WROTE__.length} 个文件: ${[...new Set(global.__WROTE__)].join(", ") || "（无）"}`);
      if (!global.__WROTE__.length) { console.log(`     ⚠️ 一个文件都没写`); bad++; }
      /* ⚠️ 触发记录必须真的被写进去。此前 alertHistory **只有 init 写过**，
         运行期没人更新，Tab 2 的历史标记因此停在初始化那天。
         桩里喂了一根必然触发的 13:45（z=10 · rvol=5），所以这条断言不是空跑。
         ⚠️ 键是**路径最后两段**（见 alfs 桩），不是 `data/symbols/…` ——
            第一次就是这里探错，读到 undefined 还以为功能没生效。 */
      if (t === "producer-intraday.js") {
        const doc = JSON.parse(global.__FS__["symbols/AAA.json"] || "{}");
        const e = (doc.alertHistory || []).find(h => h.signalId === "PV5");
        if (!e) { console.log("     ❌ PV5 触发了却没写进 alertHistory"); bad++; }
        else if (e.n !== (e.bars || []).length && (e.bars || []).length !== 8) {
          console.log(`     ❌ n=${e.n} 与 bars=${(e.bars||[]).length} 不符（未截断时应相等）`); bad++;
        } else console.log(`     ✅ alertHistory 已续: ${e.d} PV5 n=${e.n} bars=${(e.bars||[]).length}`);
      }
      /* ⚠️ 推送正文里不许出现内部码。判据是「这个词是给机器看的还是给人看的」：
         端点的 bmo/amc、契约的 us_equity、投递层级 L1–L4、来源 origin 的 chain/model、
         裸信号 ID —— 页面对每一个都有名字，推送这一路此前一个都没有。
         ⚠️ 只在**真的推了**的时候才判，并把捕获条数印出来 ——
            0 条要看得见，否则「查过了没问题」和「压根没推」长得一样。 */
      if (PUSHED.length) {
        const CODES = /(^|[^A-Za-z])(bmo|amc|us_equity|L[1-4]|chain|model|PV[1-5]|EV[1-6]|US[1-3]|DR[1-4]|MA[1-3]|PO[1-4]|PF[1-3])([^A-Za-z]|$)/;
        const leak = PUSHED.map(x => String(x.body || "")).filter(b2 => CODES.test(b2));
        if (leak.length) {
          console.log(`     ❌ 推送正文里有内部码: 「${leak[0].replace(/\n/g, " ⏎ ").slice(0, 90)}」`);
          bad++;
        } else console.log(`     ✅ 推送 ${PUSHED.length} 条，正文无内部码`);
      } else console.log(`     —  这一轮没有推送（本判据未求值）`);
    } catch (e) {
      console.log(`  ❌ ${t.padEnd(24)} ${e.constructor.name}: ${e.message}`);
      if (e.stack) console.log("     " + e.stack.split("\n")[1].trim());
      bad++;
    }
  }
  process.exit(bad ? 1 : 0);
})();
