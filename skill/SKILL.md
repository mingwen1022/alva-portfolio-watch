---
name: portfolio-watch
description: Build a portfolio-watch Playbook from one sentence — a dashboard plus phone alerts. Use whenever a user says "keep an eye on my NVDA and TSLA", "tell me if something big happens", "monitor my holdings", "alert me when my positions move", or anything with that intent, even without the words playbook, dashboard, or alert. Covers US equities and crypto; other asset classes get fallback thresholds and are labelled unvalidated. Never predicts direction and never gives trading advice.
---

# Portfolio Watch

Turn one sentence into a Playbook that keeps running: the **dashboard** answers "what is
happening to my holdings", the **alerts** reach a phone when something is worth a look.

This skill decides three things on the user's behalf — **what counts as a move, what counts
as noise, and how to rank several signals firing at once**. All three are alerting problems;
the dashboard is where their answers become visible.

**This skill ships its own producers. It does not delegate.**

```
scripts/*.js        nine files, uploaded as they are. They ARE the implementation
@alva/portfolio-watch   a different, platform-side implementation with a similar name.
                        Do NOT switch to it. It needs a Pro subscription, its state
                        model is not this contract, and a page built on it will not
                        match data-contract
alva skillhub       there is a platform skill called `portfolio-watch-setup` that wraps
                        that module. Reading it is fine; building from it is not
```

A real run went looking for that module, wrote `require("@alva/portfolio-watch")`, hit
`requires a Pro subscription`, rewrote the same file four times, and came back having built
only half the automations. If something here is unclear, the answer is in `references/`,
not in another skill.

## Seven core principles

**Every constraint downstream is one of these made concrete. Where a later section appears to
conflict, these win.**

**1 · Look thresholds up, never invent them.** Triggers and parameters live in `signal-spec`.
The credibility statement on the page depends on that — a made-up number makes it false.
**2 · Evidence level is a delivery ceiling, not a label.** Six levels each cap a delivery
level (`signal-spec` → Admission). Read the table; do not reduce it to validated / not.
**3 · No direction, no advice.** Outcomes split evenly after a trigger. The entire claim is
"this is outside this symbol's own normal", and it stops there.
**4 · Never hand the deterministic part to a model.** Timestamps, percentiles, move sizes,
same-day-or-not: compute them. Models report facts reliably and conclude unreliably.
**5 · A quantity that cannot be computed is not displayed anywhere.** An insufficient baseline
means disabled, not "a rough estimate". With no denominator, something that looks like a z
score is worse than nothing.
**6 · Silence needs wording.** No material, no alerts, no benchmark are all normal states —
but the page has to say they are normal, or the user reads a broken system.
**7 · Fixed template, variable data.** Rewriting the page each run means every user gets a
different product.

## What is in this skill

```
references/alva-platform.md   Platform build contract: runtime · ALFS · push · release · billing · silent failures
references/signal-spec.md     The 13 signals: triggers · parameters · indicator dictionary · fallback rule · alert engine
references/data-contract.md   Every file a run must write and every field the page reads
references/data-sources.md    Endpoints · fetch semantics that fail silently · the attribution contract
scripts/                      Producers and the attribution module, ready to upload and run
template/index.html           The dashboard; it fetches the JSON above and renders four tabs
```

**Read on demand, not end to end.** Before each step, read these:

| Step | Read first |
|---|---|
| 1 Decide what to watch | this file |
| 2 Build baselines | `signal-spec` → Thresholds · Indicator dictionary · `data-sources` → Endpoints · `data-contract` → data/baselines.json |
| 3 Configure signals | `signal-spec` → Delivery table · Signal definitions · Admission · `data-contract` → data/signals.json |
| 4 Compute today | `signal-spec` → Signal definitions · Indicator dictionary · `data-contract` → data/findings.json · data/baselines.json |
| 5 Apply the template | `alva-platform` → Reading data from the page · `data-contract` → File layout |
| 6 Configure alerts | `signal-spec` → Alert engine · `data-sources` → Attribution · `data-contract` → config/alerts.json |
| 7 Configure automation | `alva-platform` → Cronjob, feed, playbook · `data-contract` → data/meta.json |
| 8 Release | `alva-platform` → Push requires three things at once · Release order · Design gate |

**Step 4 cannot produce findings without the triggers in `signal-spec` → Signal definitions.**
Writing from this file instead means inventing thresholds — principle 1.

**`references/` is the single source of truth. This file repeats no threshold, no trigger and
no command signature.** Where a number appears in both, `references/` wins.

