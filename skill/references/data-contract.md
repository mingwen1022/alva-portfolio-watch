# Data contract

The files a run must write, and every field the page reads. The page computes nothing — if a
number appears on screen, it came from here.

Signals and thresholds are in `signal-spec.md`. Endpoints are in `data-sources.md`.

## File layout

```
~/playbooks/<name>/
  config/
    alerts.json          user configuration — the only writable file
  data/
    signals.json         signal catalogue, generated from signal-spec
    findings.json        today's findings, overwritten every run
    portfolio.json       holdings, KPI, allocation
    series.json          equity curve
    news.json            today's related news
    baselines.json       per-symbol baselines
    market.json          tab 3
    symbols/<SYM>.json   tab 2, one file per symbol
    state.json           cross-run state — dedup, cooldowns, state-kind bits
    meta.json            run time, freshness, known gaps
```

**`meta.json` lives in `data/`, not at the playbook root.** The page fetches
`data/meta.json`; a root-level copy is never read and never errors under a local static server.

**`state.json` is the only read-modify-write file.** Read the previous run's content and merge.
Overwriting it loses dedup keys and cooldown timestamps.

## data/state.json

```json
{
  "asOf": "2026-08-21T16:00:00-04:00",
  "keys": {
    "MSTR:US1": { "on": true,  "since": "2026-08-19T14:22:00-04:00",
                  "lastPush": "2026-08-19T14:22:00-04:00", "clearedAt": null,
                  "armedFor": 125.0 },
    "SOUN:US3": { "on": false, "since": "2026-08-14T16:00:00-04:00",
                  "lastPush": "2026-08-14T16:00:00-04:00",
                  "clearedAt": "2026-08-21T16:00:00-04:00", "armedFor": -0.20 }
  }
}
```

| Field | Meaning |
|---|---|
| key | `"<symbol>:<signalId>"` |
| `on` | whether the condition holds this run. Meaningful for state-kind only; always false for event-kind |
| `since` | start of the current unbroken run of truth. Cleared on reversal |
| `lastPush` | when a push actually reached a phone — dedup and cooldown both read this |
| `clearedAt` | when the reversal happened. Keep one more period, then delete the key |
| `armedFor` | the user line value this key was armed at |

**`lastPush` means "pushed", not "computed".** A signal capped at L2 is computed daily and
never pushed; using it for dedup swallows the first push after a promotion to L1.

**`armedFor` resets the whole key when the value changes.** A changed line is a new rule, and
the old "already pushed" must not suppress its first trigger.

**Prune, or the file grows without bound.** Delete a key when `clearedAt` is set and a period
has passed, or when `lastPush` is older than the longest cooldown (45 calendar days).

## data/signals.json

Generated from `signal-spec.md`, never hand-written. **All 13 signals, always.**

```json
{
  "generatedFrom": "signal-spec.md@<sha>",
  "signals": {
    "PV1": {
      "name":        { "zh": "价量异动 · 日线", "en": "Price-volume move · daily" },
      "type":        "alert",
      "assetClass":  ["us_equity", "crypto"],
      "granularity": "daily",
      "evidence":    "green",
      "severity":    "critical",
      "maxDelivery": "L1",
      "pushable":    true
    }
  }
}
```

`type` — `alert` enters the stream · `display` page only · `record` · `calendar` · `attribution`
`evidence` — `green` · `amber` (tested, criterion not met) · `red` · `blue` (cited) · `yellow` · `white` · `na`
`assetClass` — `us_equity` · `crypto` · `other`

Signals that apply to `other`: PV1 · PV3 · PV4 · US1 · US2 · US3. Not PV5 (no intraday
fallback), not EV1 / EV4 / EV6 (an ETF has no insiders, earnings or company news), not DR1.

**This one file serves three consumers**: the page's type labels, the page's own ID-whitelist
audit, and the eval whitelist assertion. Names are written once so the three cannot drift.
**The front end must never author a type name.**

