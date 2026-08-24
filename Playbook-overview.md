# Playbook overview

The Playbook this Skill generates consists of four tabs, four scheduled jobs, and a
delivery rule that decides which alerts reach a phone. This document describes what each
part carries and how alerts are judged and delivered. Full signal definitions are in
[`product/signal-spec.md`](product/signal-spec.md); the per-block interface spec is in
[`product/content-spec.md`](product/content-spec.md).

[中文版](Playbook介绍.md)

---

## The four tabs

Tabs are divided by what the content *is*, not by delivery tier. Delivery tier answers a
different question, which touchpoint something is sent to, and the two are separate
dimensions. Anything pushable appears on the first screen; not everything on the first
screen is pushable.

| Tab | Content | Basis for inclusion |
|---|---|---|
| **1 · Holdings & Alerts** | Alert stream · today's scan · portfolio totals · allocation across three cuts · equity curve · holdings table · news and earnings calendar | Validated content, eligible for the first screen |
| **2 · Symbol Detail & Alert History** | One symbol at a time: two years of candles with past triggers marked · insider filings · earnings · related news | Objective facts, organised per symbol |
| **3 · Market** | Indices · volatility · rates · commodities · crypto sentiment · market-wide earnings calendar | Objective data, **not a signal source** |
| **4 · Method** | What counts as a move · what was rejected · how concurrent signals are ordered · capability boundaries | The reasoning and its limits |

Nothing in Tab 3 participates in trigger evaluation. It exists so the reader knows the
day's market backdrop, not to add a signal source. The macro family (MA1 · MA2) was
falsified in backtesting, and presenting market data as a signal would contradict that
result.

Tab 1 shows the day's scan readings even on days with zero alerts. **No alerts and no run
are two different states**, and the scan table is the only evidence the engine ran.

---

## What counts as a move

Price and volume must both cross that symbol's own lines within the same session. One
without the other is not an alert.

| Signal | Price condition | Volume condition |
|---|---|---|
| **PV1 · daily** | robust \|z\| ≥ 1.5 | RVOL ≥ 2.0 (US equities) / 3.0 (crypto) |
| **PV5 · intraday 15-min** | same-slot \|z\| ≥ 4.75 (US) / 10.0 (crypto) | RVOL ≥ 2.0 / 3.0 |

Lines come from the symbol's own history: robust σ over 90 sessions, and for intraday,
over the past 90 samples of that same time of day (e.g. every 09:45). The same percentage
is not the same event across symbols: 1.5% is a move for KO and is inside the noise for
DOGE.

Thresholds are fixed values rather than rolling quantiles. A rolling quantile lets the
definition of "unusual" drift with the market itself, which classifies genuine moves as
normal during volatile periods.

AND is used rather than the platform's suggested OR. The basis is trigger volume, not a
difference in effect: at matched trigger counts the two are indistinguishable
(p = 0.70–0.84), while OR produces 5.96× as many trigger days, 5.6 per week versus 1.0
for a five-symbol book. That basis flips sign under all six split-half specifications, so
its evidence grade is capped at "unverified".

---

## What counts as noise

A single criterion:

```
realised volatility over the 5 sessions after a trigger ÷ the median of an ordinary
5-session window  →  relative baseline multiple

lower bound of the 95% bootstrap interval > 1.0   ∧   independent episodes ≥ 5
```

Computed per symbol; pooling across symbols is not permitted. Trigger frequency,
magnitude, and hit rate are descriptive quantities and do not enter the criterion.

21 alert candidates were tested against it. One passed:

| Result | Signals |
|---|---|
| Passed | PV1 |
| Cleanly falsified | MA1 0/16 · MA2 0/16 · EV2 0/56 · EV5 1/44 · DR3 no dose response |
| Real but too small | EV3 median multiple 1.117 against PV1's 1.49; unusable per symbol |
| Insufficient sample or not reusable | DR1 (threshold varies 6× across symbols) · DR2 · EV1 |
| Data blocked | EV4 calendar depth 1.6 years · MA3 no FOMC calendar endpoint |

Falsified signals do not appear in the interface and are not carried in the alert stream.
Their experimental records are kept in
[`backtest/signal-registry.md`](backtest/signal-registry.md).

---

## Ordering when several signals fire at once

Ordering is by delivery ceiling, not by signal type. Each alert passes three ceilings and
the strictest one applies:

| Ceiling | Meaning |
|---|---|
| `symbol_grade` | Has this rule been validated on this symbol |
| `degraded` | Is this symbol in a high-volatility state |
| `signal_evidence` | The evidence grade of the signal itself |

The result maps to four delivery tiers:

```
L1   phone push
L2   overview alert stream
L3   holdings page
L4   record page
```

**A missing grade is treated as capped, not as passing.** No grade means nobody measured
whether the rule holds on that symbol, and failing open would let an unvalidated signal
reach the phone.

In the interface, a symbol whose delivery is capped carries a dot beside its logo; the
tooltip names which rule is capped and why. No dot means both price-volume rules on that
symbol are eligible to push.

### User-set lines are exempt from all three ceilings

Stop (US1), take-profit (US2), and drawdown (US3) lines set by the user **bypass all three
ceilings** and always deliver at L1. They are the user's instruction, not the system's
judgement. Insufficient evidence about a symbol is not a reason to suppress an
instruction.

---

## The four scheduled jobs

| Job | Frequency | Output |
|---|---|---|
| Daily | after each session close | PV1 · scan readings · holdings valuation · equity curve extension |
| Intraday | every 15 minutes | PV5 · user lines · intraday price refresh |
| Pre-market | before each session | news · earnings calendar · insider filings · funding rates |
| Market | hourly | indices · rates · commodities · crypto sentiment |

Initialization runs once and produces baselines, per-symbol grades, a replay of historical
triggers, and the nine files the page requires. Baselines belong to initialization; the
runtime only fetches the current day. Thresholds are locked when the baseline is built and
are not re-solved afterwards.

---

## Alert detail and attribution

Every alert in the stream opens into a detail dialog that lays out what the judgement rests
on: why it was worth a push (or, for a capped alert, why it was not), the moment it fired,
a price chart of the bars around the trigger with the trigger marked, the market over the
same window, where this move sits in the symbol's own history of moves, and the position's
weight and P&L. The dialog steps to the previous or next alert without returning to the list.

Alerts that reach L1 carry a written explanation: a retrieval-backed model call looks for a
possible account among news items matched within a time window.

Its boundaries are stated on the alert card:

- It offers a **possible reading**, not an assertion of cause
- When no source matches it says so, rather than leaving the field blank. "Not asked" and
  "asked and found nothing" are different states
- A daily quota applies; alerts beyond it still carry sources and computed context, but no
  written paragraph
- It never predicts direction and never gives trading advice

---

## Degraded states in the interface

| Condition | Presentation |
|---|---|
| No linked account | Amounts, P&L, and the equity curve are withheld as a block, with a note that these require an account. Alerts are unaffected |
| Baseline under 60 sessions | No readings for that symbol; shows "day N since listing" rather than computing a number anyway |
| Unvalidated asset class (ETFs and similar) | Marked `unvalidated`; thresholds are solved from a pool of the same class, and the evidence grade may not display as green |
| A producer has not run | The affected block states the gap rather than rendering blank; blank is indistinguishable from "nothing today" |
