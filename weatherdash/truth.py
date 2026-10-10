"""Observed temperature (ERA5 reanalysis via Open-Meteo, free, no key) for verification and model fitting."""
import time

import pandas as pd
import requests

API = "https://archive-api.open-meteo.com/v1/archive"


def city_daily_mean_c(lat, lon, tz, start, end, tries=6):
    """Daily mean 2 m temperature (deg C) of the local civil day, from hourly ERA5."""
    params = dict(latitude=lat, longitude=lon, start_date=start, end_date=end, hourly="temperature_2m",
                  timezone=tz)
    for a in range(tries):
        r = requests.get(API, params=params, timeout=90)
        if r.status_code == 200:
            h = r.json()["hourly"]
            s = pd.Series(h["temperature_2m"], index=pd.to_datetime(h["time"]), dtype=float)
            return s.groupby(s.index.date).agg(lambda x: x.mean() if x.count() >= 23 else float("nan")).dropna()
        time.sleep(min(2 ** a * 2, 30))
    raise RuntimeError(f"Open-Meteo failed for {lat},{lon}: {r.status_code} {r.text[:120]}")


def city_daily_history(lat, lon, tz, start, end, tries=6):
    """Daily mean 2 m temperature (deg C), local civil day, over a long span (daily endpoint)."""
    params = dict(latitude=lat, longitude=lon, start_date=start, end_date=end, daily="temperature_2m_mean",
                  timezone=tz)
    for a in range(tries):
        r = requests.get(API, params=params, timeout=120)
        if r.status_code == 200:
            d = r.json()["daily"]
            s = pd.Series(d["temperature_2m_mean"], index=pd.to_datetime(d["time"]), dtype=float)
            return s.dropna()
        time.sleep(min(2 ** a * 2, 30))
    raise RuntimeError(f"Open-Meteo failed for {lat},{lon}: {r.status_code} {r.text[:120]}")
