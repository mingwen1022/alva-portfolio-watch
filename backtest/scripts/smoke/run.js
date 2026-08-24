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
           slotBaselines: { "13:30": { med: 0, sigma: 0.003, vmed: 1000, n: 90 } },
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
const CTX = { kv: KV, self: { ts: () => ({ append: async () => {} }) } };

const targets = ["producer.js", "producer-intraday.js", "producer-context.js", "producer-market.js"];
let bad = 0;
(async () => {
  for (const t of targets) {
    global.__FS__ = seed(); global.__WROTE__ = [];
    global.__ARGS__ = { root: "/alva/home/u/playbooks/p", playbookUrl: "https://x/y" };
    global.__CTX__ = CTX;
    global.__HTTP__ = () => [];                 // 取数一律返回空 —— 常态路径
    for (const k of Object.keys(require.cache)) delete require.cache[k];
    try {
      await require(path.join(SK, t));
      await new Promise(r => setTimeout(r, 30));
      console.log(`  ✅ ${t.padEnd(24)} 写了 ${global.__WROTE__.length} 个文件: ${[...new Set(global.__WROTE__)].join(", ") || "（无）"}`);
      if (!global.__WROTE__.length) { console.log(`     ⚠️ 一个文件都没写`); bad++; }
    } catch (e) {
      console.log(`  ❌ ${t.padEnd(24)} ${e.constructor.name}: ${e.message}`);
      if (e.stack) console.log("     " + e.stack.split("\n")[1].trim());
      bad++;
    }
  }
  process.exit(bad ? 1 : 0);
})();