**Scripts run in the Alva V8 runtime: JavaScript only, no top-level `await`.** Read
`alva-platform` → Runtime before writing any script. Python will not run on this platform.

---

## Step 1 · Decide what to watch

**Do not skip ahead to building.** The shape of the input determines every branch after it.

### 1.1 Get the symbol list

```
Symbols only, no sizes    use them; portfolio.json gets linked = false, equal weights
Symbols with sizes         the user typed quantities and costs — that IS a linked book.
  typed into the message   Take them as given; do not go looking for an account.
                           `linked = true`, weights by market value, P/L from avgCost
"my holdings"              alva portfolio accounts -> account-id -> portfolio summary
accounts returns []        no linked account, ask the user (see 1.4)
an account is listed but
  summary will not read    say which account and quote the error, then ask (see 1.4)
Nothing clear              ask the user
```

**`linked` means "we know the sizes", not "a broker is connected."** The code decides it as
`holdings.some(h => h.shares != null)` and nothing else. A user who types "NVDA 60 shares at
150, BTC 0.12 at 68000" has given you everything an account would have given you, and the
whole value/weight/P&L half of the page works from it. **Do not ask them to connect a
brokerage when they have already told you.** The only thing a real account adds is that it
keeps itself up to date.

**A listed account is not a readable one.** A real run found a linked Interactive Brokers
account whose authorization had lapsed; this table only named the empty-list case, so the
agent had to extrapolate — it landed on the right branch (ask), but it stopped after
`accounts` and told the user "authorization expired" without ever calling `portfolio
summary`. **Run the second call before naming a cause.** Whatever comes back, the user is the
one who has to go fix it, so give them the account id and the endpoint's own words rather
than a paraphrase — "reconnect your brokerage" is not actionable when three are linked.

**When an account is linked, the broker's schema is not this contract's schema.** Money
values are objects, `quantity` is not `shares`, `side` can be `SHORT`, currency is per-value,
and the balance and the positions carry different timestamps. `scripts/portfolio-link.js`
does that mapping and refuses what it cannot represent rather than computing a wrong number.
The differences and why each one matters: `data-contract` → Mapping a linked brokerage account.

**Take `totalValue` and `cash` from the broker; never recompute them.** The broker's figure
carries dividends, fees and same-day cash movements you cannot see, and a recomputed total
drifts from it while both are labelled "total value" on the page.

**No linked account is a normal state, not a degraded one.** Alerts all still run — price,
volume and calendar signals need only market data. Only money-denominated fields are
unavailable: `kpi` keeps `fromHigh`, `value` and `lifetimePnl` become `null`, and `weight`
falls back to equal weighting with `weightSource = "equal"`. `allocation.byAssetClass` does
not depend on money and stays complete.

### 1.2 Classify each symbol

**This decides almost every branch downstream.**

| Class | Test | Consequence |
|---|---|---|
| US equity | a **single company** listed on a US exchange, not an ETF | 12 signals available; DR1 is crypto-only |
| Crypto | a USDT spot pair on a major exchange | 5 fewer: earnings · attribution · insider · two theme signals |
| Other | none of the above — **ETF** · Hong Kong · A-shares · commodities · bonds · FX | fallback thresholds, `thresholdSource = "fallback_solved"` |

**ETFs are "other".** The sample pool is 92 single companies stratified by GICS sector, and
**sector classification presupposes a single company**. Marking SPY as validated borrows a
single-stock threshold to vouch for a basket. The measured ETF pool solves to a lower
`theta_v` than US equity.

**Verify the data is reachable before promising to watch a symbol.** For a non-US symbol,
try one against the daily endpoint in `data-sources` → Endpoints first. **If it is unreachable, say
so immediately and leave it out** — never build a page that lists a symbol whose every cell
is an em dash.

Four hard constraints for "other":

```
assetClass is "other"       do not omit the field; the page hides blocks by class membership
PV5 is not enabled          there is no fallback rule for intraday thresholds
Evidence never shows green  fallback thresholds are unvalidated; lending them our mark vouches for them
US indices are not its benchmark   say so in the tab 4 boundaries
```

### 1.3 Two fields the book carries that no endpoint gives you

`theme` and `logo` come from **you**, when you build the book. There is no endpoint for
either, and the MCP call that would answer the first one bills as an LLM call.