**When a third asset class enters the book, every signal's `assetClass` has to move with it.**
The failure is silent: the symbol gets a solved threshold, produces findings, and then every
one of them is hidden because "this signal does not apply to that asset class".

**A fallback threshold caps the evidence mark, not the delivery level.** The symbol is marked
unvalidated while its `delivery` is still decided by the three ceilings below — one of which
is computed on that symbol's own history using its own solved threshold, which is more direct
than class-level validation. Keep the two separate.

## data/findings.json

```json
{
  "asOf": "2026-08-21T16:05:00-04:00",
  "findings": [{
    "id":          "2026-08-21:NVDA:PV1",
    "symbol":      "NVDA",
    "assetClass":  "us_equity",
    "signalId":    "PV1",
    "unit":        "session",
    "severity":    "critical",

    "triggeredAt": "2026-08-21T16:05:00-04:00",
    "knownAt":     "2026-08-21T16:05:00-04:00",
    "episodeId":   "2026-08-21:NVDA",
    "novelty":     1.0,
    "priority":    0.723,

    "measured":    { "z": -4.12, "rvol": 3.4, "move": -0.062 },

    "trigger": {
      "unit":            "session",
      "moveAt":          "2026-08-21T16:05:00-04:00",
      "thresholdSource": "validated",
      "barSlot":         null,
      "barClose":        null
    },

    "delivery": { "level": "L1", "cappedBy": null },

    "context": {
      "sizeRank":  { "rank": 7, "of": 502, "unit": "sessions" },
      "benchmark": { "symbol": "SPY", "benchmarkMove": -0.003,
                     "symbolMove": -0.062, "applicable": true },
      "pnl":       { "today": -968, "shares": 124, "lifetime": 2180 },
      "attribution": {
        "notRun":  null,
        "timing":  "before",
        "summary": "Two outlets reported a slip in next-generation rack shipping schedules",
        "sources": [{ "title": "…", "url": "https://…",
                      "publishedAt": "2026-08-21T13:40:00-04:00",
                      "source": "reuters.com", "summary": "…", "origin": "chain" }],
        "model":   null,
        "generatedAt": "2026-08-21T16:05:31-04:00"
      }
    }
  }],

  "scan": [
    { "symbol": "NVDA", "state": "quiet", "unit": "session", "asOf": "2026-08-21",
      "price":  { "today": -0.0098, "line": 0.03837, "usual": 0.02558 },
      "volume": { "rvol": 0.689, "line": 2.0, "partial": false },
      "bar":    { "z": 1.33, "rvol": 0.6, "slot": "15:00", "state": "quiet",
                  "line": 0.01329, "volumeLine": 2.0, "bars": 25 } },
    { "symbol": "NEWCO", "price": null, "volume": null,
      "state": "insufficient_baseline", "baselineDays": 41 }
  ]
}
```

**On the bar tier** `trigger.barSlot` is `"09:00"` and `trigger.barClose` carries that bar's
own close; `context.sizeRank.unit` becomes `"bars"`.

**`barClose` is that bar's close, and `null` on the session tier.** An intraday card must
print a price and **cannot borrow the day's close**: one measured case had a 09:00 bar closing
at $0.0834 against a daily close of $0.0916 — 9.6% apart, opposite directions.

**`delivery.cappedBy`** is `null`, `"symbol_grade"`, `"signal_evidence"` or `"degraded"`.

**`degraded` caps at L2, and never applies to US1/US2/US3.** Both halves have been got wrong
in this system before: the cap was written as L3 in one place and L2 in another, and it was
applied to user lines — which held three user-set stop and take-profit lines off the phone
because the symbol was volatile, when volatility is exactly why the user drew them.

**`trigger.barSlot` is a join key in UTC, not a display string.** To show a time, format the
offset-bearing `triggeredAt`. Never slice `HH:MM` and append a timezone name.

**Compute `sizeRank` from the raw population value, not from `measured.move`.**

