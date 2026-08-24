# Signal specification

The 13 settled signals — trigger, parameters, scope, delivery, and the copy each is allowed
to produce — plus the alert engine that turns findings into what reaches a phone.

Data fields are in `data-contract.md`. Endpoints and the attribution contract are in
`data-sources.md`. Platform mechanics are in `alva-platform.md`. Nothing here is repeated there.

**Do not enable a signal that is not in this file.** Everything omitted was either falsified
or never settled.

## Delivery table

| ID | Signal | Type | Scope | Evidence | Delivery | Tab |
|---|---|---|---|---|---|---|
| **PV1** | Price-volume, daily | alert | US equity | green, independently reviewed | L1 push | 1 · alerts |
| **PV1** | Price-volume, daily | alert | crypto | green, independently reviewed | L1 push | 1 · alerts |
| **PV5** | Price-volume, 15-min | alert | US equity | green, independently reviewed | L1 push | 1 · alerts |
| **PV5** | Price-volume, 15-min | alert | crypto | green, independently reviewed | L1 push | 1 · alerts |
| **EV4** | Earnings calendar | calendar | US only | — calendar | L1 push | 1 · alerts, 2 |
| **PV3** | Move-size marker | display | both | — display | L3 holdings | 1 · holdings |
| **PV4** | Coverage marker | display | both | — metadata | L3 holdings | 1 · holdings, 2 |
| **US1** | Stop line | alert | both | — user-set | L1 push | 1 · alerts |
| **US2** | Take-profit line | alert | both | — user-set | L1 push | 1 · alerts |
| **US3** | Drawdown line | alert | both | — user-set | L1 push | 1 · alerts |
| **EV6** | Company news | attribution source | US only | yellow, awaiting review | attached to PV1/PV5 cards | 1 · alert card |
| **EV1** | Insider cluster buy | record | US only | — record | L4 record | 2 |
| **DR1** | Funding-rate extreme | display | crypto only | orange, criterion not met | L3 holdings | 1 · holdings, 2 |
| **PF2** | Theme concentration | display | US only | orange, final | L3 health | 1 · allocation |
| **PF3** | Theme resonance | display | US only | orange, final | L3 health | 1 · allocation |

13 signals, 15 rows — PV1 and PV5 appear per asset class because their thresholds differ.

**Delivery level and Tab are separate axes.** Delivery answers "which touchpoint"; only L1
interrupts. Tab answers "where on the page".

**Write all 13 into `data/signals.json` whatever the portfolio holds.** Scope is expressed by
the `assetClass` field, never by omitting a row: the page reads type names from this file,
the page's own ID-whitelist audit reads it, and the eval whitelist assertion reads it. A
missing row becomes an unrecognized ID the moment that signal appears in findings.

**The "Signal" column is an internal identifier, not user-facing wording.** Take the label
from each signal's copy template. "Double confirmation" is forbidden in the interface — see PV5.

**Severity names never reach the interface either.** `Critical / Warning / Informational` are
ordering inputs. Say what the tier means for the user:

```
NO   Band is loose, so the alert is downgraded to Warning
YES  Band is loose — this symbol's alerts stay on the page and do not push
```

## Thresholds

### Validated asset classes

Daily (PV1), lookahead 5 trading days:

| Asset class | theta_z | theta_v |
|---|---|---|
| **US equity** | **1.5** | **2.0** |
| **Crypto** | **1.5** | **3.0** |

Intraday (PV5), lookahead 5 bars:

| Asset class | theta_z_bar | theta_v_bar | Session |
|---|---|---|---|
| **US equity** | **4.75** | 2.0 | regular hours only, 26 slots |
| **Crypto** | **10.0** | 3.0 | all hours, 96 slots |

**These are industry anchors that passed the criterion, not values chosen by backtest.**

### Unvalidated asset classes: the fallback rule