```
theme    US single stocks only. NVDA -> "AI", TSLA -> "Autos", MSTR -> "Crypto proxy".
         ⚠️ Never put an ETF in a theme. SPY is already a basket, and theme concentration
            would then count one index fund as a single bet — the exact thing that
            measure exists to catch. Leave the key off; do not invent an "Other" bucket,
            because "not classified" and "classified as miscellaneous" are two statements.
         Omitting it for every holding is a legitimate outcome — PF2 and PF3 then have
         no input and the page says so. Omitting it *silently* on a book that clearly has
         themes is not.
logo     ⚠️ **Do not fill this in by hand — `init.js` resolves it.** It builds a candidate
         URL per asset class, calls HEAD on it, and keeps only what returns 200.
         Pass one in `holdings[].logo` only to override.
```

Only `theme` is yours. You know what NVDA is; filling it is the same kind of act as
filling `name`.

**Why the logo is not:** the earlier version of this section asked you to fill it and gave
no URL, so four real runs shipped `logo: null` on every holding and every page drew
lettered tiles. The tile is a real design, not a failure state — but a field that is null
everywhere forever is a branch nobody exercises. The reason it stayed empty is that the
answer is not knowledge, it is a lookup with three different rules and one trap:

| | Source | Measured |
|---|---|---|
| US equities, new listings | `…/arrays-public-assets/logos/<SYM>.svg` | NVDA · AAPL · MSFT · TSLA · AMD · KLAR · CHYM all 200 |
| ETFs | the same pattern | **SPY · QQQ · GLD · TLT · XLE · IWM all 404** |
| Crypto | CoinMarketCap numeric id, not the ticker | BTC=1 · SOL=5426 · DOGE=74; `init.js` carries the top 25 |

Following the pattern without checking would put a **broken image** on every ETF row —
strictly worse than the tile, because the tile is a design and a broken image is a fault.

### 1.4 A single symbol is a valid portfolio

"Watch NVDA" and "watch my NVDA, TSLA and AAPL" take the same path. Do not build a separate
one for a single symbol; only which blocks are meaningful differs.

```
Still present    alert stream · scan table, one row is fine · tabs 2, 3, 4
Whole block out  portfolio slices · PF2 · PF3
By position      KPI and equity curve — with no position use linked:false, do not invent a watch-only mode
```

**Holding nothing is normal, not an edge case.** Users often want to watch something they
have not bought.

### 1.5 Three cases that require asking

**Do not guess for the user.** A wrong guess produces a Playbook watching the wrong thing,
and it takes days to notice.

| Case | Ask |
|---|---|
| No symbols and no readable account | Which ones do you want to watch? Connect a brokerage account first? |
| A named symbol does not resolve | `XXXX` did not resolve — is that the right ticker? |
| More than 30 symbols | That is more than the page reads at a glance, and the phone will go off most days. Watch all of them, or the ten largest by weight? |

**Never silently drop a symbol that did not resolve.** Say which ones were left out.

**Substitute every slot before you speak.** A real run read the row above and told the user
"roughly N alerts a day … the top K by weight" — **the letters, not numbers**. `XXXX` reads as
a slot and got filled; `N` and `K` read like prose and did not. If a number cannot be computed
yet, do not promise one: say what will happen in words, as the row now does. The rule
generalises — nothing shaped like a placeholder reaches the user.

### 1.6 Things the user may also say

```
"tell me if it drops 5%"   US-family user line -> userLines in config/alerts.json
                           US1/US2 store a price, not a percentage — convert here
"only after the close"     channels.quietHours
"will it fall tomorrow?"   say plainly that we do not do this; offer what we do
"should I sell?"           same; no trading advice
"add RSI / MACD"           no — see "Never do this"
```

---

## Step 2 · Build a baseline per symbol

**Once per symbol, incrementally after that.** Definitions and windows: `signal-spec` → Indicator dictionary.

| Order | Do | Produces |
|---|---|---|
| 1 | Fetch **all available daily bars** and 4–5 months of 15-minute bars | raw price and volume |
| 2 | Indicator layer: robust volatility · volume median · percentile distribution · distribution usability | intermediates |
| 3 | Take thresholds by asset class (`signal-spec` → Thresholds) | thresholds |
| 4 | Signal layer: which signals fired today | findings |
| 5 | Write | `data/baselines.json` |

`scripts/lib.js` already implements the core arithmetic for steps 2 and 4. **Use it rather
than writing a second version** — two implementations drift, and the symptom is a number on
the page disagreeing with the same number in an alert.

### 2.1 Where the data comes from

**Endpoints, parameters and billing are in `data-sources` → Endpoints.** Copy them; do not assemble
from memory. The next section there carries the fetch semantics that fail without raising — **read it
before writing the fetch code**.

Three that fail without erroring:

