# Weather to Energy Dashboard

A daily-updated, self-scoring dashboard of how forecast weather translates into electricity demand and
wind and solar generation (pilot: six US grid regions), plus a crop-stress layer for the US corn and soybean states.

Every day (08:30 UTC, after the ECMWF 00z open-data cycle is published) a GitHub Action:

1. reads the **IFS 2 m temperature, 100 m wind and surface solar radiation forecasts** for each region's load centres and generation areas straight from ECMWF's
   open-data mirror, **in memory** (index files give byte ranges, so only the needed fields are fetched;
   nothing raw is stored),
2. turns it into population-weighted regional daily temperature, heating/cooling degree days and a
   **demand forecast next to the demand that normal weather would imply**,
3. turns 2 m temperature, dew point, rainfall and daily maximum temperature at ten US crop states into weekly
   **heat-stress, vapour-pressure-deficit and rainfall drivers** (vs normal) and an expected change in the USDA
   good+excellent corn/soybean rating,
4. appends the forecasts to small **ledgers** (`data/ledger_temp_demand.csv`, `data/ledger_wind_solar.csv`, `data/ledger_crops.csv`),
5. **scores** every forecast whose day has passed against ERA5 weather, EIA-930 demand and wind/solar
   generation, and USDA NASS weekly crop condition (streamed from the Quick Stats bulk file, no key), with normal
   weather as the baseline,
6. publishes the dashboard (force-pushed to `gh-pages`, so history does not grow).

## Data and licences
- Forecasts: ECMWF open data (IFS, 0.25 deg), CC-BY-4.0. Contains ECMWF open data.
- Observed temperature: ERA5 reanalysis (Copernicus) via Open-Meteo, CC-BY-4.0.
- Demand and generation: U.S. EIA Form 930 hourly grid data (public).
- Crop condition: USDA NASS Quick Stats (public).

## Layout
```
weatherdash/fetch.py      byte-range fetch from the ECMWF mirrors (retry + mirror fallback)
weatherdash/grib.py       in-memory GRIB decode + bilinear point sampling
weatherdash/regions.py    pilot regions, load centres, approximate population weights
weatherdash/demand.py     temperature -> daily demand model (degree days, day of week, trend)
weatherdash/forecast.py   forecast -> regional temperature, degree days, demand, wind and solar vs normal
weatherdash/renewables.py learned wind power curve (hat basis) and solar map, capacity-growth term
weatherdash/crops.py      state points, weekly heat/VPD/rain drivers
weatherdash/nass.py       USDA NASS weekly condition from the Quick Stats bulk file
weatherdash/ledger.py     forecast ledger and verification vs climatology
weatherdash/dashboard.py  single-page dashboard
pipelines/fit_demand_model.py   one-off demand model fit (2023-2025 train, 2026 holdout)
pipelines/fit_renewables.py     one-off wind/solar fit (site weights learned from EIA output)
pipelines/fit_crops.py          one-off crop-condition model (ten-state average, leave-one-year-out)
pipelines/run_daily.py          the daily job
pipelines/backfill.sh           score archived past forecasts
```

## Scope and limits
Pilot only: six US balancing authorities. Regional temperature is a
population-weighted point sample (approximate weights); the demand model has no holiday, humidity or
behind-the-meter solar terms. Wind and solar levels are re-anchored each day to the last 28 days of observed output (the learned maps
drift as capacity is added); correlation with observed output is untouched. Crop layer: corn and soybean ratings run
about June to mid-September, so the rating outlook is off outside the season while the weather drivers run all year;
weekly condition change is a noisy target, so it is modelled for the ten-state average. Next: soil moisture, winter
wheat and non-US regions. Research record, not an operational or trading tool.