Hong Kong, commodities, ETFs, bonds, FX and any non-US equity were never backtested. For a
holding outside US equity and crypto:

**1. If at least 12 symbols of that class are reachable** — take the top 12 by dollar volume
from the screener. Sweep `theta_v` over `[1.0, 6.0]` in steps of 0.25 and pick the value
whose **pool-level share of triggering days** lands closest to **4.16%**, the measured share
for US equity PV1 at `theta_v = 2.0`.

- **Both sides must use the same aggregation.** The anchor is pool-level, so compute the
  candidate pool-level too — not a median across symbols. The same quantity differs by
  0.15pp between the two.
- **Solve at pool level, never per symbol.** Pool-level solving reproduces exactly across a
  split-half; per-symbol solving reproduced in 29% of cases.

**2. If fewer than 12 are reachable** — use the US equity constants, `theta_z` 1.5 and
`theta_v` 2.0.

**3. `thresholdSource = "fallback_solved"` in both cases.** There is no third enum value;
inventing one for "never solved" fails the L2 eval assertion.

**4. `theta_z` is 1.5 in both cases.** Only `theta_v` is solved.

**5. Unvalidated classes do not enable PV5.** There is no fallback for intraday thresholds,
and borrowing 4.75 or 10.0 has no basis.

**6. Unvalidated classes must be labelled in the interface, and their evidence level must
never display as green.**

**Verify the data is reachable before promising to watch a symbol.** For a non-US symbol,
try the daily endpoint once before building. The screener's country filter does not return
Hong Kong listings — it returns US-listed shares of Hong Kong companies — and
`symbol=0700.HK` returns 400. **The one unvalidated class known to work end to end is ETFs**
(18-symbol pool, solved `theta_v` = 1.75).

**The fallback rule itself is not systematically validated.** Holdout was run on one class
only, the 4.16% anchor comes from US equity with no independent basis for other classes, and
the stratification axis differs per class. Say this in the interface, not only here.

**The pool selection rule must be deterministic.** Random sampling gives a different
`theta_v` for the same portfolio on two runs — that is a random number, not a specification.
Measured: random samples of 6, repeated 30 times, matched the full-pool answer half the
time, spread `[2.50, 3.25]`.

### Three rules about thresholds

**1. Thresholds come from an external anchor, not from the criterion.** The criterion passes
almost everywhere on the grid and its pass rate falls monotonically with the threshold, so
"highest pass rate" always picks the lowest cell. The criterion validates a given threshold;
it cannot choose one.

**2. No volatility banding.** One `theta_z` for every asset class.

**3. Fixed values, not rolling quantiles.** A rolling quantile drifts with the market, so two
runs on the same portfolio produce different configurations. **Reproducibility is the point.**
Volatility rolls daily; the threshold does not move.

### What to compute per symbol at runtime

Thresholds are looked up, never calibrated per symbol. Two things *are* per symbol:

- **Baseline length** — under **60 trading days**, PV1 and PV5 are **disabled**, not
  downgraded. The 90-day denominator does not exist yet, so the quantity is not computable;
  "do not push" would be the wrong statement. Mark the symbol with PV4.
- **Distribution usability `rho`** — out of band means downgrade or disable.
- **Per-symbol delivery ceiling** — fewer than 5 independent blocks caps that signal at L2
  for that symbol.

Both are defined in `data-contract.md` → data/baselines.json, under `m23` and `signalGrades`.

**Never hardcode an exclusion list of symbols.** That excludes the symbols that were tested
and lets untested ones through — delivering more the less you know.

## Signal definitions

### PV1 — price-volume, daily

**Trigger** `|z_rob| >= 1.5 AND RVOL >= theta_v`, `theta_v` 2.0 US / 3.0 crypto.

Uses `M2` and `M3`. `M23` gates applicability.

| Attribute | Value |
|---|---|
| Scope | All US equity and crypto that pass the `M23` check |
| Lookahead | 5 trading days |
| Dedup | Update within the same `anomalyEpisodeId`; short window |

