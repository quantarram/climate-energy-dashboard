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


def site_hourly(lat, lon, tz, start, end, tries=8, cache_dir=None):
    """Hourly ERA5 100 m wind speed (m/s) and surface solar radiation (W/m2, mean over the preceding hour),
    local time, as a DataFrame. Split by year so each response stays small; finished past years are cached
    on disk when cache_dir is given (fitting only -- the daily job never caches)."""
    import os
    frames = []
    for y in range(int(start[:4]), int(end[:4]) + 1):
        s, e = max(start, f"{y}-01-01"), min(end, f"{y}-12-31")
        cpath = os.path.join(cache_dir, f"{lat}_{lon}_{tz.replace('/', '-')}_{y}.csv") if cache_dir else None
        if cpath and y < int(end[:4]) and os.path.exists(cpath):
            frames.append(pd.read_csv(cpath, index_col=0, parse_dates=True))
            continue
        params = dict(latitude=lat, longitude=lon, start_date=s, end_date=e, timezone=tz, wind_speed_unit="ms",
                      hourly="wind_speed_100m,shortwave_radiation")
        df = None
        for a in range(tries):
            try:
                r = requests.get(API, params=params, timeout=120)
                if r.status_code == 200:
                    h = r.json()["hourly"]
                    df = pd.DataFrame({"wind100": h["wind_speed_100m"], "ghi": h["shortwave_radiation"]},
                                      index=pd.to_datetime(h["time"]))
                    break
            except (requests.RequestException, ValueError):
                pass
            time.sleep(min(2 ** a * 2, 60))
        if df is None:
            raise RuntimeError(f"Open-Meteo hourly failed {lat},{lon},{y}")
        if cpath and y < int(end[:4]):
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(cpath)
        frames.append(df)
        time.sleep(0.25)
    return pd.concat(frames).astype(float)


def point_hourly(lat, lon, tz, start, end, tries=8, cache_dir=None):
    """Hourly ERA5 2 m temperature, dew point (deg C) and precipitation (mm), local time; finished past years cached on
    disk when cache_dir is given (fitting only)."""
    import os
    frames = []
    for y in range(int(start[:4]), int(end[:4]) + 1):
        s, e = max(start, f"{y}-01-01"), min(end, f"{y}-12-31")
        cpath = os.path.join(cache_dir, f"crop_{lat}_{lon}_{tz.replace('/', '-')}_{y}.csv") if cache_dir else None
        if cpath and y < int(end[:4]) and os.path.exists(cpath):
            frames.append(pd.read_csv(cpath, index_col=0, parse_dates=True))
            continue
        params = dict(latitude=lat, longitude=lon, start_date=s, end_date=e, timezone=tz,
                      hourly="temperature_2m,dew_point_2m,precipitation")
        df = None
        for a in range(tries):
            try:
                r = requests.get(API, params=params, timeout=120)
                if r.status_code == 200:
                    h = r.json()["hourly"]
                    df = pd.DataFrame({"t2m": h["temperature_2m"], "d2m": h["dew_point_2m"], "precip": h["precipitation"]},
                                      index=pd.to_datetime(h["time"]))
                    break
            except (requests.RequestException, ValueError):
                pass
            time.sleep(min(2 ** a * 2, 60))
        if df is None:
            raise RuntimeError(f"Open-Meteo hourly failed {lat},{lon},{y}")
        if cpath and y < int(end[:4]):
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(cpath)
        frames.append(df)
        time.sleep(0.25)
    return pd.concat(frames).astype(float)
