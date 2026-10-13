# Climate Signals Dashboard (formerly the Weather Impacts Dashboard)

**Live: https://quantarram.github.io/weather-impacts-dashboard/**

A daily-updated, self-scoring record of rare, slow climate conditions and what happens to markets after they fire. Each condition is a conditional-exceedance (CPE) row: *when this climate series is in its extreme tail, how often does that market follow into its own tail over the next N days?* Every condition is frozen in advance with its threshold fixed from data through 2012, logged the day it first fires, and scored only on what happens afterwards.

This is the live counterpart of **Paper 17**, *Why Everyday Weather Does Not Move Markets, and Where Rare Extremes Might* ([Zenodo](https://zenodo.org/records/23301263), [Substack](https://arunramanathans.substack.com/p/why-everyday-weather-does-not-move)). The paper's result is a candidate, not a finding: rare extreme tails showed persistence only inside the CPE framework's own selection rules, on few episodes, and a simple trading rule on them lost money in the causal backtest. This dashboard collects the forward evidence. Code and research scripts: [quant-regime-research](https://github.com/quantarram/quant-regime-research) (`notebooks/weather_finance/`).

## What the front page shows
- **Climate state now**: the Oceanic Nino Index and the Nino 3.4 anomaly.
- **Frozen conditions**: four tables, 97 conditions in all, each with where the series stands against its threshold, an event log, and a live record of resolved and pending outcomes.
- **Registered decision experiment**: the strong-evidence conditions turned into implied paper positions by one fixed rule, scored daily against holding the same targets and SPY.
- **A backtest panel** with the causal walk-forward of the same rule (no historical edge).

## The four frozen tables
| Table | Rows | Conditions | Series | Frozen | Role |
|---|---|---|---|---|---|
| Batch 1 | 43 | 7 | ONI, Nino 3.4, SOI, Arctic, North Atlantic and Pacific Decadal oscillations | 2026-10-10 | survivors; in the decision rule |
| Batch 3 | 181 | 41 | Nino 1+2/3/4, MEI v2, tropical Atlantic, Atlantic warm pool, PNA, Southern Annular Mode | 2026-10-11 | survivors; in the decision rule |
| Batch 4 | 38 | 22 | regional drought (Delta, Southeast, Texas, northern plains, West), Trans-Nino, North Pacific Gyre Oscillation, global temperature, snow cover | 2026-10-11 | survivors; in the decision rule |
| Batch 5 | 44 | 27 | 14 non-ENSO predictor families | 2026-10-12 | watch tier, weaker evidence; condition ledger only |

Tables from weekly freezes (b6, b7, ...) are listed in `data/cpe_climate/books.json`. Most rows are ENSO indices that move together, so they are one ocean state restated, not independent findings; the page says so next to each table.

## How a condition is scored
A condition fires on the first day its series crosses its frozen threshold (conditions already beyond it at the freeze are logged once as "ongoing"). Each firing opens an outcome for every row of that condition: did the target's forward move over the row's horizon (21 to 300 days) land beyond its frozen threshold in the stated direction? The page reports the claimed probability (formation), the realised hit rate and both base rates. Horizons are in the target's own trading days (a 252-day horizon is 252 of its bars, about 14 calendar months for a weekday market). Until 2026-10-14 they were counted in rows of the seven-day price calendar, which made a 252-day horizon 252 calendar days; no outcome had resolved by then, and the registered decision experiment's positions now run for the trading-day horizon. No significance test is used; overlapping horizons are valid samples.

## Registered decision experiment
Registered 2026-10-11, scored from 2026-10-12 (`weatherdash/climate_decisions.py`, `data/climate_decisions_daily.csv`). Each firing condition votes on its target's direction until its horizon expires; opposite votes cancel; the active targets are held at equal weight, at 10 bp per unit of turnover. Benchmarks are the same targets held long, SPY, and drift-adjusted excess. Reviews come at 125, 250 and 500 trading days, and the verdict rule ("evidence of an edge" or "no evidence of an edge") is fixed in advance. Positions are paper positions, not advice. The weekly tables are outside this rule.

## Daily and weekly routines
- **Daily** (08:30 UTC, `pipelines/run_daily.py`): refreshes the climate indices and prices, logs new entry events, scores resolved outcomes and rebuilds the page. `python pipelines/daily_summary.py` prints what changed since the previous day.
- **Weekly**: new, distinct conditions are frozen by a fixed rule (`FREEZE_RULES.md`; script `weekly_freeze.py` in the research repo). Most weeks may freeze nothing.

## Data and licences
- Climate indices: NOAA Climate Prediction Center and Physical Sciences Laboratory (ONI, Nino regions, SOI, AO, NAO, PDO, MEI v2, TNA, TSA, warm pool, PNA, AAO, TNI, NPGO).
- Drought: NOAA NCEI nClimDiv state Palmer Drought Severity Index. Global temperature: NASA GISS GISTEMP v4. Snow cover: Rutgers Global Snow Lab.
- Prices: Yahoo Finance public chart data (small stores in `data/cpe_climate/`).
- Contains ECMWF open data (CC-BY-4.0) only in the archive panels.

## Layout
```
weatherdash/cpe_climate.py        frozen-condition ledger: index parsers, watchlist, entry events, forward scoring, tables (books)
weatherdash/climate_decisions.py  the registered decision experiment
weatherdash/signals_page.py       the front page (data/signals.json)
weatherdash/prices.py             Yahoo chart fetcher
pipelines/run_daily.py            the daily job (climate stage first, then the archive stage)
pipelines/build_site.py           builds docs/index.html and docs/archive.html
pipelines/daily_summary.py        what changed since yesterday
data/cpe_climate/                 frozen tables, price stores, event logs, index files, books.json, backtest export
data/signals.json                 page payload; data/climate_decisions_daily.csv paper-portfolio returns
FREEZE_RULES.md                   the daily and weekly routines and the freeze rule
ARCHIVE.md                        the earlier daily weather-forecast panels (modules, pipeline, limits)
```

## Scope and limits
Research record, not advice and not a trading tool. The conditions rest on few independent episodes: a rare climate state is a handful of occurrences in four decades, so forward results accrue slowly (the first outcomes resolve about 2026-12-12, most through 2027) and a few resolved outcomes cannot separate a real edge from luck. Survivor tables were selected using test-period results, so their test scores are upward-biased; only the live record is free of that. The weather-forecast archive is in [ARCHIVE.md](ARCHIVE.md).

## Citation

If you find this work useful, please cite the relevant paper(s):

**Paper 17: the research behind this dashboard**
```
RAMANATHAN S, A. (2026). Why Everyday Weather Does Not Move Markets, and
Where Rare Extremes Might. Zenodo.
https://doi.org/10.5281/zenodo.23301263
```

**Method: the conditional exceedance (CPE) framework**
```
RAMANATHAN S, A. (2026). A Conditional Exceedance Framework for
Interpretable Trading Decisions. Zenodo.
https://doi.org/10.5281/zenodo.20769150
```

**This dashboard (code and data)**
```
RAMANATHAN S, A. (2026). Climate Signals Dashboard (formerly the Weather
Impacts Dashboard) [software and data]. GitHub.
https://github.com/quantarram/weather-impacts-dashboard
```