**Downgrade rules**

1. Annualized volatility above the per-class bound → Warning, no push.
   **US equity 50%, crypto 92.8%.**
2. `rho > 40%`, band too loose → Warning.
3. `rho < 2%`, band too tight → disabled, interface marks coverage insufficient.

**The volatility bound must be per class.** The least volatile crypto asset sits at 54.2%
and all 25 exceed 50%, so the US bound would leave PV1-crypto permanently empty at L1 while
its delivery level says L1 push.

| | |
|---|---|
| What it says | Price moved well outside this symbol's own normal, with real turnover behind it |
| What it does not say | **No direction.** Outcomes split evenly after a trigger |
| What to do | Compare with same-day news and the index; with no confirmable driver, record and watch |

**Copy template**

> **NVDA price-volume move** · 24.5% of your book
> Close −5.6%, 2.7× its own robust volatility, volume 3.4× normal
> Same period: NVDA −5.6% / SPY −0.3%

### PV5 — price-volume, 15-minute bar

**Trigger, US equity** `|z_rob_bar| >= 4.75 AND RVOL_bar >= 2.0`, regular hours only, 26 slots.
**Trigger, crypto** `|z_rob_bar| >= 10.0 AND RVOL_bar >= 3.0`, all hours, 96 slots.

**Baselines must come from the same time of day.** `sigma_rob` uses the prior 90 days of
returns **at that slot**; RVOL is today's bar's **single-bar** volume over the median
single-bar volume at that slot across the prior 90 days.

- **Single bar, not cumulative.** A cumulative measure drags the day's earlier volume along
  and gets blunter toward the close.
- **No reading when the same-slot sample is under 30 days.** Do not compute on a short sample.

Lookahead is 5 bars (75 minutes).

**Three copy constraints, both asset classes**

1. **Never call it "double confirmation."** The intraday `theta_v` is a strictness knob, not a
   second confirmation: at matched trigger counts its contribution is +0.006 (US, p=0.835)
   and −0.128 (crypto, p=0.860). Write "abnormal price move, with thin-volume bars already
   filtered out."
2. **Never say which symbols pass.** Per-symbol rank does not survive out of period.
3. **Alert volume swings 1.5× year to year.** Do not plan capacity by a fixed count.

**The opening bar is effectively single-legged.** `P(volume leg | price leg)` is 88.6% on the
first US bar, 33–50% near the close, 54.2% overall — and the opening bar carries 11.2% of all
triggers. Record this in scope.

**Extended hours are unusable.** Only 62.8% of extended-hours slots exist and half cannot
produce `sigma_rob` at all.

### EV6 — company news, attribution source

**Not an independent alert.** It is the input and gate for enrichment block 2: EV6 decides
whether there is material to read, attribution decides what the material says.

**Trigger** a news item with ticker `relevance == 1.0` AND `topic ∈ {earnings, M&A, IPO}` at
topic relevance `>= 0.5` AND published within 120 minutes of the alert AND at or before it.

| Parameter | Value |
|---|---|
| Ticker relevance | 1.0 |
| Topic relevance | >= 0.5 |
| Window | ±120 minutes |
| How many | 3 most recent by publish time |

Endpoint `/api/v1/stocks/market-news` (1 credit per call).

- **`symbol` filtering is not strict** — a query for NVDA returns other companies' stories.
  Filter on `tickers[].relevance_score` yourself.
- **`relevance_score` is a string with inconsistent formatting** (`"1"` and `"1.000000"` in
  one response), so `=== 1.0` is false for every row and the first gate silently returns
  nothing without erroring. `parseFloat` first. Same for `topics[].relevance_score`.
- **`start_time` and `end_time` are both required**; omitting either returns 400. `limit` caps at 100.
- **Use `publish_time`** (unix seconds) for the window test, never the string form.
- **Carry `summary` through.** Title alone leaves the model doing keyword matching and forces
  the reader to open the article to learn anything.
