/* Map a linked brokerage account into this product's portfolio shape.
 *
 * The broker's schema is NOT this contract's schema — see
 * references/data-contract.md -> Mapping a linked brokerage account. Four differences are
 * load-bearing, and three of them produce a wrong number rather than a missing one:
 *
 *   money values are objects, not numbers
 *   `side: "SHORT"` inverts P/L and we have no field for it
 *   currency is per-value, so a mixed account sums apples and oranges
 *   the balance and the positions carry different timestamps
 *
 * This module refuses what it cannot represent and says why, rather than computing something
 * that looks reasonable. Everything it skips lands in `gaps`.
 */

/** money objects come as { amount, currency, currencySymbol } */
function amt(m) {
  if (m == null) return null;
  if (typeof m === "number") return m;
  return typeof m.amount === "number" ? m.amount : null;
}
function cur(m) { return (m && m.currency) || null; }

/**
 * @param summary  the object returned by `alva portfolio summary`
 * @returns { portfolio, gaps }  portfolio is partial — the caller derives name, assetClass,
 *           logo, todayPct, vol30d, fromHighPct and spark from market data
 */
function fromBrokerSummary(summary) {
  const gaps = [];
  const baseCur = cur(summary.totalValue) || "USD";

  const shorts = [], foreign = [], unusable = [];
  const holdings = [];

  for (const h of (summary.holdings || [])) {
    /* ⚠️ A short carries a positive quantity with inverted P/L, so the contract's
       `value − shares × avgCost` gets the SIGN wrong. Skipping and saying so is honest;
       including it is a wrong number presented as a right one. */
    if (h.side && h.side !== "LONG") { shorts.push(h.symbol); continue; }

    /* ⚠️ Every total in this contract is a bare number, so two currencies cannot both be in
       it. Adding them produces a figure that means nothing and looks fine. */
    const hc = cur(h.marketValue) || cur(h.currentPrice) || baseCur;
    if (hc !== baseCur) { foreign.push(`${h.symbol}:${hc}`); continue; }

    const shares = typeof h.quantity === "number" ? h.quantity : null;
    const avgCost = amt(h.avgCost);
    const last = amt(h.currentPrice);
    const value = amt(h.marketValue);
    if (shares == null || last == null) { unusable.push(h.symbol); continue; }

    holdings.push({
      symbol: h.symbol,
      shares,
      avgCost,
      last,
      value,
      /* the broker already computed this; on a margin account it is one of two possible
         definitions, so record where it came from rather than recomputing */
      weight: typeof h.allocation === "number" ? +h.allocation.toFixed(4) : null,
      lifetimePnl: (value != null && avgCost != null) ? +(value - shares * avgCost).toFixed(2) : null,
    });
  }

  if (shorts.length)   gaps.push("short_positions_unsupported:" + shorts.join(","));
  if (foreign.length)  gaps.push("multi_currency_unsupported:" + foreign.join(","));
  if (unusable.length) gaps.push("holdings_missing_fields:" + unusable.join(","));

  const iso = ms => (typeof ms === "number" ? new Date(ms).toISOString() : null);

  return {
    portfolio: {
      linked: true,
      /* ⚠️ Authoritative. Never recompute as Σ value + cash — the broker's figure carries
         dividends, fees and same-day cash movements this module cannot see, and a recomputed
         total drifts from it while both are labelled "total value". */
      cash: amt(summary.cash),
      kpi: { totalValue: amt(summary.totalValue) },
      currency: baseCur,
      weightSource: "broker",
      holdings,
      /* ⚠️ Two instants. The balance and the positions are as of different times, and one
         field cannot state both — the same error as one asOf over a mixed equity/crypto book. */
      asOf: iso(summary.asOfMs),
      positionsAsOf: iso(summary.positionsAsOfMs),
      /* ⚠️ The broker's price lags the market. Signals run on kline data, so this and a
         signal's "today" can legitimately disagree; the page must say so rather than
         force them to match. */
      lastSource: "broker",
    },
    gaps,
  };
}

module.exports = { fromBrokerSummary, amt };