**`unit` participates in the merge key.** `session` comes only from PV1, `bar` only from PV5,
and `line` only from US1/US2/US3. The two price-volume tiers never merge with each other.

**User lines carry `unit: "line"` and get their own card.** They are state-kind — they clear
and say so — while a price-volume finding is event-kind and expires. Folding one lifecycle
into the other leaves a card that has to be both. **Only the intraday producer evaluates
them**: two producers evaluating the same lines emit two findings with one id, and the page
shows the same line twice.

**Lines live in `baselines[sym].triggerLine[unit]`, never duplicated inside a finding.**

### `attribution` is the only field that cannot be recomputed

Everything else in these files is arithmetic over price and volume; this one is a model
output. Two consequences: it must be carried forward across runs rather than re-requested,
and every other field must be reproducible without it.

```
notRun: "daily_cap"   we did not look — the day's attribution budget was spent
notRun: null          we did look
summary: null         we looked, including the model's own search, and found nothing
summary: "…"          we found something and this was written from it
```

**`summary` non-null implies `sources` non-empty.** An explanation the reader cannot open is
not an explanation.

**`notRun` and `timing: "none"` are different statements.** Collapsing "we did not look" into
"we looked and found nothing" makes the page state something false — legally, without erroring.

**"Did we ask" is tested by `generatedAt`, never by `model`.** `model` is always `null`
because `ask()` returns no model name, so a branch keyed on it collapses entirely.

**Sources of `origin: "model"` have `publishedAt`, `source` and `summary` all `null`** — a
self-directed search reports a link and nothing verifiable.

**No clock times inside `summary`.** It is a stored string that no rendering layer converts,
and the card header already shows when the alert fired. A time written into the paragraph
carries whatever timezone the prompt happened to contain.

### `scan[]` covers every holding

It is the only evidence that the engine ran over the whole book, and on a zero-alert day it is
the only signal-derived content on the page.

**`scan[].asOf` is the bar this row was read from, not the time of this run.** A mixed book
has two "most recent closes" over a weekend — equities stop on Friday, crypto continues. One
`asOf` cannot say both, and putting Friday's −0.98% under a Saturday timestamp reads as
Saturday's move. When they diverge, append
`holdings_span_multiple_sessions:<date,date>` to `meta.gaps`.

**Two `state` fields.** The row-level one describes the session tier; `bar.state` describes
intraday. **The two tiers also name their lines differently** — `price.line` / `volume.line`
on the session block, `line` / `volumeLine` on the bar block.

**`state = "insufficient_baseline"` requires `price` and `volume` to be `null`**, with
`baselineDays` giving the count.

## data/portfolio.json

```json
{
  "linked": true,
  "asOf": "2026-08-21T16:00:00-04:00",
  "cash": 3200.00,
  "kpi": {
    "totalValue": 60876.00,
    "totalPnl":   { "abs": 1865, "pctOnCost": 0.0330 },
    "todayPnl":   { "abs": -379, "pct": -0.0062 },
    "fromHigh":   { "pct": -0.0506, "high": 64120, "sessionsAgo": 19 }
  },
  "holdings": [{
    "symbol": "NVDA", "name": "NVIDIA", "assetClass": "us_equity",
    "logo": "https://…/NVDA.svg",
    "last": 118.20, "todayPct": -0.062, "fiveDayPct": -0.096,
    "shares": 60, "avgCost": 150.00,
    "value": 14656.80, "weight": 0.241, "lifetimePnl": 2180,
    "vol30d": 0.0255, "fromHighPct": -0.138,
    "spark": [113.2, 114.0, 118.9],
    "notes": ["PV3"]
  }],
  "allocation": {
    "byHolding":    [{ "key": "NVDA", "value": 14656.80, "weight": 0.241 }],
    "byAssetClass": [{ "key": "us_equity", "value": 46108.00, "weight": 0.758 }],
    "byTheme":      [{ "key": "AI", "value": 36424.00, "weight": 0.497,
                       "members": ["AMD", "NVDA", "SOUN"] }]
  },
  "checks": [{ "signalId": "PF2", "value": 0.598, "detail": { "theme": "AI", "holdings": 3 } }]
}
```