- **Do not use `banner_image`.** Third-party images turn an alert card into a news feed.
- Deduplicate outlets by `source_domain`, not `source`.

| Attribute | Value |
|---|---|
| Scope | **US only.** Crypto fails the relevance gate at every threshold tested |
| Claim level | Same-day co-occurrence and time proximity. **Never that the story drove the move** |
| Coverage | 19.01% with truncation; 25.73% without, of which 26.1% is after-the-fact reporting |

**Do not loosen this gate.** The model can search on its own, so EV6's recall is not the
bottleneck — its job is to be a high-precision starting point.

**The page's "related news" block does not share this gate** (`rel >= 0.80`, no topic gate,
whole day). A display block wants recall; an attribution gate wants precision.

### EV1 — insider cluster buy

**Trigger** at least 2 distinct `owner_name` within 30 calendar days with
`transaction_code = P` (open-market purchase). **Use `filing_date`, not `transaction_date`.**

Endpoint `/api/v1/stocks/insider/transactions` (1 credit per call). US only — crypto has no
Form 4 equivalent. Refresh daily. **Does not enter the alert stream.**

- **Nearly inert for mega caps.** Over 8.6 years: AAPL 0 filings, PLTR 2 from 1 person,
  NVDA 20 from 2 (all in 2020). Put this in the coverage matrix.
- **Roughly 40% of symbols have an untrustworthy `filing_date`** — one symbol has 61% of
  records where `filing_date == transaction_date` alongside a P90 of 347 days. Detect the
  bimodal pattern and flag data quality.
- The endpoint returns `amount` (signed) and `price`. There is no `securities_transacted` field.

**Copy template**

> NVDA · insider filings
> 8/11 <filer name> bought · <shares> shares · <total value>
> 8/13 <filer name> bought · <shares> shares · <total value>

Print the count of filers before the count of filings, and show both — a symbol can have many
filings and no open-market buys at all.

### DR1 — funding-rate extreme

**Trigger** `|M12| >= 0.05% per 8h`, the perpetual funding rate.

Endpoint `/api/v1/crypto/funding-rate` (free), native 8-hour granularity. Crypto only.
Refresh aligned to settlement (00:00 / 08:00 / 16:00 UTC). **Does not enter the alert stream.**

**Why it is not an alert:** a placebo shift of ±30 days passes the criterion just as often,
because an extreme funding rate is a range state rather than an event. The threshold also
does not survive out of period — the share of days above 0.05% differs 14× between 2021 and
later years.

**Copy template**

> BTC · funding rate 0.082% per 8h

**Never write "crowded longs", "over-leveraged", or "correction risk."** Those are directional.

### PF2 — theme concentration

**Trigger** `M21 > 35%`, the portfolio's combined weight in one theme.

US only; there is no theme data for crypto. Refresh on holdings change and daily.
**Does not enter the alert stream.**

**35% is an industry convention, not a backtested value.** If the interface colours by it,
say so. Under equal weights the condition degenerates into a count.

**Copy template**

> Largest theme is 42%, across 3 holdings

**Never write "therefore riskier" or "consider diversifying."** Three of four measurement
angles do not support it.

### PF3 — theme resonance

**Trigger** some theme is shared by at least 2 holdings. There is no weight threshold.

US only. Refresh on holdings change and daily. **Not an independent alert** — plain "two
holdings in the group triggered together", with no theme dimension, scores strictly better.

**Evidence is highly concentrated:** 85.8% of triggers fall in 8 sessions. Behaviour in calm
periods is unverified and the interface must say so.

**Copy template**

> 3 holdings share one theme: Artificial Intelligence

**Never write "therefore they move together."**

### PV3 — move-size marker

**Trigger** `|M1| > 5% AND NOT PV1` — a large single-day move whose volume leg did not
confirm, so it is not an alert.

