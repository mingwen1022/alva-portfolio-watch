/* US1 / US2 / US3 — the user's own lines.
 *
 * Shared by the daily and intraday producers on purpose. The same family was already
 * duplicated once in this system (deliveryOf) and the two copies drifted, so there is one
 * implementation and both callers use it.
 *
 * These are STATE-kind signals, not events. The difference is the whole file: an event
 * cannot become false, a state can, so a state needs one bit of memory per line and has to
 * say "cleared" out loud when it flips back.
 */

const KIND = {
  US1: (price, drawdown, v) => price <= v,      // stop line
  US2: (price, drawdown, v) => price >= v,      // take-profit line
  US3: (price, drawdown, v) => drawdown <= v,   // drawdown line, v is negative
};

/**
 * @param holdings  portfolio.holdings — needs symbol · last · fromHighPct · assetClass · todayPct
 * @param userLines config/alerts.json userLines, { SYM: { US1: 125.0 } }
 * @param enabled   config/alerts.json enabled
 * @param prevKeys  state.json keys from the previous run (read-modify-write)
 * @param nowIso    this run's instant, offset-bearing
 * ⚠️ unit is always "line". `session` belongs to PV1 and `bar` to PV5 — the contract
 *    asserts it, and a user line is neither tier of a price-volume measurement.
 * @returns { findings, keys, pushable }
 */
function evaluate({ holdings, userLines, enabled, prevKeys, nowIso }) {
  const unit = "line";
  const H = {};
  for (const h of holdings) H[h.symbol] = h;
  const day = nowIso.slice(0, 10);
  const keys = Object.assign({}, prevKeys || {});
  const findings = [], pushable = [];

  for (const sym of Object.keys(userLines || {})) {
    const h = H[sym];
    if (!h) continue;                       // line on a symbol no longer held
    for (const sig of Object.keys(userLines[sym])) {
      if (!KIND[sig]) continue;
      if (enabled && enabled[sig] === false) continue;
      const v = userLines[sym][sig];
      if (typeof v !== "number") continue;

      const key = `${sym}:${sig}`;
      let st = keys[key];

      /* ⚠️ Re-arm when the user edits the line. A changed value is a new rule, and the old
         "already pushed" must not swallow the new line's first crossing. */
      if (st && st.armedFor !== v) st = null;

      /* ⚠️ `null <= 125` 在 JS 里是 true。取数失败的标的 last 是 null，
         不设这道门会产出一条 severity critical、L1、actual 为 null 的告警。 */
      const price = h.last, drawdown = h.fromHighPct;
      const need = sig === "US3" ? drawdown : price;
      if (typeof need !== "number" || !Number.isFinite(need)) continue;
      const on = KIND[sig](price, drawdown, v);
      const was = !!(st && st.on);
      const actual = sig === "US3" ? drawdown : price;

      if (on) {
        /* first crossing pushes; a continuation does not */
        const novelty = was ? 0 : 1.0;
        const since = was ? st.since : nowIso;
        keys[key] = { on: true, since, armedFor: v,
                      lastPush: novelty ? nowIso : (st ? st.lastPush : null),
                      clearedAt: null };
        const f = mkFinding({ sym, sig, h, v, actual, nowIso, day, unit, novelty, since });
        findings.push(f);
        if (novelty) pushable.push(f);
      } else if (was) {
        /* ⚠️ Stay one more period, labelled cleared, before leaving. Otherwise the user who
           set a stop, got a push, and opens the app that evening finds nothing — and
           "it recovered" looks exactly like "the system is broken" on an empty list. */
        keys[key] = { on: false, since: st.since, armedFor: v,
                      lastPush: st.lastPush, clearedAt: nowIso };
        const f = mkFinding({ sym, sig, h, v, actual, nowIso, day, unit,
                              novelty: 0, since: st.since });
        f.clearedAt = nowIso;
        findings.push(f);
      } else if (st && st.clearedAt) {
        delete keys[key];                   // the cleared card had its period; drop it
      } else if (!st) {
        keys[key] = { on: false, since: null, armedFor: v, lastPush: null, clearedAt: null };
      }
    }
  }

  /* a line whose symbol or config entry is gone leaves no orphan state behind */
  const UL = userLines || {};
  for (const key of Object.keys(keys)) {
    const [sym, sig] = key.split(":");
    if (!KIND[sig]) continue;
    /* 标的从账本里移除也要清 —— 否则开关位以 on:true 留着，
       将来重新加回时 was 仍为 true，novelty 变 0，那次跨越永远不推。 */
    if (!H[sym] || !UL[sym] || typeof UL[sym][sig] !== "number") delete keys[key];
  }

  return { findings, keys, pushable };
}

function mkFinding({ sym, sig, h, v, actual, nowIso, day, unit, novelty, since }) {
  return {
    id: `${day}:${sym}:${sig}`,
    symbol: sym,
    assetClass: h.assetClass,
    signalId: sig,
    unit,
    /* Critical for the whole family, and never downgraded — the user drew this line, and we
       have no standing to hold it back with our own evidence rules. */
    severity: "critical",
    triggeredAt: nowIso,
    knownAt: nowIso,
    episodeId: `${day}:${sym}`,
    novelty,
    priority: novelty ? 3 * (h.weight == null ? 1 : h.weight) : 0,
    measured: { z: null, rvol: null, move: h.todayPct == null ? null : h.todayPct },
    trigger: {
      unit,
      moveAt: nowIso,
      thresholdSource: "user_set",
      barSlot: null,
      barClose: null,
      /* the page renders the card from this; without it the card falls through to the
         price-volume branch, looks for rvol, and throws inside a click handler */
      userLine: { kind: sig, value: v, actual: round5(actual), since },
    },
    delivery: { level: "L1", cappedBy: null },
    context: {
      sizeRank: null,
      benchmark: { symbol: null, benchmarkMove: null, symbolMove: null, applicable: false },
      pnl: null,
      /* ⚠️ 用户线从不做归因，所以整个键缺省 —— 不能写
         `{notRun:null, timing:"none"}`，那两个值合起来的意思是
         「我们找过了，今天没有相关报道」，而我们根本没找过。
         契约的 eval 也断言用户线不带 attribution。 */
    },
  };
}

function round5(x) { return x == null ? null : Math.round(x * 1e5) / 1e5; }

module.exports = { evaluate, KIND };