**Three accounting identities must hold simultaneously**, tolerance 0.02:

```
sum(holdings[].value) + cash      == kpi.totalValue
sum(holdings[].weight) + cash/total == 1
sum(holdings[].lifetimePnl)       == kpi.totalPnl.abs
```

**Guard every derived number and refuse to write a non-finite one.** `NaN` survives
`JSON.stringify` as `null`, the page renders `null` as `+$0`, and the KPI silently empties.
Throwing at write time turns a wrong page into a failed run.

**With `linked: false`**, `value` and `lifetimePnl` are `null`, `weight` falls back to equal
with `weightSource: "equal"`, and `kpi` keeps only `fromHigh`.

### Mapping a linked brokerage account

`alva portfolio summary --account-id <id>` returns a different shape from this contract, and
the differences are not cosmetic.

```json
{ "totalValue": { "amount": 11703.05, "currency": "USD", "currencySymbol": "$" },
  "cash":       { "amount": 2.27, "currency": "USD", "currencySymbol": "$" },
  "holdings": [{
    "symbol": "MSTU", "side": "LONG", "quantity": 4286,
    "avgCost":      { "amount": 8.838, … },
    "currentPrice": { "amount": 2.73, … },
    "marketValue":  { "amount": 11700.78, … },
    "allocation": 0.99980 }],
  "asOfMs": 1787465873590,
  "positionsAsOfMs": 1787465938000 }
```

| Broker field | This contract | Note |
|---|---|---|
| `symbol` | `symbol` | direct |
| `quantity` | `shares` | different name |
| `avgCost.amount` | `avgCost` | **unwrap** |
| `currentPrice.amount` | `last` | **unwrap** — and see the staleness note below |
| `marketValue.amount` | `value` | **unwrap** |
| `allocation` | `weight` | different name; set `weightSource: "broker"` |
| `side` | — | **no field here.** See below |
| `totalValue.amount` | `kpi.totalValue` | **authoritative — do not recompute** |
| `cash.amount` | `cash` | authoritative |
| `asOfMs` | `asOf` | the balance's instant |
| `positionsAsOfMs` | `positionsAsOf` | the positions' instant, **a different one** |
| — | `name` · `assetClass` · `logo` · `todayPct` · `fiveDayPct` · `vol30d` · `fromHighPct` · `spark` | ours to derive |

**Every money value is an object, never a number.** `h.avgCost` is `{amount, currency,
currencySymbol}`. Calling `.toFixed()` on it throws; interpolating it renders
`[object Object]`. Unwrap explicitly — matching field names do not mean matching types.

**`side` can be `SHORT`, and this contract has nowhere to put it.** A short carries a
positive `quantity` with inverted P/L, so `value − shares × avgCost` gets the **sign wrong**.
That is a wrong number, not a missing one. **Until there is a field for it, skip short
positions and record `short_positions_unsupported:<SYM,…>` in `meta.gaps`** — a holding
absent with a stated reason is honest; a holding present with inverted P/L is not.

**Currency is per-value, so a mixed-currency account is possible.** This contract has no
currency field and every total here is a bare number. Summing two currencies produces a
number that means nothing. **Skip any holding whose currency differs from `totalValue`'s and
record `multi_currency_unsupported:<CUR,…>`.**

**Two instants, not one.** The balance and the positions are as of different times. Keep both;
a single `asOf` covering both is the same error as one `asOf` over a mixed equity/crypto book.

**`totalValue` is authoritative — never recompute it as `Σ value + cash`.** The broker's number
includes dividends, fees and same-day cash movements that are invisible here. A recomputed
total drifts from it while both are labelled "total value" on the page.