Both asset classes. **Display only, never pushed.** Sits next to the "today" cell in the
holdings table and as a third-tier hollow marker on the chart.

| | |
|---|---|
| What it says | This day moved a lot, but volume did not follow, so we did not wake you |
| What it does not say | **Not that it was a fake move, and not that it is safer** |

**Copy template**

> Move · over 5% in a day, volume below the 2.0× line

**PV3 exists to make the filter visible** — it is the evidence for "what counts as noise."
Reading it as a weak signal is a misuse.

### PV4 — coverage marker

**Trigger** available baseline shorter than 60 trading days.

Both asset classes. **Metadata: it describes our capability, not the market.**

It **constrains other displays**: with an insufficient baseline, show no move percentile, no
30-day volatility, no distance from high. Affected cells render as an em dash. **PV3 markers
stop too** — without 60 days there is no reliable volume median.

**Copy template**

> NEWCO has 41 days, short of the 60 required. Until then its price baseline is too short to
> judge a move against.

If `company/detail` provides `ipo_date`, phrase it as "day 41 since listing" — more legible
than an abstract count. Check that endpoint's billing before using it.

**This is not optional politeness.** On a real new listing with 295 days of history, a fixed
5% threshold fires on 33% of days. Without the coverage marker the user reads constant alerts
as an active stock rather than a baseline that does not exist yet.

### EV4 — earnings calendar

**Trigger** next earnings date at most 1 trading day away.

Endpoint `/api/v1/stocks/earnings-calendar` (free); its `time` field gives before/after
market directly. US only.

**A calendar, not a signal** — it detects nothing, it surfaces a scheduled date, and it does
not go through the alert criterion. Lead time is about 30 days.

**Must run pre-market.** Its copy says "reports after tomorrow's close"; a post-close job
cannot produce that on the day.

**Copy template**

> AAPL · August 22 · earnings calendar
> Reports after tomorrow's close · 18.8% of your book · earnings-day volatility is 2.58× normal

**Never write `T−1`.** Give the actual date and put the relative phrase ("tomorrow") in the
description line — the date answers "which day", the phrase answers "how long".

### US1, US2, US3 — user lines

| ID | Interface name | Trigger | Intrinsic direction |
|---|---|---|---|
| **US1** | Stop line | price <= user value | down |
| **US2** | Take-profit line | price >= user value | up |
| **US3** | Drawdown line | `M22` <= user value | down |

All three fire on crossing, with no smoothing and no cooldown. `M22` is drawdown from high.

**No parameters of ours.** `thresholdSource = "user_set"`. **Store prices, not percentages** —
convert at configuration time.

| Attribute | Value |
|---|---|
| Scope | Both asset classes |
| Severity | **Critical for the whole family**, bypassing importance weighting |
| Dedup | State-based: stays true without re-pushing, until it reverses |
| Unit | `line` — not `session` or `bar`, which belong to the two price-volume tiers |
| Evaluated by | the intraday job only, every 15 minutes, on the freshest price |
| Evidence ceiling | **Exempt.** These are the user's own lines |

**US never downgrades.** PV1 downgrades on high volatility or a loose band; US does not. This
is the only family with that exemption.

| | |
|---|---|
| What it says | **The line you drew has been touched** |
| What it does not say | Not that we think you should act |

**Copy template**

> NEWCO · take-profit line
> Your +25% line was reached · +$749 today

**Do not render US lighter than PV.** US is a decision trigger the user pre-committed to; PV
is an attention trigger.

## Indicator dictionary

Only indicators referenced by settled signals.