```
Derive the US regular-hours window from ET, never a hardcoded UTC constant —
  either constant is wrong for half the year
"25–26 bars a day" cannot detect that; both windows are 6.5 hours.
  Check whether the first bar of the day is 09:30 ET
Count failed segments separately when paging. "ERR 400" is not "one bar"
```

**When an intraday volume ratio comes out at 20–50×, check what time that bar is before
believing it.**

### 2.2 Setting thresholds

| Asset class | How | `thresholdSource` |
|---|---|---|
| US equity · crypto | look up `signal-spec` → Thresholds | `validated` |
| Other, at least 12 symbols reachable | pool-level solve for `theta_v` per the fallback rule | `fallback_solved` |
| Other, fewer than 12 | use the US equity constants | `fallback_solved` |

**No numbers in this file** — a copy here goes stale the moment the spec changes.

```
theta_z is never solved         uniform across classes; the sweep solves theta_v only
Unvalidated classes: no PV5     there is no fallback for intraday thresholds
Same aggregation on both sides  the anchor is pool-level, so the candidate must be too
```

**Thresholds are fixed when the baseline is built and locked after that.** Re-solving lets
them drift with the market and breaks "the same portfolio produces the same configuration
twice" — **that property is this skill's reproducibility mechanism**. Volatility rolls daily;
thresholds do not move.

### 2.3 An insufficient baseline disables, it does not degrade

Under **60 trading days** (`signal-spec` → What to compute per symbol at runtime),
price-volume signals are **disabled** and the symbol is marked with PV4.

What a short sample produces is not "a rough z score" — **the denominator does not exist yet**.
Until it does, the page shows this symbol's price and the fact that we cannot judge it.

### 2.4 Compute a delivery ceiling per symbol

**Thresholds answer "what crosses the line". This answers "once it crosses, does it push".
The two are independent.**

Thresholds are looked up and uniform, and the table behind them rests on a backtest over a
sample pool. **For a symbol that was never tested, we do not know whether it behaves like the
pool.** This step tests that on the symbol's own history. Algorithm and the three verdicts:
`data-contract` → data/baselines.json.

```
When     once, the first time a signal is enabled for a symbol; frozen after that
Data     that symbol's entire daily history — step 2.1 already fetched it
Reading  insufficient_sample means "not enough to conclude", not "invalid".
         The page says "not yet assessed"
```

**Use the full history.** Measured: truncating to 802 bars puts three symbols in a different
delivery tier than the full history does. **Change the window and the
conclusion flips — and the short-window version looks just as reasonable.**

**The page must explain "it crossed but my phone stayed quiet."** Both legs passed, the scan
table shows a trigger, and nothing happened — unexplained, that reads as a broken system.

---

## Step 3 · Configure signals

Enable the 13 settled signals from `signal-spec` → Delivery table, **filtered by asset class**,
and write each into `data/signals.json` (fields: `data-contract` → data/signals.json).

| Scope | Signals |
|---|---|
| US equity and crypto | PV1 · PV5 · PV3 · PV4 · US1 · US2 · US3 |
| Also `other` | PV1 · PV3 · PV4 · US1 · US2 · US3 — **not PV5** |
| US equity only | EV1 · EV4 · EV6 · PF2 · PF3 |
| Crypto only | DR1 |

⚠️ **`other` needs its own row in `assetClass`, and leaving it out fails silently.** The symbol
gets a solved threshold, produces findings, and then every one of them is hidden because the
signal does not list its class.

**Write all 13, omit none — scope is expressed by the `assetClass` field, not by deletion.**
The same file is the catalogue for three consumers: the page's type labels, the page's own
ID-whitelist audit, and the eval whitelist assertion. **Omit one and it becomes an
unrecognized ID the moment it appears in findings, failing that assertion.** Whether a block
renders follows from the symbol's class being in that signal's `assetClass`; whether a key
exists in the data follows from whether the signal applies to that symbol — inapplicable
means the whole key is absent, never `null`.

**Do not enable signals outside the spec.** Everything omitted was falsified or never settled.

---

## Step 4 · Compute today and write the data files

**Step 2 produced baselines, step 3 produced the catalogue. This produces "how is today".**
Field definitions: `data-contract` → data/findings.json.

**`state.json` is the only read-modify-write file**; the rest are overwritten wholesale.
Overwriting it loses dedup keys and cooldown timestamps.