**Weight has two definitions on a margin account.** One measured case: the API reported
`allocation` 0.9998 while the broker's own interface showed 103.6% for the same position —
market value over total value versus over net equity. Take the API's number and say which one
it is; do not compute your own.

**The broker's `currentPrice` lags the market.** In the same measured snapshot the API said
2.73 while the broker's interface said 2.83. Signals run on kline data, not on this price, so
the holdings table's "last" and the signal's "today" can legitimately disagree. **Say so on
the page** rather than forcing them to match.

## data/series.json

```json
{
  "unit": "USD",
  "points": [{ "d": "2026-08-21", "value": 60876.00, "dayPnl": -379, "cumReturn": 0.0330 }],
  "benchmark": { "symbol": "SPY", "points": [{ "d": "2026-08-21", "cumReturn": 0.0912 }],
                 "coverage": "us_equity_only" },
  "high": { "d": "2026-08-02", "value": 64120 }
}
```

**The curve starts on the day the account was connected, not the day the position was opened.**
`benchmark.coverage` says what the benchmark actually covers — for a mixed book, SPY is not
the benchmark for the crypto part, and the page must say so rather than imply otherwise.

## data/baselines.json

```json
{
  "NVDA": {
    "sigmaRobust": 0.0255, "sigmaAnn": 0.405,
    "baselineDays": 502, "usable": true,
    "m23": { "rho": 0.187, "verdict": "pass", "n": 504 },
    "distribution": {
      "p50": 0.0098, "p95": 0.0412, "p99": 0.0688,
      "histogram": { "from": -0.11, "binWidth": 0.0055, "counts": [1,0,2,3,7,14] }
    },
    "distributionBar": { "unit": "15min", "tz": "UTC",
      "slots": { "21:30": { "n": 135, "p50": 0.00137, "p95": 0.00544,
                            "histogram": {}, "top": [] } } },
    "slotBaselines": {
      "13:45": { "med": -0.00051668, "sigma": 0.00561752, "vmed": 6960881.75, "n": 90 }
    },
    "thresholds": { "theta_z": 1.5, "theta_v": 2.0, "source": "validated" },
    "signalGrades": {
      "PV1": { "maxDelivery": "L1", "verdict": "usable",
               "multiple": 2.31, "ci": [1.46, 3.12], "blocks": 11, "days": 3292 },
      "PV5": { "maxDelivery": "L2", "verdict": "insufficient_sample",
               "multiple": 1.61, "ci": [1.34, 2.46], "blocks": 3, "days": 3292 }
    },
    "triggerLine": {
      "session": { "price": 0.033, "volume": 2.0 },
      "bar":     { "price": 0.014, "volume": 2.0 }
    },
    "historicalTriggers": { "PV1": 14, "PV5": 31, "windowSessions": 502,
                            "last7": { "PV1": 1, "PV5": 0 } },
    "degraded": null
  }
}
```

### `m23` is the only runtime guard that can detect "the method does not apply here"

`rho = P(|z| >= theta_z)` over the last 504 trading days. Fewer than 250 usable days gives
`rho: null` and `verdict: "insufficient_sample"`, which routes to the PV4 coverage marker.

```
rho < 0.02          band too tight, this symbol can barely ever trigger -> disable
0.02 <= rho <= 0.40 pass
rho > 0.40          band is meaningless -> downgrade to Warning
```

**The upper bound is 0.40.** It has been written as 0.60 in places where nothing measured ever
came close to either bound, so the disagreement stayed invisible — and the executable copy had
the loose one. A high-`rho` symbol would then be graded `pass` and pushed when the rule says
hold it on the page.

### `signalGrades` is the per-symbol delivery ceiling, independent of thresholds

Computed once, the first time a signal is enabled for a symbol. Frozen after that.

**Each signal is graded on the series it actually fires on.** PV1 fires on daily closes, so its
grade runs over the symbol's **entire daily history**. PV5 fires on 15-minute bars, so its grade
runs over the **intraday bar series** — the same bars the runtime evaluates, restricted to
regular hours for US equities. Grading PV5 on daily data measures a different signal and is
the reason PV5 grades were absent, which in turn silenced the whole family once the missing
grade began capping at L2.

