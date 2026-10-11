"""Observed weather for verification and model fitting: ERA5 reanalysis and ERA5-Land via Open-Meteo (free, no key).

The free tier rate-limits by minute, hour and day. Two modes:
  * interactive / fitting (default): wait out the limit that was hit and carry on;
  * daily CI (env OPEN_METEO_NO_WAIT=1): never wait. A limit, or an exhausted time budget (set_budget), raises
    OpenMeteoUnavailable at once, and the caller defers scoring to the next run instead of stalling the job.
"""
import datetime as _dt
import os
import time

import pandas as pd
import requests

API = "https://archive-api.open-meteo.com/v1/archive"
DEADLINE = None


class OpenMeteoUnavailable(RuntimeError):
    """Open-Meteo could not be used right now (rate limit, time budget, repeated failures)."""


def set_budget(seconds):
    """Give all Open-Meteo calls from now on a total wall-clock budget."""
    global DEADLINE
    DEADLINE = time.time() + seconds


def _reason(r):
    try:
        return str(r.json().get("reason", ""))
    except ValueError:
        return ""


def _wait_for_limit(reason):
    low = reason.lower()
    now = _dt.datetime.now()
    if "minutely" in low:
        wait = 75
    elif "hourly" in low:
        wait = 3600 - (now.minute * 60 + now.second) + 20
    else:  # daily quota resets at 00:00 UTC
        utc = _dt.datetime.now(_dt.timezone.utc)
        wait = 86400 - (utc.hour * 3600 + utc.minute * 60 + utc.second) + 180
    print(f"  Open-Meteo limit reached ({reason[:45]}); waiting {wait // 60} min", flush=True)
    time.sleep(wait)


def _get_json(params, tries=6, timeout=60):
    last = None
    for a in range(tries):
        if DEADLINE is not None and time.time() > DEADLINE:
            raise OpenMeteoUnavailable("time budget for Open-Meteo calls exhausted")
        try:
            r = requests.get(API, params=params, timeout=timeout)
        except requests.RequestException as e:
            last = type(e).__name__
            time.sleep(min(2 ** a, 20))
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                last = "unreadable response"
                time.sleep(min(2 ** a, 20))
                continue
        reason = _reason(r)
        if "limit" in reason.lower():
            if os.environ.get("OPEN_METEO_NO_WAIT") == "1":
                raise OpenMeteoUnavailable(reason)
            _wait_for_limit(reason)
            continue
        last = f"{r.status_code} {reason[:60]}"
        time.sleep(min(2 ** a * 2, 30))
    raise OpenMeteoUnavailable(f"failed after {tries} tries: {last}")


def city_daily_mean_c(lat, lon, tz, start, end):
    """Daily mean 2 m temperature (deg C) of the local civil day, from hourly ERA5."""
    h = _get_json(dict(latitude=lat, longitude=lon, start_date=start, end_date=end, hourly="temperature_2m", timezone=tz))["hourly"]
    s = pd.Series(h["temperature_2m"], index=pd.to_datetime(h["time"]), dtype=float)
    return s.groupby(s.index.date).agg(lambda x: x.mean() if x.count() >= 23 else float("nan")).dropna()


def city_daily_history(lat, lon, tz, start, end):
    """Daily mean 2 m temperature (deg C), local civil day, over a long span (daily endpoint)."""
    d = _get_json(dict(latitude=lat, longitude=lon, start_date=start, end_date=end, daily="temperature_2m_mean", timezone=tz),
                  timeout=120)["daily"]
    return pd.Series(d["temperature_2m_mean"], index=pd.to_datetime(d["time"]), dtype=float).dropna()


def _years(start, end):
    for y in range(int(start[:4]), int(end[:4]) + 1):
        yield y, max(start, f"{y}-01-01"), min(end, f"{y}-12-31")