| File | Contents |
|---|---|
| `data/findings.json` | today's findings plus **a scan reading for every holding** in `scan[]` |
| `data/portfolio.json` | holdings · KPI · allocation across three slices |
| `data/series.json` | portfolio equity curve plus benchmark |
| `data/market.json` | market page data |
| `data/symbols/<SYM>.json` | per symbol: candles · 52-week range · alert history · insider · earnings · funding · news |
| `data/state.json` | cross-run state: dedup · cooldowns · state-kind signal bits |
| `meta.json` | run time · data freshness · **known gaps** |

**`scan[]` is not optional.** It is the only evidence that the engine ran over every holding,
and on a zero-alert day it is the only signal-derived content on the page. Without it the
user cannot tell whether the engine ran at all.

**`meta.gaps` must be honest.** Anything not computed, not reachable or under-covered goes in
— tab 4's boundaries read from it. **Empty is worse than wrong**, because the user concludes
everything worked.

**When something does not apply, omit the whole key; never write `null`.** `funding` is crypto
only; `insider` and `earnings` are US only. The page decides by key presence — "does not
apply" and "nothing yet" are different statements.

**Compute each fact once.** The triggering reading goes in `findings[].measured` and the page
reads it; do not recover it from the line value on the page. **This gets bypassed most often
when a field is null and the front end computes its own** — which then agrees by coincidence,
with nothing keeping it that way.

### 4.1 Intraday percentiles are a separate distribution

**They must come from the same time of day** — mixing all 26 bars is structurally dominated by
the open and the close. Store under `baselines[sym].distributionBar.slots[<slot>]`; fields in
`data-contract` → data/baselines.json.

**The slot string is UTC and it is a join key, not a display value.** To display a time,
format the offset-bearing `triggeredAt`. Never slice `HH:MM` out of a string and append a
timezone name — crypto trades around the clock, so this error is invisible on screen.

**On crypto this block saturates.** Rank lands in the top 3 in 93–100% of measured cases, so
"1st largest of N" says the same thing every time. **The rank saturates but the histogram
does not** — on crypto use distance, not rank.

---

## Step 5 · Apply the dashboard template

`template/index.html` is **literally the starting point**, not a reference — four tabs, the
alert card structure, the pill system, colour semantics, chart marker conventions, the modal,
and all copy are already implemented. **Read it before deciding what to fill in.**

```
Fixed     layout · card structure · pills · colour semantics · chart markers · modal · wording
Variable  language · symbol list · user lines · which blocks appear
          — all from JSON, never hardcoded
```

**This is where reusability actually lands.** Only a fixed template plus variable data is
"works for a portfolio it has never seen". Extend the template only when a user needs a block
it does not have; **the default path is to apply it as-is**.

### 5.1 Three rules the template cannot enforce

**Timestamps come from `meta.freshness`; never hardcode one.** Label each block with its own
time rather than a single "last updated" — the three freshness values move at very different
rates, so one label necessarily lies about two of them.

**Staleness has to be visible.** When `now − freshness.prices` exceeds one and a half refresh
cycles, say so on the page. **A quiet day's credibility rests entirely on this** — otherwise
the user cannot tell "nothing moved" from "it did not run".

**Audit lists read from the data, never from a hand-copied list.** Forbidden-word lists,
column sets and similar checks go stale the moment the data changes: a hand-written allow-list
of Latin words produced eight false positives the first time the book changed. Hardcode only
what is a deliberate product decision, because that part is a decision rather than data.

### 5.2 Reading the data

**A published page sits behind the gateway, where relative-path `fetch` always 404s.** Use the
`@alva-ai/toolkit` ALFS client with absolute paths — see
`alva-platform` → Reading data from the page.

Keep the ALFS root in **one constant**: empty for local preview, the absolute root when
published. One HTML file then works in both places; do not maintain two versions.

### 5.3 The four tabs

All four tabs are already built in the template; this step only fills in the data.

```
1 Holdings & alerts  alerts + today's scan + totals + allocation + equity curve + holdings + news
2 Symbol detail      pick one symbol, see everything about it
3 Market             indices · rates · commodities · crypto sentiment · calendar.
                     Objective data, not a signal source
4 Method             what counts as a move · what counts as noise · how ranking works · boundaries
```

**Tab 4 is not optional.** It is where this product's credibility comes from — the answer to
"why should I believe this counts as a move" has to be on the page, not only in a document.
**Which boundaries to state: `signal-spec` → Capability boundaries.** Use that list; do not
draft your own.

**Which blocks appear is decided by the data, not by you**: the `assetClass` scope in
`signals.json` plus key presence in each file.

---

## Step 6 · Configure alerts

Eight stages, order fixed (`signal-spec` → Alert engine):

```
classify -> admit -> dedupe -> merge co-occurring -> suppress -> order -> enrich -> deliver
```

