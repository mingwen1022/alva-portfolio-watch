# Data sources

Every endpoint the settled signals need, the fetch semantics that fail silently, and the
contract the attribution call has to satisfy.

Signal definitions are in `signal-spec.md`. Output fields are in `data-contract.md`.

## Endpoints

| Source | Endpoint | Feeds | Depth and cost |
|---|---|---|---|
| US daily bars | `/api/v1/stocks/kline` | M1–M4 · M23 | 2018-01 onward · free |
| Crypto daily bars | `/api/v1/crypto/binance/spot/usdt/kline` | M1–M4 · M23 | 2018-01 onward · free |
| US intraday bars | `/api/v1/stocks/kline` with `interval=15min` | PV5 | 366 days per query max · free |
| Insider transactions | `/api/v1/stocks/insider/transactions` | M7 · M8 | 8.5 years · **1 credit per call** |
| Funding rate | `/api/v1/crypto/funding-rate` | M12 | 2020-03 onward · free |
| Company news | `/api/v1/stocks/market-news` | EV6 | **1 credit per call** · field table in `signal-spec.md` |
| Earnings calendar | `/api/v1/stocks/earnings-calendar` | EV4 | free · about 30 days of lead time |
| Company detail | `/api/v1/stocks/company/detail` | logo · sector · ipo_date | **billing unverified — check before use** |
| Market benchmark | US daily bars with `symbol=SPY` | enrichment block 1 | free |
| Index quotes | `/api/v1/macro/index/real-time?symbol=` | market page | free · `^GSPC` `^IXIC` `^DJI` `^VIX`, URL-encode the caret |
| Index roster | `/api/v1/macro/index/symbols` | discovering valid symbols | free |
| Treasury curve | `/api/v1/macro/treasury-rates?limit=1` | market page | free |
| Commodities | `/api/v1/macro/commodity/real-time?symbol=` | market page | free · `GCUSD` `SIUSD` `CLUSD` `NGUSD` `HGUSD` |
| Crypto sentiment | `/api/v1/crypto/fear-greed-index` | market page | free · needs `start_time` and `end_time` |

**Confirm billing before relying on any endpoint being free.** Several endpoints in this
project were documented as free and later measured as billed. How to check:
`alva-platform.md` → Billing.

**`POST /api/v1/social-feeds/x/handles` is a billed premium discovery unit. Do not call it.**

### What these endpoints cannot give you

Say so on the page rather than substituting something close.

| Wanted | Reality |
|---|---|
| A daily change on an index or commodity | The real-time endpoints return **one point and ignore a time range**. Carry the previous session's price forward in `market.json` and difference against it; the first run reports `null`. Never write 0 — "unchanged" is a claim, "unknown" is not |
| Total crypto market cap, BTC dominance | `/api/v1/crypto/market-cap` **requires a symbol** and there is no total. Reporting BTC's own cap as the total would be wrong and dominance cannot be derived from one number. Leave both `null` and add `crypto_market_totals_unavailable` to `meta.gaps` |
| Theme membership for PF2 and PF3 | Only via an MCP tool, **which bills as an `ask()` call**, not as a free data endpoint. Budget for it or leave the theme slice out and say the book has no theme data |
| A screener for the fallback threshold pool | Not among the documented endpoints. Without it, an unvalidated asset class falls to the fewer-than-12 branch and takes the US constants |
| A forward macro calendar (FOMC, CPI) | No endpoint. Reminders of that kind cannot be built, and the capability boundary must say so |

## Fetch semantics

Each of these fails without raising.

```
Responses come newest-first        reorder before using
Field names differ by asset class  equity  time_period_start / price_close / volume_traded
                                   crypto  time_open / price_close / volume
start_time and end_time required   omitting either returns 400 — not a backend fault
limit silently truncates           funding rate defaults to 30, caps at 1000
limit has a ceiling                crypto daily is about 3000; exceeding it fails the whole segment
Crypto symbols are pairs           BTCUSDT, not BTC
Intraday interval is "15min"       "15m" returns 400
Count failed segments separately   "ERR 400" is not "one bar". Folding failures into a
                                   success count makes a 400 look like a fetch that worked
Drop the first bar of each day     its previous bar is yesterday's close, not a bar-sized move
```

**US intraday covers regular hours only, and the window must be derived from ET.** Daylight
time makes 09:30–16:00 ET equal 13:30–20:00 UTC; standard time makes it 14:30–21:00 UTC.
**Hardcode either constant and half the year is off by an hour** — an hour of pre-market
pulled in, the last hour of the session dropped.

**"25–26 bars a day" cannot detect that.** Both windows are 6.5 hours, so the count is right
either way and the check passes during the wrong half of the year. **Check the boundaries
instead:** the first bar of each day must be 09:30 ET and the last 15:45 ET.