| | PV1 | PV5 |
|---|---|---|
| Series | daily closes, full history | 15-minute bars, as deep as the endpoint allows |
| `W` baseline | 90 sessions | 90 days at the same slot |
| `F` lookahead | 5 sessions | 5 bars |
| `blocks` gap unit | sessions | bars |
| `days` field | sessions in the series | bars in the series |

**Intraday depth is bounded by the endpoint** — 366 days per query for US equities, and in
practice four to five months are fetched. That is enough for `blocks >= 5` on an active symbol
and not enough on a quiet one, which is exactly what `insufficient_sample` is for.

Six steps, with `r_t` the simple return over the chosen series and `n` its length.

```
1  Trigger days    T   = { t : |z_t| >= theta_z AND RVOL_t >= theta_v }
                         recomputed with the same thresholds the runtime uses
2  Post volatility A_t = pstdev(r_{t+1} … r_{t+F})
                         population standard deviation over those F days, their own mean removed
3  Baseline        typ = median{ A_t : t over every assessable day }
                         ⚠️ the denominator is EVERY assessable day, not the non-trigger days
4  Multiple        m_t = A_t / typ,  for t in T
5  Interval        resample m with replacement, same size, B times, taking the median each time
                   ci = [2.5th percentile, 97.5th percentile]
6  Blocks          blocks = |{ t in T : t − prev(t) >= F }|
                   triggers closer together than F belong to one block
```

Assessable range is `t in [W+1, n−F)` — the first `W` days have no baseline, the last `F` have
no lookahead.

```
ci[0] > 1.0 AND blocks >= 5   ->  maxDelivery "L1", verdict "usable"
blocks >= 5, ci[0] <= 1.0     ->  maxDelivery "L2", verdict "effect_unclear"
blocks < 5                    ->  maxDelivery "L2", verdict "insufficient_sample"
```

**1.0 is the line that says nothing happened** — a multiple of 1.0 means the five days after a
trigger are as turbulent as any other five days.

**The criterion reads the interval, never the point estimate.** One measured pair: a symbol
with a point estimate of 1.299 is capped while one at 1.254 is not, because the first has 41
independent blocks and the second 110 — same centre, an interval nearly twice as wide, wide
enough to contain 1.0.

**`B = 20000`, and seed the bootstrap per symbol.** This is not "pick something large": at
B = 2000 one symbol's lower bound landed between 0.9702 and 1.0153 across ten seeds, so 20% of
seeds decided its delivery tier by a random number. At B = 20000 all ten seeds agree. A shared
RNG stream also makes the result depend on the order symbols are processed in — re-seed per
symbol so that reordering the book cannot change a tier.

**When a grade is missing, cap at L2.** An unassessed symbol is `insufficient_sample`, not
`usable`. Defaulting to L1 when the computation is absent turns the only noise gate in the
system into a pass-through, and it fails in the direction that reaches the phone. The US
family is exempt — those are the user's own lines.

**Use the full history.** Measured: truncating to 802 bars puts three symbols in a
different delivery tier than the full history does. The short-window version looks
equally reasonable, which is what makes it dangerous.

**Seed the bootstrap per symbol and make B large.** The criterion is a hard line at 1.0, so
sampling noise has to be far smaller than the distance from the estimate to 1.0. At B = 2000
one symbol's lower bound landed between 0.9702 and 1.0153 across ten seeds — 20% of seeds
decided its delivery tier by a random number. A shared RNG stream also makes the result depend
on symbol ordering.

**`insufficient_sample` is not falsification.** It says the sample was too small to conclude.
The page says "not yet assessed".

**The page must explain "it crossed but nothing pushed."** Both legs passed, the scan table
shows a trigger, the phone stayed quiet — unexplained, that reads as a broken system.