The three most often got wrong:

**Merging** — one card per `(symbol, episodeId, unit)`, with several pills. **`unit` is part
of the key**: daily and intraday are two things within one day and their directions can
differ, so they never merge.

**Ordering** — **primary order is reverse chronological**; `severity × position_weight ×
novelty` only ranks alerts at the same instant. Use `triggeredAt`, not `knownAt`.
**Ordering never truncates** — the page's "top N plus a fold" is a fold.

**Enrichment** — the four blocks are in `signal-spec` → Enrichment, card order is already built into the template. **Block 1, what fired, comes first.** The only reason the card exists is
that a deterministic rule fired; putting the model's paragraph ahead of it lets the least
reliable part open for the most reliable one.

### 6.1 Attribution

**The contract is `data-sources` → Attribution, and the prompt itself lives only in
`scripts/attribution.js`.** Use that module; do not redraft the prompt. Its wording encodes
measured failures, and a second copy drifts from the one that runs.

Four decisions belong to this step:

```
Whether to call    user lines US1–3 and EV4 never call, and the block does not render;
                   everything else calls.
                   Call even with no material — the strict chain only covers US equities,
                   so crypto material is empty every time. "Skip when empty" means crypto
                   never gets attribution at all
One card, one call after merging, iterate over cards, not over signals
Four timing values before / after / untimed / none, all computed from timestamps in code.
                   untimed must not collapse into none — that puts "nothing found" above real sources
After ordering     it cannot change whether or where something is delivered. On failure the
                   alert still goes out, without an explanation
```

**The retrieval window is ±120 minutes in both directions; reporting filed after the move is
still collected.** News lags the move it describes — traders act well before a newsroom writes
it up, so a "before only" window filters out the real explanatory material, crypto especially.
**At the same time, forbid the model from commenting on whether an item preceded or followed
the move**: that offset is already printed next to each source, and repeating it can only
produce a negation, which consumes the entire character budget.

**Do not pass a `model` parameter**; use the platform default. `attribution.model` is
**always `null`** because `ask()` does not return a model name. **Never use it to decide
whether attribution ran** — that test reads `generatedAt`.

### 6.2 Output validation: two hard gates

```
Gate 1  number whitelist  every number in the output must appear in the **rendered prompt text**;
                          otherwise drop the explanation and still show the material.
                          Normalize first: strip sign · thousands separators · trailing zeros · % and x
Gate 2  no source, no ship  an explanation must rest on at least one source, retrieved or model-found
Recorded, not blocked     wording · length · language · disclaimers. Detect disclaimers by
                          sentence shape, strip them, and record that you did
```

**These two are the failures a user cannot detect for themselves, which is why only they are
hard gates.** Whether the prose reads well is visible; whether a z score is −5.56 or −6.5 is
not, and an explanation with no source behind it reads exactly like one with sources.

**Gate 2 must live in code, not only in the prompt.** Measured twice: with empty material the
model would not say "nothing found" and instead assembled a sentence out of "a broader crypto
rally" and "posts on X", with an empty source list. **Give it that exit in the prompt and
catch the times it does not take it.**

**Build the whitelist from the rendered prompt text, not by re-formatting the source data.**
Formatting the same number twice and comparing for equality rejects the correct value the
model copied.

**Never validate a source by HTTP status** — paywalled sites return 401/403 to anything that
is not a browser.

---

## Step 7 · Configure automation

**Group by cadence, not one cronjob per signal.** Signals sharing a cadence share a script:
one less job is one less failure point and one less duplicate fetch. Different cadences must
stay apart.

| Cronjob | Frequency | Signals | Why this frequency |
|---|---|---|---|
| Intraday | every 15 minutes | PV5 · US user lines | that is the granularity of an intraday signal, and a crossing must be timely |
| Daily | once after the close | PV1 · US user lines · baseline increment | they judge a whole trading day |
| Pre-market | **once, weekdays, pre-market** | EV4 earnings calendar · EV1 insider | EV4's copy says "reports after tomorrow's close" — a post-close job cannot produce that on the day |
| Market | hourly | tab 3 reference data | the macro endpoints are hourly at best, and none of this feeds a threshold |

| Cronjob | Script |
|---|---|
| Intraday | `scripts/producer-intraday.js` |
| Daily | `scripts/producer.js` |
| Pre-market | `scripts/producer-context.js` |
| Market | `scripts/producer-market.js` |

Upload them as they are. **They take no editing, but they do take arguments** — each reads
`root` and `playbookUrl` from `--args`, and without them every run throws silently. See
`alva-platform` → Cronjob, feed, playbook.

