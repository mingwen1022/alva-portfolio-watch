# Portfolio Watch

**English** · [中文](README.zh-CN.md)

An [Alva](https://alva.ai) Skill. A user describes the holdings they want watched in one
sentence; it builds a Playbook that keeps running: a four-tab dashboard, four scheduled
jobs, and alerts pushed to their phone.

The Skill owns the judgment calls: what counts as a move, what is noise, and how to order
several signals that fire at once. Thresholds come from backtests over 92 US equities and
25 crypto assets, validated per symbol rather than by one market-wide rule.

- Live instance: [alva.ai/u/mpkg1/playbooks/portfolio-watch](https://alva.ai/u/mpkg1/playbooks/portfolio-watch)
- What the Playbook does and how alerting works: [English](Playbook-overview.md) · [中文](Playbook介绍.md)
- How the problem was approached: [APPROACH.md](APPROACH.md)

## About this repository

The repository holds the Skill itself and everything it rests on. The four layers stand
on their own:

**Specification** (`product/`) is the single place where settled signals are defined:
trigger expressions, parameters, scope, and delivery tier for 13 signals, plus the data
contract for what the Skill writes. Thresholds and formulas change here.

**Evidence** (`backtest/`) records where those definitions came from: 28 candidates tested,
what the pass criterion is, which were falsified, which had too little sample, and which
hold as a mechanism but do not generalize. Conclusions are filed per signal family; how a
conclusion changed over time is kept separately in `revisions.md`.

**Evaluation** (`eval/`) answers a different question: hand SKILL.md to an agent that knows
nothing else, and check what it builds. 11 cases, 17 real runs, six judge layers, 73
recorded defects.

**Implementation** (`skill/` · `mock/` · `pipeline/`) is the deliverable, a runnable
interface with contract-shaped data, and the pipeline that generates the demo data.

`skill/references/` is a condensed English version written for the agent. It corresponds
to `product/` but addresses a different reader; `product/` is authoritative.

## Layout

| Directory | Contents |
|---|---|
| [`skill/`](skill/) | The Skill: [SKILL.md](skill/SKILL.md) · [scripts/](skill/scripts/) (init plus four producers) · [template/](skill/template/) · [references/](skill/references/) |
| [`product/`](product/) | Signal definitions · formulas · interface content · data contract · computation chain |
| [`backtest/`](backtest/) | Backtest conclusions, criteria, sample universe, data notes · [README](backtest/README.md) |
| [`eval/`](eval/) | Cases, judges, report, defect ledger · [README](eval/README.md) |
| [`mock/`](mock/) | The interface and three contract-shaped data sets |
| [`pipeline/`](pipeline/) | Fetching and building the demo data |
| [`notes/`](notes/) | Archived early research and process records |
| [`traffic/`](traffic/) | GitHub traffic history — an Action copies it daily, because GitHub keeps only 14 days |

## Running it locally

```bash
python3 -m http.server 8899 --directory mock
# http://localhost:8899/portfolio-watch-mock.html
```

`mock/` ships three books to switch between: a mixed portfolio, ETFs plus newly listed
symbols, and a first run. What the page fetches is an instance of the contract defined in
[`product/output-schema.md`](product/output-schema.md).

## Checks

```bash
python3 backtest/scripts/checks/check_consistency.py   # spec · contract · copy · producer smoke, 24 checks
python3 eval/judges/assertions.py mock/data            # artifact assertions L0–L3
node    eval/judges/l4_render.js <artifact dir>        # L4, headless render
python3 skill/bundle.py                                # build the delivery bundle
```

Every assertion is listed in [`eval/judges.md`](eval/judges.md) — 51 of them, generated
from the judge code rather than written by hand. Results per run are in
[`eval/report.html`](eval/report.html); defects are in
[`eval/badcases.md`](eval/badcases.md).

## Data

The backtest data is about 54 MB and is not in the repository. Part of it is full post text
from a third-party platform, which should not be redistributed alongside the code.
The conclusions live in the documents under `backtest/`; the raw data is only needed to
recompute them.

Sources, endpoints, parameters, billing, and known traps are in
[`backtest/data-sources.md`](backtest/data-sources.md); the scripts are in
[`backtest/scripts/fetch/`](backtest/scripts/fetch/).

## Limits

- The path to a real brokerage account has not been verified end to end. Field shapes are
  confirmed; multi-currency, SHORT positions, and margin-account weighting are not.
- Everything was tested on simulated data over a five-day build. Intraday, after-hours, and
  across-the-week execution has not been verified over repeated cycles.
- The backtest covers US equities and crypto. ETFs, HK equities, and similar classes render
  and alert correctly where history exists, but whether an alert is followed by a
  price-volume move has not been validated on those asset classes.
- The pass criterion only measures volatility amplification after a trigger. Information
  that does not express itself through volatility is outside what this ruler can measure.
- US intraday signals do not currently push to the phone: within regular trading hours the
  trigger count is too low to meet the independent-block requirement, so the per-symbol
  grade caps at L2. Crypto is not affected.

## License

[MIT](LICENSE). **This is not investment advice** — it is an engineering demonstration of
signals and alerting. No accuracy is warranted, and nothing here should be used as a basis
for trading.