def site_hourly(lat, lon, tz, start, end, cache_dir=None):
    """Hourly ERA5 100 m wind speed (m/s) and surface solar radiation (W/m2, mean over the preceding hour), local time.
    Split by year; finished past years are cached on disk when cache_dir is given (fitting only)."""
    frames = []
    for y, s, e in _years(start, end):
        cpath = os.path.join(cache_dir, f"{lat}_{lon}_{tz.replace('/', '-')}_{y}.csv") if cache_dir else None
        if cpath and y < int(end[:4]) and os.path.exists(cpath):
            frames.append(pd.read_csv(cpath, index_col=0, parse_dates=True))
            continue
        h = _get_json(dict(latitude=lat, longitude=lon, start_date=s, end_date=e, timezone=tz, wind_speed_unit="ms",
                           hourly="wind_speed_100m,shortwave_radiation"), timeout=120)["hourly"]
        df = pd.DataFrame({"wind100": h["wind_speed_100m"], "ghi": h["shortwave_radiation"]}, index=pd.to_datetime(h["time"]))
        if cpath and y < int(end[:4]):
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(cpath)
        frames.append(df)
        if cache_dir:
            time.sleep(4.0)
    return pd.concat(frames).astype(float)


def point_hourly(lat, lon, tz, start, end, cache_dir=None):
    """Hourly ERA5 2 m temperature, dew point (deg C) and precipitation (mm), local time; cached like site_hourly."""
    frames = []
    for y, s, e in _years(start, end):
        cpath = os.path.join(cache_dir, f"crop_{lat}_{lon}_{tz.replace('/', '-')}_{y}.csv") if cache_dir else None
        if cpath and y < int(end[:4]) and os.path.exists(cpath):
            frames.append(pd.read_csv(cpath, index_col=0, parse_dates=True))
            continue
        h = _get_json(dict(latitude=lat, longitude=lon, start_date=s, end_date=e, timezone=tz,
                           hourly="temperature_2m,dew_point_2m,precipitation"), timeout=120)["hourly"]
        df = pd.DataFrame({"t2m": h["temperature_2m"], "d2m": h["dew_point_2m"], "precip": h["precipitation"]},
                          index=pd.to_datetime(h["time"]))
        if cpath and y < int(end[:4]):
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(cpath)
        frames.append(df)
        if cache_dir:
            time.sleep(4.0)
    return pd.concat(frames).astype(float)


def soil_daily(lat, lon, tz, start, end, cache_dir=None):
    """Daily mean root-zone (0-100 cm) volumetric soil moisture (m3/m3) from ERA5-Land, layers weighted 7:21:72 by thickness."""
    cpath = os.path.join(cache_dir, f"soil_{lat}_{lon}_{tz.replace('/', '-')}.csv") if cache_dir else None
    if cpath and os.path.exists(cpath):
        cached = pd.read_csv(cpath, index_col=0, parse_dates=True).iloc[:, 0]
        if cached.index.max() >= pd.Timestamp(end) - pd.Timedelta(days=10):
            return cached
    d = _get_json(dict(latitude=lat, longitude=lon, start_date=start, end_date=end, timezone=tz,
                       daily="soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean"),
                  timeout=120)["daily"]
    df = pd.DataFrame({k: d[k] for k in d if k != "time"}, index=pd.to_datetime(d["time"])).astype(float)
    out = ((7 * df.iloc[:, 0] + 21 * df.iloc[:, 1] + 72 * df.iloc[:, 2]) / 100).rename("sm")
    if cpath:
        os.makedirs(cache_dir, exist_ok=True)
        out.to_csv(cpath)
    return out


def hourly_batch(points, hourly, start, end, extra=None, chunk=20):
    """Several locations in one request. points: [(lat, lon)]; hourly: list of Open-Meteo hourly variables.
    Returns one DataFrame per point (same order), UTC-naive hourly index, one column per variable. The window is widened a day
    on each side so every local day of [start, end] is complete after conversion to local time (to_local)."""
    a = (pd.Timestamp(start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    b = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    out = []
    for i in range(0, len(points), chunk):
        pts = points[i:i + chunk]
        params = dict(latitude=",".join(str(p[0]) for p in pts), longitude=",".join(str(p[1]) for p in pts),
                      start_date=a, end_date=b, hourly=",".join(hourly), timezone="UTC")
        if extra:
            params.update(extra)
        js = _get_json(params, timeout=120)
        if isinstance(js, dict):
            js = [js]
        for loc in js:
            h = loc["hourly"]
            out.append(pd.DataFrame({v: h[v] for v in hourly}, index=pd.to_datetime(h["time"])).astype(float))
    return out


def to_local(df, tz):
    """Re-label a UTC-naive hourly frame with local wall-clock time (what the per-location timezone requests return)."""
    d = df.copy()
    d.index = d.index.tz_localize("UTC").tz_convert(tz).tz_localize(None)
    return d