**Frequency is set by when the signal's data changes, not by how often we want to look.**
Funding rates settle every 8 hours; fetching every 15 minutes returns the same value.

### Before you move on, count them

**Four cronjobs. Not two, not three.** Two real runs of the same one-sentence request built
four and two respectively, and the two-job run raised nothing: the page renders, the alerts
fire, and only the parts fed by the missing jobs stay empty forever — news, the earnings
calendar, funding rate, and the whole market tab. **Every one of those looks like "no data
this run" rather than "this job was never created."**

```bash
alva deploy list        # must show four, one per script above
```

| Missing | What silently never happens |
|---|---|
| Pre-market | `symbols[].news` · `earnings` · `insider` · `funding` — DR1 and EV1 have no input |
| Market | tab 3 keeps the skeleton `init.js` wrote; `earningsWeek` stays empty |
| Daily | no `scan` rows, so the whole alert-basis half of the holdings table is blank |
| Intraday | no PV5, no user lines — the two signals that need to be timely |

`data/meta.json` → `freshness` is the receipt: it must carry **prices · intraday · news ·
earningsCalendar · market**. A key missing there means that producer has never run.

### Then prime each one once

Creating the cronjob is not the same as having run it. Between publication and the first
tick, whatever that producer feeds is empty — and empty reads as "nothing happened today,"
not as "this has not run yet." Intraday recovers in fifteen minutes; **the daily job may not
tick for another twenty hours**, and until then the holdings table has no alert basis at all.
The first person to open the page is usually the person who just asked for it.

```bash
for s in producer producer-intraday producer-context producer-market; do
  alva run --entry-path "~/playbooks/<name>/scripts/$s.js" --timeout-ms 600000 \
    --args '{"root":"/alva/home/<user>/playbooks/<name>","playbookUrl":"<url>"}'
done
```

Then read the receipt back and count five keys. A real run created all four cronjobs and
primed three of them; `freshness.intraday` was missing and the page shipped without PV5 or
user lines. **Four created, four primed, five keys — check all three, they fail separately.**

**Cron is evaluated in UTC**; convert pre-market and post-close from ET.
See `alva-platform` → Runtime.

**Initialization runs once and belongs in no cron** — it performs steps 2 and 3, after which
the cronjobs only do increments.

**Run `scripts/init.js` before creating any cronjob.** The page fetches eight files plus one
per symbol and **rejects the whole load if any is missing**, so cronjobs without
initialization show "Data did not load" rather than a partial page. `init.js` writes all of
them: `signals` · `baselines` · `portfolio` · `findings` · `series` · `news` · a `market`
skeleton · `meta` · `symbols/<SYM>.json`.

**Scale the timeout to the book.** Initialization is linear in symbols: each one costs a
daily pull, **four segmented intraday pulls**, a logo HEAD, and a PV5 history replay. A single
symbol finishes in well under a minute; a nine-symbol book does not. A flat `540000` was
written when the intraday pull was one request instead of four — allow roughly

```
--timeout-ms  $(( 120000 + 60000 * <symbol count> ))     # 9 symbols → 660000
```

and give it headroom rather than the tightest number that worked once. **Timing out here is
the worst failure this skill has**: `init.js` writes nine files in sequence, so a kill lands
between two of them and leaves a playbook that loads but is missing `series` / `news` /
`market` / `meta` — and the page rejects the whole load rather than showing a partial one.

```bash
alva run --entry-path '~/playbooks/<name>/scripts/init.js' \
  --timeout-ms 660000 --max-heap-size-mb 1024 --args '{
  "root": "/alva/home/<user>/playbooks/<name>", "cash": 0,
  "holdings": [{"symbol":"NVDA","assetClass":"us_equity","name":"NVIDIA","shares":60,"avgCost":150}]}'
```

**Verify by its artifacts, not its status** — `feed.run` swallows exceptions. Check that
`data/baselines.json` has a `signalGrades` entry per symbol; a symbol with none will never push.

⚠️ **`init.js` is the only place `signalGrades` is computed, and it gates every push.** It
runs the criterion on the series each signal actually fires on — daily closes for PV1,
15-minute bars for PV5 — with `B = 20000` and a seed derived from the symbol. Do not
reimplement it: the criterion sits on a hard line at 1.0, and a wrong implementation moves
every symbol's delivery tier without erroring.

**Three windows, three different numbers** (`signal-spec` → Indicator dictionary): robust
volatility and volume median use one, the percentile distribution another, and the
minimum-usable threshold a third — **a threshold is not a window; below it the signal is
disabled.**