**When an intraday volume ratio comes out at 20–50×, check the bar's time first.** Same-slot
volume medians in pre-market are near zero, so any trade at all produces a huge ratio.

## The EV6 filter chain

Four deterministic steps, in order. This chain selects the material handed to attribution.

```
1  Ticker relevance   tickers[].relevance_score == 1.0 for this symbol
2  Event topic        topics[] contains earnings, M&A or IPO at relevance >= 0.5
3  Timing             |publish_time − alert_time| <= 120 minutes AND publish_time <= alert_time
4  Ordering           newest first, take 3
```

**Step 3's second condition is an admission test, not a sort.** Coverage is 19.01% with it
and 25.73% without, and 26.1% of the difference is after-the-fact reporting. Admitting
reporting written *about* the move is close to circular.

**Filter before sorting, never the reverse.** News density differs by a factor of 500 across
symbols; taking "the 3 most recent" from a heavily covered name returns the last twenty
minutes of syndication.

**This chain is for the coverage measurement. The live attribution retrieval uses a
different window** — see below. The two are not interchangeable.

## Attribution

**The prompt lives in `scripts/attribution.js`.** It is the only copy. Use that module rather
than redrafting the prompt — the wording encodes measured failures, and a second copy drifts.

### Shape of the call

```
one card  =  one call  =  one explanation
```

Merging decides how many cards exist, not how many explanations a card gets. A single-signal
card is the degenerate case and still takes one call. **EV4 and user lines are never
attributed.**

Attribution runs **after ordering**, once the card is committed. It cannot change whether or
where anything is delivered. When the call fails, the alert still goes out without an
explanation.

### Retrieval window

**±120 minutes in both directions.** Reporting filed after the move is collected.

News lags the move it describes — traders act well before a newsroom writes it up — so a
before-only window filters out the real explanatory material, on crypto especially, where the
strict chain returns nothing at all.

**But the model must not comment on whether an item preceded or followed the move.** The
offset is already computed and printed next to each source for the reader. Asking the model
to restate it produces a negation that consumes the whole character budget and adds nothing.

### What code computes, what the model does

| Computed in code | Produced by the model |
|---|---|
| the timing value: before / after / untimed / none | the explanation paragraph |
| every offset shown next to a source | additional sources it found itself |
| the size rank and its qualifier | — |
| the number whitelist | — |

**The model never produces the timing badge.** Only chain-retrieved sources decide it;
model-found sources have unverifiable publication times and can only push it to `untimed`.
**`untimed` must not collapse into `none`** — that prints "nothing found" above real sources.

**Do not pass a `model` parameter**; use the platform default. `attribution.model` is always
`null` because `ask()` does not return a model name, so **never use it to test whether
attribution ran** — that test reads `generatedAt`.

### Output contract

```json
{"explanation": "<English, 2 to 3 sentences, at most 220 characters>" or null,
 "additionalSources": ["https://…"]}
```

`explanation: null` is a legal answer meaning "nothing found", not a parse failure. Record it
as its own outcome; folding it into a failure count makes "we looked and found nothing"
indistinguishable from "the model broke".

### Two hard gates

```
Gate 1  number whitelist   every number in the output must appear in the rendered prompt text.
                           Normalize before comparing: strip sign, thousands separators,
                           trailing zeros, and a trailing % or x
Gate 2  no source, no ship an explanation must rest on at least one source, retrieved or
                           model-found. With none, discard it and record what was discarded
```

**Only these two are hard gates, because they are the failures a user cannot detect.**
Whether the prose reads well is visible to anyone; whether a z score is −5.56 or −6.5 is not,
and an explanation with no source behind it reads exactly like one with sources.

**Gate 2 must exist in code, not only in the prompt.** Measured twice: with empty material the
model would not return `null` and instead assembled a sentence out of "a broader crypto rally"
and "posts on X", with an empty source list.

**Build the whitelist from the rendered prompt text, not by re-formatting the source data.**
Rendering the same number twice — once at one decimal for the prompt, once at two for the
whitelist — rejects the correct value the model copied.

**Never validate a source by HTTP status.** Paywalled sites return 401/403 to anything that is
not a browser, so real and fake URLs answer identically.

Wording, length, language and disclaimers are **recorded, not blocked**. Detect disclaimers by
sentence shape rather than a word list, strip them, and record that you stripped something —
silently editing a model's output is speaking for it.

### Daily cap

`config/alerts.json` holds `attribution.dailyCap`, reset per UTC day, adjustable by the user.

```
Counted per card, not per signal   a merged card is one unit
First come, first served           waiting for the close to pick the best ones delays every push by a day
Carry results across runs          the test for "already asked" is whether generatedAt is set,
                                   not whether there is any text. A result of "found nothing"
                                   must carry forward too, or the next run re-asks and
                                   the page loses the answer
When exhausted                     the card says the daily limit was reached — never
                                   "no reporting found", which is a different statement
```
