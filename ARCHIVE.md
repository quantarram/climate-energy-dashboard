# Archive: the daily weather-forecast panels

These panels were the first version of this dashboard. They turn the ECMWF open forecast into electricity demand, wind and solar generation, crop stress, gas burn and gas storage, and score themselves against what happened. The research found that free weather forecasts carry no price signal (see the paper), so they are no longer the front page. They stay on `docs/archive.html` because a second registered live experiment (`data/decision_registry.json`) is still being scored.

## The pipeline

A daily-updated, self-scoring record of how forecast weather translates into electricity demand and
wind and solar generation (pilot: six US grid regions), plus a crop-stress layer for the US corn and soybean states.

Every day (08:30 UTC, after the ECMWF 00z open-data cycle is published) a GitHub Action:

1. reads the **IFS 2 m temperature, 100 m wind and surface solar radiation forecasts** for each region's load centres and generation areas straight from ECMWF's
   open-data mirror, **in memory** (index files give byte ranges, so only the needed fields are fetched;
   nothing raw is stored),
2. turns them into population-weighted regional temperature and heating/cooling degree days (a **demand forecast
   next to the demand that climatology would imply**: the demand at the average temperature for that calendar date
   over 1996-2025, 30 years) and into **wind and solar generation forecasts** through learned weather-to-output
   maps, each next to the generation climatology would give (average wind and sunshine for that date over
   2015-2025, 11 years),
3. turns 2 m temperature, dew point, rainfall and daily maximum temperature at ten US crop states into weekly
   **heat-stress, vapour-pressure-deficit and rainfall drivers** (vs climatology: 2015-2025 average for that week of the year, 11 seasons) and an expected change in the USDA
   good+excellent corn/soybean rating,
4. appends the forecasts to small **ledgers** (`data/ledger_temp_demand.csv`, `data/ledger_wind_solar.csv`, `data/ledger_crops.csv`),
5. **scores** every forecast whose day has passed against ERA5 weather, EIA-930 demand and wind/solar
   generation, and USDA NASS weekly crop condition (streamed from the Quick Stats bulk file, no key), with climatology as
   the baseline,
6. publishes the dashboard (force-pushed to `gh-pages`, so history does not grow).

## Data and licences (archive)
- Forecasts: ECMWF open data (IFS, 0.25 deg), CC-BY-4.0. Contains ECMWF open data.
- Observed temperature: ERA5 reanalysis (Copernicus) via Open-Meteo, CC-BY-4.0.
- Demand and generation: U.S. EIA Form 930 hourly grid data (public).
- Crop condition: USDA NASS Quick Stats (public).

## Layout (archive modules)
```
weatherdash/cpe_climate.py    frozen climate signal ledger: indices, watchlist, onset events, forward scoring
weatherdash/signals_page.py   front page builder (data/signals.json)
weatherdash/fetch.py      byte-range fetch from the ECMWF mirrors (retry + mirror fallback)
weatherdash/grib.py       in-memory GRIB decode + bilinear point sampling
weatherdash/regions.py    pilot regions, load centres, approximate population weights
weatherdash/demand.py     temperature -> daily demand model (degree days, day of week, trend)
weatherdash/forecast.py   forecast -> regional temperature, degree days, demand, wind and solar vs climatology
weatherdash/renewables.py learned wind power curve (hat basis) and solar map, capacity-growth term
weatherdash/crops.py      state points, weekly heat/VPD/rain drivers
weatherdash/nass.py       USDA NASS weekly condition from the Quick Stats bulk file
weatherdash/ledger.py     forecast ledger and verification vs climatology
weatherdash/exposure.py   physical exposure: gas burned in power plants, regional gas storage, power-price sensitivity (scored vs EIA)
weatherdash/decisions.py  the live hypothesis test: frozen decision rules, scored against flat, hold and climatology-only twins
weatherdash/prices.py     daily closes for the experiment (Yahoo public chart endpoint, small log)
weatherdash/dashboard.py  single-page dashboard
pipelines/fit_demand_model.py   one-off demand model fit (2023-2025 train, 2026 holdout)
pipelines/fit_renewables.py     one-off wind/solar fit (site weights learned from EIA output)
pipelines/fit_crops.py          one-off crop-condition model (ten-state average, leave-one-year-out)
pipelines/fit_exposure.py       one-off fit of the gas-burn, storage and power-price models
pipelines/backfill_exposure.py  derive the exposure ledgers from the forecast ledgers
pipelines/run_daily.py          the daily job
pipelines/backfill.sh           score archived past forecasts
```

## Exposure panels and the live experiment
Three panels translate the forecasts into physical exposure and score them: gas-fired generation by region (EIA-930), the expected weekly change in
regional gas storage against the five-year norm (EIA weekly report), and the weather-driven premium in next-day power prices (an estimate, not scored).
A fourth section runs a **registered experiment**: decisions from the forecast signals, with rules, instruments, costs and the criterion for "evidence of an edge" frozen in
`data/decision_registry.json` on 2026-10-11 and scored from 2026-10-12 against holding nothing, holding the same instruments, and the same decisions driven by climatology alone.
The hypothesis is that free weather forecasts alone give no edge; the experiment can falsify it. A null result is not proof that no edge exists anywhere.

## Scope and limits (archive)
Pilot only: six US balancing authorities. Regional temperature is a
population-weighted point sample (approximate weights); the demand model has no holiday, humidity or
behind-the-meter solar terms. Wind and solar levels are re-anchored each day to the last 28 days of observed output (the learned maps
drift as capacity is added); correlation with observed output is untouched. Crop layer: corn and soybean ratings run
about June to mid-September, so the rating outlook is off outside the season while the weather drivers run all year;
weekly condition change is a noisy target, so it is modelled for the ten-state average. Next: soil moisture, winter
wheat and non-US regions. Research record, not an operational or trading tool.
