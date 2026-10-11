# How conditions are frozen, and the daily and weekly routines

## Daily
The workflow runs every day at 08:30 UTC (`pipelines/run_daily.py`): it refreshes the climate indices and prices, logs new entry events for every frozen condition, scores outcomes as horizons resolve, and rebuilds the page.
`python pipelines/daily_summary.py` prints what changed since the previous day's committed payload (newly firing and ended conditions, new entry events, resolved outcomes, the registered decision experiment).

## Weekly freeze of new, distinct conditions (`notebooks/weather_finance/weekly_freeze.py` in quant-regime-research)
The rule is fixed and applies unchanged every week:
1. Re-evaluate the four batches' formation rows (formation through 2012, thresholds frozen) with test data through the freeze date.
2. Candidates are watch-tier rows (at least 3 formation and 2 test episodes, test hit rate at least 2/3, test CPE at least 10 points above the test base rate, at least 100 test days) that are not already frozen.
3. Exclude the ENSO family (frozen in 224 overlapping rows) and series with no live feed or with look-ahead or external-weight problems (ACE, CBTMP, HDDGAS, CDDPOW, ICE, IOD).
4. Keep a row only if its (predictor family, target, direction) is not already in any frozen table, and keep one row per such combination (highest formation conviction).
5. If nothing passes, nothing is frozen. Otherwise the new rows become the next table (b6, b7, ...), registered in `data/cpe_climate/books.json`.
Weekly tables are condition ledgers only: they are outside the registered decision rule, which covers the tables frozen with it (batches 1, 3 and 4).

Expect most weeks to freeze nothing: a row enters the watch tier only when new test episodes accumulate, which is slow for rare events. New distinct conditions mainly come from adding new predictor series as new batches.