**`degraded` is one of `null` · `"high_vol"` · `"m23_loose"` · `"m23_strict"` ·
`"short_baseline"`.** The value names the reason, and the page must say the reason rather than
the tier — "this symbol's alerts stay on the page" rather than "downgraded to Warning".

### Other fields

**`triggerLine` translates thresholds into quantities a reader can compare against**, per unit.
The page renders from this; findings never store a line value.

**`historicalTriggers` counts triggering days for both PV1 and PV5, not bars.**
`historicalTriggers.PV5` must equal the number of PV5 entries in that symbol's `alertHistory`.

**`distributionBar` is a separate distribution and must not reuse the daily one.** Store only
the slots that actually triggered today — crypto has 96 slots a day and storing all of them
wastes 95.

**`thresholds` holds two pairs — session and bar. Never mix one pair's values with the other's.**

## data/market.json

```json
{
  "indices":     [{ "symbol": "SPX", "name": "S&P 500", "price": 7641.16,
                    "change": 23.6, "changePct": 0.0031, "asOf": "…" }],
  "treasury":    { "asOf": "…", "curve": [{ "tenor": "1M", "yield": 0.0469 }],
                   "spread2y10y": 28 },
  "commodities": [{ "symbol": "GCUSD", "name": "Gold", "price": 4590.20,
                    "changePct": 0.0044, "asOf": "…" }],
  "crypto":      { "asOf": "…", "fearGreed": 31,
                   "totalMarketCap": 3.02e12, "btcDominance": 0.440 },
  "earningsWeek": [{ "d": "2026-08-24", "beforeOpen": 118, "afterClose": 89 }]
}
```

`indices[].change` is in points and `changePct` is a ratio; both are present. Which blocks
render follows from the book's asset classes — an all-equity book shows no crypto block.

## data/symbols/<SYMBOL>.json

```json
{
  "symbol": "NVDA",
  "kline":  [{ "d": "2026-08-21", "o": 126.1, "h": 127.0, "l": 117.9, "c": 118.20, "v": 102864553 }],
  "intraday": { "unit": "15min", "tz": "UTC", "sessions": 3,
                "bars": [{ "t": "2026-08-21T13:30", "o": 126.1, "h": 126.8,
                           "l": 125.4, "c": 125.9, "v": 3810422 }] },
  "range52w": { "low": 103.90, "high": 174.57, "asOf": "2026-08-21" },
  "alertHistory": [{ "d": "2026-06-17", "signalId": "PV1", "z": -2.85 }],
  "insider": { "windowDays": 30, "filedInWindow": 71, "codeFilter": ["P","S"],
               "buys":  { "people": 2, "filings": 3, "signalId": "EV1",
                          "items": [{ "filingDate": "2026-06-22", "owner": "LE PHONG",
                                      "code": "P", "shares": 1200, "price": 118.4,
                                      "value": 142080 }] },
               "sells": { "people": 4, "filings": 12, "signalId": null, "items": [] } },
  "earnings": { "next": "2026-09-09", "time": "amc",
                "past": [{ "d": "2026-07-30", "time": "amc" }] },
  "funding":  { "asOf": "…", "unit": "8h", "threshold": 0.0005, "normalized": true,
                "points": [{ "t": "…", "rate": 0.0004 }],
                "extremeDays": ["2026-08-19"] },
  "news":     [{ "title": "…", "url": "https://…", "publishedAt": "…", "source": "…",
                 "summary": "…", "sentiment": 0.41, "relevance": 1.0 }],
  "coverage": { "pv5From": "2024-05-02" }
}
```

**Omit the whole key when a block does not apply** — `funding` for equities, `insider` and
`earnings` for crypto. Never write `null`: the page decides by key presence, and "does not
apply" is a different statement from "nothing yet".

**`intraday` exists to draw the intraday alert card, not to compute intraday baselines.** It
holds a few sessions; baselines need 90 days and live in `slotBaselines`.