| ID | Name | Definition | Window | Used by |
|---|---|---|---|---|
| **M1** | Simple return | `r_t = C_t / C_{t-1} − 1` | — | PV3 · M2 |
| **M2** | Robust z | `(r_t − med) / sigma_rob` | 90 days, **excluding today** | PV1 · PV5 |
| **M3** | Relative volume | `V_t / median(V_{t−90..t−1})` | 90 days | PV1 · PV5 |
| **M4** | Annualized volatility | `sigma_rob × sqrt(A)`, A = 252 equity / 365 crypto | 90 days | PV1 downgrade |
| **M7** | Insider cluster count | distinct filers, filtered by `transaction_code` | 30 calendar days | EV1 |
| **M8** | Filing lag | `filing_date − transaction_date` | — | EV1 |
| **M10** | Earnings distance | trading days to next earnings | — | EV4 |
| **M12** | Funding rate | normalized to 8h, neutral ≈ 0.01% | — | DR1 |
| **M20** | Position weight | holding value / portfolio value | — | ordering |
| **M21** | Theme exposure | sum of weights in a theme, **deduplicate synonyms** | — | PF2 · PF3 |
| **M22** | Drawdown from high | — | — | US3 |
| **M23** | Distribution usability | `P(|z| >= theta_z)` over the last 504 trading days | 504 days | PV1 applicability |

**Simple returns, not log returns.** The two produce different trigger sets.

## Alert engine

One engine for every family. **Detection stays per family — there is no unified anomaly
score.** Price-volume needs two legs, events need clusters, derivatives need debouncing.

```
classify -> admit -> dedupe -> merge co-occurring -> suppress -> order -> enrich -> deliver
```

### Delivery levels

| Level | Nature | Settled entries |
|---|---|---|
| **L1 phone push** | interrupts | PV1 · PV5 · EV4 · US1 · US2 · US3 |
| L2 overview stream | there when the app opens | PF3 |
| L3 holdings page | same | PV3 · PV4 · DR1 · PF2 |
| L4 record page | same | EV1 |

### Admission

**First gate, type.** `alert` → L1/L2 candidate · `modifier` → never delivered alone ·
`display` → capped at L3 · `record` → L4 · `calendar` and `attribution source` by their own rules.

**Second gate, evidence level is a delivery ceiling:**

| Evidence | Highest reachable |
|---|---|
| green, verified | L1 |
| yellow, self-tested awaiting review | **L1**, but the summary must say "not independently reviewed" |
| blue (cited, not self-tested) · yellow (untested) | L2 |
| orange, tested and criterion not met | L3 |
| red, falsified | L4 |
| white, unverifiable | not delivered |

**This turns the evidence level from documentation into a runtime constraint: an unvalidated
signal may not wake the user.** It also relaxes automatically — promoting a signal to green
grants push rights without editing a table.

**Two exceptions:** the US family is exempt, and PF2 drops to L3 because it is a state rather
than an event.

**One more:** a symbol with `thresholdSource = "fallback_solved"` must not be delivered as
green, whatever the signal's own evidence level says.

### Dedup

Continuations of the same `anomalyEpisodeId` update the card; they do not push again.

```
PV price     short window   one-off events
EV events    long window    45 calendar day cooldown; one batch may be filed over several days
US lines     state-based    stays true without repeating, until it reverses
```

**Intraday and daily share an `episodeId`, and still produce two cards.** They share the
episode so that dedup and cooldown see them as one story; they stay separate cards because
`unit` is in the merge key and the two tiers' directions can disagree. A close that reverses
an intraday move is reported as the daily card for that day, not as an edit to the intraday one.

State lives in `state.json`.

### How alerts clear

**By the signal's kind, not by the calendar.**

```
Event-kind   PV1 · PV5 · EV1 · EV4         something happened at a moment
             It cannot become false, only old -> expires into history, no "cleared" label

State-kind   US1 · US2 · US3 · DR1 · PF2   a condition currently holds
             It can become false -> clears on reversal, and must say "cleared" once
```

Expiry follows **the next period of the same granularity**, never midnight:

