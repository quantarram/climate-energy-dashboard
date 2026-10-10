"""
One-off (re-run occasionally) fit of the temperature->demand model for each balancing authority.

Training: 2023-2025 daily EIA-930 demand + ERA5 temperature at the region's load centres.
Held out: 2026 to date. Reports MAPE against a month x day-of-week climatology of demand.
Stores only coefficients, the temperature climatology (day-of-year, population-weighted, 1996-2025, 30 years) and
the holdout scores -- no raw data.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from weatherdash import demand, eia, regions, truth  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demand_model.json")
TRAIN_END = "2025-12-31"
HIST_START = "1996-01-01"


def region_temp_history(region, end):
    """Population-weighted daily mean temperature (deg C) of the region, 1996 to `end`."""
    cities = regions.REGIONS[region]["cities"]
    series, w = [], []
    for c, (lat, lon, wt) in cities.items():
        series.append(truth.city_daily_history(lat, lon, regions.city_tz(region, c), HIST_START, end))
        w.append(wt)
        time.sleep(0.4)
    df = pd.concat(series, axis=1).dropna()
    return (df * (np.array(w) / sum(w))).sum(axis=1)


def main():
    end = (pd.Timestamp.today().normalize() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")  # ERA5 lags ~5 days
    bas = list(regions.REGIONS)
    parts = []
    for name in eia.six_month_files(range(2023, 2027)):
        print("EIA", name, flush=True)
        parts.append(eia.daily_demand(name, bas))
    dem = pd.concat(parts)
    out = {"trained_through": TRAIN_END, "holdout_through": None, "regions": {},
           "climatology": {"years": "1996-2025", "n_years": 30, "what": "population-weighted daily mean temperature by day of year, 15-day smoothing"}}
    for ba in bas:
        t = region_temp_history(ba, end)
        y = dem[dem["ba"] == ba].set_index("date")["demand_mwh"].sort_index()
        y = y[~y.index.duplicated()]
        idx = y.index.intersection(t.index)
        y, tt = y.loc[idx], t.loc[idx]
        tr = idx <= pd.Timestamp(TRAIN_END)
        te = ~tr
        beta = demand.fit(idx[tr], tt[tr], y[tr])
        pred = demand.predict(beta, idx[te], tt[te])
        # climatology baseline: mean demand by (month, day-of-week) over the training years
        clim = y[tr].groupby([idx[tr].month, idx[tr].dayofweek]).mean()
        base = np.array([clim.get((m, d), np.nan) for m, d in zip(idx[te].month, idx[te].dayofweek)])
        ape = lambda p: float(np.nanmean(np.abs(p - y[te].values) / y[te].values) * 100)
        # temperature climatology by day-of-year over 1996-2025 (30 years), 15-day smoothing
        tn = t[t.index <= pd.Timestamp(TRAIN_END)]
        doy = tn.groupby(tn.index.dayofyear).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
        sm = pd.concat([doy.iloc[-7:], doy, doy.iloc[:7]]).rolling(15, center=True).mean().iloc[7:-7]
        out["regions"][ba] = {
            "beta": [float(b) for b in beta], "clim_temp_c_by_doy": [round(float(v), 3) for v in sm.values],
            "n_train": int(tr.sum()), "n_test": int(te.sum()),
            "test_mape_model_obs_temp": round(ape(pred), 3), "test_mape_climatology": round(ape(base), 3),
            "mean_daily_demand_mwh": round(float(y.mean()), 0),
        }
        out["holdout_through"] = str(idx.max().date())
        print(f"{ba}: n_train={int(tr.sum())} n_test={int(te.sum())}  MAPE model(obs T) {ape(pred):.2f}%  "
              f"climatology {ape(base):.2f}%", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"))
    print("saved", OUT)


if __name__ == "__main__":
    main()