**Insider rows carry `shares`, `price` and `value`.** The endpoint returns `amount` (signed)
and `price`; there is no `securities_transacted` field. Reading the wrong name yields an em
dash on every row, which reads as the endpoint having no data.

## config/alerts.json

The only user-writable file.

```json
{
  "version": 1,
  "userLines": {
    "MSTR": { "US1": 125.0 },
    "AMD":  { "US2": 450.0 },
    "NVDA": { "US3": -0.12 }
  },
  "enabled": { "PV1": true, "PV5": true, "EV4": true, "US1": true, "US2": true, "US3": true },
  "channels": { "push": true, "quietHours": null },
  "attribution": { "dailyCap": 10 }
}
```

**US1 and US2 store a price; US3 stores a ratio.** Convert from whatever the user said at
configuration time — storing a percentage and converting at evaluation time puts the
conversion in the hot path where a stale price makes the line move.

## data/meta.json

```json
{
  "generatedAt": "2026-08-21T16:05:12-04:00",
  "nextRun": "2026-08-21T16:35:00-04:00",
  "specVersion": "signal-spec.md@<sha>",
  "producedSignals": ["PV1", "US1", "US2", "US3"],
  "scanned": { "holdings": 5, "newsItems": 187, "newsPassed": 6 },
  "freshness": { "prices": "…", "news": "…", "earningsCalendar": "…" },
  "gaps": ["crypto_attribution_falsified", "newco_short_baseline"]
}
```

**`producedSignals` says which signals this run actually produced.** A signal nobody declared
renders as "not enabled" rather than as "on but quiet". Each producer merges its own entries
rather than overwriting the list — several producers write this file.

**`gaps` must be honest.** Anything not computed, unreachable or under-covered goes in; tab 4's
boundaries read from it. **Empty is worse than wrong.**

**Timestamps on the page come from `freshness`, never hardcoded.**

**No finding may be timestamped after `generatedAt`.** A 24-hour market's last bar extends to
fetch time while `asOf` is pinned to a close, which produces alerts from the future. One line
of assertion, no statistics required.

## data/news.json

```json
{
  "asOf": "…", "chain": "wide", "minRelevance": 0.80,
  "items": [{ "symbol": "TSLA", "title": "…", "url": "https://…", "source": "…",
              "publishedAt": "…", "summary": "…", "sentiment": 0.41, "relevance": 0.93 }]
}
```

This is the display block at the bottom of tab 1 and it uses a **wider** chain than EV6:
relevance `>= 0.80`, no topic gate, the whole day. A display block wants recall; the
attribution gate wants precision. Fetch on demand — never poll.

## What the eval asserts

| Layer | Assertion |
|---|---|
| L0 structure | every file parses and matches this schema |
| L1 whitelist | `findings[].signalId` is a subset of `signals.json` and its evidence is not red |
| L2 parameters | validated classes match the spec exactly; unvalidated carry `fallback_solved` and are recomputable |
| L2 accounting | the three portfolio identities hold within 0.02 |
| L3 consistency | no signal is always true at its threshold · no downgrade empties a delivery level · no `sizeRank` when `baselineDays < 60` · no EV6/PF2/PF3 on crypto · no DR1 on equities |
| L3 provenance | every PV finding's `(symbol, date)` appears in that symbol's trigger history, and `historicalTriggers` matches its length |
| L3 units | `unit: "session"` only from PV1, `unit: "bar"` only from PV5 · lines come from `triggerLine[unit]` · `|measured.z|` meets that tier's threshold |
| L3 attribution | `timing` equals the pure function of `sources[]` and `moveAt` · `summary` non-null implies `sources` non-empty · every `sources[].url` parses · user lines and EV4 carry no attribution · a merged card carries exactly one · no clock time in `summary` |
| L3 coverage | `scan[].symbol` equals the holdings set exactly · every finding's symbol is `triggered` in `scan` |
| L3 clock | no timestamp anywhere is later than `meta.generatedAt` |
| L4 copy | the forbidden-phrase lists, both languages |