| Signal | Leaves when |
|---|---|
| PV1 daily | the next close does not trigger |
| PV5 intraday | accumulates through the day, all leave at the close. **Never folded into the PV1 card** |
| US1/2/3 | price returns inside the line |
| DR1 | rate returns inside the threshold |
| EV4 | after the release |
| EV1 | the 45-day cooldown expires |

**Recomputing each round is not replacing each round.** The intraday job runs every 15
minutes; a PV5 that fired at 10:15 no longer fires at 10:30. **Intraday findings accumulate
and are not replaced; only the day boundary clears them.** Replacing per round makes an alert
vanish 15 minutes after it pushed.

| Time | What happened | Card |
|---|---|---|
| 05:00 | PV5 fires | appears, ×1 |
| 05:15 | does not fire | **unchanged.** The 05:00 event still happened |
| 05:30 | fires again | same card, ×2, header moves to 05:30 |
| close | — | whole card leaves, into history |

**So the alert on screen can be from the previous close.** At ten in the morning the daily
card describes yesterday's close, because today has not closed. That is not staleness — it is
the most recent reading that ruler has taken. **Every card carries a date** so the two are
never read as the same day.

**Crypto's close is 20:00 ET, not 16:00 ET.** Binance daily bars cut on UTC, so day D closes
at D+1 00:00Z. Writing 16:00 ET produces a card reporting a close that will not be known for
another four hours. For a mixed book, `asOf` takes the latest close among holdings.

**A cleared alert stays one more period before leaving**, labelled "cleared" with the time.
Otherwise the user who set a stop line, got a push, and opens the app that evening finds
nothing — and "it recovered" looks exactly like "the system is broken" on an empty list.

**Event-kind clearing needs no state at all** — it is recomputed from the day's data each
round. Only state-kind needs one bit, and that is the bit dedup already stores.

### Merging co-occurring signals

Multiple signals on the same `(symbol, episodeId, unit)` become **one card with several pills**.

```
NVDA  −6.2%  [price-volume · daily] [stop line]
```

**`unit` is part of the key.** Daily and intraday are two things within one day and their
directions can differ: one measured case had a 15-minute bar at −2.04% (z −10.18) inside a
day that closed +6.56% (z +3.30). Merged, the header can only pick one direction — and it
picks the one opposite to the day.

**Every card reports its bar count, including a count of one.** Otherwise a merged card and a
single-trigger card read as two different kinds of object.

### Suppression

Only four legitimate reasons:

```
1  outside trading hours, or a known data-source delay
2  below the classification threshold
3  the same thing already pushed
4  the user's quiet hours
```

**"Too many alerts today" is not one of them** — that delivers fewest on the days the user
needs them most.

### Ordering

**Primary order is reverse chronological.** Alerts are a stream; reordering by importance puts
a 09:00 alert above a 16:00 one, which reads as scrambled.

**Only alerts at the same instant are ranked**, which is where "several signals at once"
actually arises:

```
priority = severity × position_weight × novelty

severity          Critical 3 · Warning 2 · Informational 1
position_weight   the symbol's portfolio weight, 0–1 (M20); portfolio-level signals use 1.0
novelty           first occurrence 1.0 · continuation of the same episode 0.5 · still true 0
```

**`novelty = 0` means "already pushed", not "unimportant".** A state-kind signal can hold for
months — one drawdown line held for nine and a half. It keeps appearing in `findings` because
the condition does hold, but it stops pushing and leaves the "new today" group.

```
Not true -> true     push once, "new today"                  novelty 1.0
True -> still true   no push, "ongoing" group, collapsed     novelty 0
True -> not true     "cleared" for one period, then history  clearedAt
User edits the line  all prior state is void, re-arm         next crossing counts as first
```

**Re-arming on edit is not optional.** A changed line value is a new rule, and the old
"already pushed" must not suppress the new line's first trigger. `state.json`'s `armedFor`
holds the value the line was armed at.