### 7.1 Cost is almost entirely "how many cards called the model today"

Attribution is the only `ask()` in the chain; nearly every data endpoint is free.
**Do not put unit prices here** — platform pricing changes; how to check is in
`alva-platform` → Billing.

```
Only cards in the alert stream    user lines · EV4 · L3 and below never call
One card, one call                iterate after merging, not per signal
Cap in config/alerts.json         attribution.dailyCap, reset per UTC day, user-adjustable
Say when it runs out              the card says "daily limit reached", never "no reporting found"
Out of budget means degrade       send the alert without an explanation; never stall the chain
Carry results across runs         never re-ask what was already asked; the test is whether
                                  generatedAt is set, not whether there is any text
```

**Alerts cluster during regime changes**, because the baseline is a rolling window and a new
volatility regime is extreme against the old one.
**Sizing the budget by the average exhausts it exactly on the days explanations matter most.**

---

## Step 8 · Release

The first seven steps produce files. **This one turns them into a Playbook.**

**Full ordering, command shapes, and what breaks when each step is skipped:
`alva-platform` → Release order.** Confirm every signature with `alva <command> --help`; the
CLI changes and `--help` does not go stale.

The three most often missed:

```
Subscription     without alva alert enable the page opens and nothing ever pushes.
                 It is the one step that leaves no artifact behind
Push needs three declare an alert output · a root-level body field in the TypeDoc ·
                 the run must come from the bound cronjob. None of them errors when missing.
                 See alva-platform -> Push requires three things at once
Design gate      alva lint playbook error-level findings really do block the release.
                 Run it locally first
```

**Draft before publishing.** Skipping the draft pushes a page nobody has looked at.

**Two flags the CLI's `--help` will lead you astray on:**

```
--skill-id     OMIT IT. The help text shows `alva/screener`, and both of a real eval's
               agents went looking for a plausible value: one picked
               `alva/portfolio-watch-setup` — an Alva-authored skill with a similar name.
               The published page then reads "Built with: Portfolio Watch Setup ·
               Created by Alva", which is a provenance claim, and a false one.
               Claiming no provenance is better than claiming someone else's.
--tags         Descriptive only. Do not put a signal ID or a threshold in here;
               tags are not a contract and nothing validates them.
```

**Verify `config/alerts.json` exists before you release.** It is the only user-writable file —
it carries the attribution cap, the push channel, quiet hours, and the user's own lines.
One of two eval agents skipped creating it, and nothing complained: the page 404s on it and
silently falls back to defaults, so "never created" and "created with defaults" look identical.

```bash
alva fs stat --path "$ROOT/config/alerts.json"   # must succeed before release
```

---

## What you produce

**File list and field definitions: `data-contract` → File layout.** Do not write field names from memory.
`config/alerts.json` is the only writable file; `data/state.json` is the only read-modify-write
one; everything else is overwritten each run.

**1 · The page is self-contained.** Beyond the design-system CSS and the chart library it
depends on nothing external, and it needs no build step.

**2 · All data comes from fetch, with no inlined fixtures.** A different JSON is a different
portfolio's page.

**3 · Bilingual, following the language the user speaks.** Switching language changes the page
content including chart axes — chart libraries read the browser locale by default and must be
set explicitly.

**4 · Every number is traceable.** For any number on screen the reader can find which field of
which file it came from. Two views of the same fact use the same numbers — not a z score in
one place and a percentage in the other.

---

## Never do this

| Never | Why |
|---|---|
| Predict direction | Outcomes split evenly after a trigger; any directional phrasing overreaches |
| Give trading advice | No "consider trimming", no "worth watching" |
| Technical indicators — RSI · MACD · Bollinger · moving-average crosses | They are predictive by construction, so a user will read them as signals, and not one was validated here. **Showing a predictive indicator without evidence is worse than not showing it** |
| Fixed-percentage alert thresholds | "Down 5% today" ignores the symbol's own normal. The same −6% is 6× normal for a low-volatility name and 1.5× for a high-volatility one |
| Say "no cause found" without qualifying it | Most alert days have no material; that is normal, not an omission. Saying "nothing found" is fine only in the same sentence as "which is normal" |
| Rank symbols by reliability | Per-symbol rank does not survive out of period — an in-sample description, not a runtime property |
| Suppress by frequency | "Too many alerts today" is not legitimate; it delivers fewest when the user needs most |
| Invent thresholds or rewrite the attribution prompt | Both have verbatim specifications; replacing them discards all the evidence behind them |