**Ongoing entries never expire**, because they are naturally bounded by the number of lines
the user set. An N-day expiry would make a still-true line vanish.

**Put ongoing lines in their own collapsed group, not in today's stream.** Say how long each
has held, and default the group to closed.

⚠️ **Do not give them a column in the holdings table.** That table compares across rows, and a
column with a value on one holding in eight displaces one that has a number on all eight.
Worse, PV1's two legs and a user line side by side read as three legs of one rule, when a user
line fires entirely on its own.

**This is half the answer to "what is noise"** — noise is not only "too small", it also
includes "you already know this."

**Use `triggeredAt`, not `knownAt`.** The latter collapses everything one cron round computed
into a single instant.

**Ordering never truncates.** A "top N plus a fold" is a fold, not a drop.

**A merged card takes the highest priority in its group**, rather than each signal competing
separately — otherwise one symbol occupies two places in the list.

The three coefficients are uncalibrated.

### Enrichment

Every alert carries four context blocks. **Blocks 1, 3 and 4 are arithmetic with no
statistical claim; block 2 is the only LLM output anywhere in the running system.**

| Block | Answers | Coverage | Produced by |
|---|---|---|---|
| 1 Market or itself | is everything down today | 100% | arithmetic |
| 2 Attribution | why did it move | 19% | **LLM** |
| 3 Is this move large | has it done this before | 100%, constrained by PV4 | arithmetic |
| 4 What did it cost me | how much does it matter | 100%, needs portfolio | arithmetic |

**Block 1 comes first.** The only reason the card exists is that a deterministic rule fired.
Putting the model's paragraph ahead of it lets the least reliable part open for the most
reliable one.

**Attribution timing has four values, all computed from timestamps:**

```
before    reporting exists from before the move
after     only after-the-fact reporting
untimed   only model-found sources, publication time unverified
none      nothing found
```

**This is not a causal classification.** Only chain-retrieved sources decide the value;
model-found sources have unverifiable timestamps and can only push it to `untimed`. The model
writes the paragraph and may add sources — it never produces the badge.

**Attribution runs after ordering.** Classification, admission, dedup, merging, suppression
and ordering all complete and the card is committed before attribution runs. That is the only
reason it is compatible with keeping the model out of magnitude judgements.

**One card, one call, one explanation.** Merging decides how many cards exist, not how many
explanations a card gets. A single-signal card is the degenerate case — still one call.
**EV4 is never attributed**; it does not merge and it carries its own reason.

**When `ask()` fails the alert still goes out**, just without block 2. Enrichment means
"already committed to delivering, now add context" — one model failure must not stall the chain.

Full contract: `data-sources.md` → Attribution. The prompt itself lives only in
`scripts/attribution.js`. Field: `findings[].context.attribution`.

## Capability boundaries

State these in the interface, not only here.

| Boundary | What to say |
|---|---|
| The criterion measures volatility expansion only | Whether the five sessions after a trigger are more turbulent than normal. Information that does not surface as volatility is invisible to this ruler |
| Sample range | 92 US equities across 11 GICS sectors plus 25 crypto assets — not the whole market |
| Crypto has no market benchmark | BTC is over half of total crypto market cap, so a market-model decomposition fails for it |
| Unvalidated asset classes | Fallback thresholds, never systematically validated; evidence must not display as green |
| Portfolio level is unvalidated | Thresholds were validated per symbol |
| Attribution can be wrong | It offers a possible explanation, not an assertion, and the material may be incomplete |
| The third asset class has no home | Hong Kong and similar listings are neither US equity nor crypto; the market page shows US indices, which are not their benchmark |
| Alerts cluster during regime changes | The baseline is a rolling 90-trading-day window. When a symbol's volatility multiplies within weeks, the first weeks of the new regime are all extreme against the old baseline, so triggers bunch up there. **This is the rule behaving correctly**, but the user gets the most alerts during the period they are most anxious. We do not suppress by frequency |
