"""IFS 2 m temperature forecast -> regional daily temperature, degree days and demand."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import demand, fetch, grib, regions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "data", "demand_model.json")
STEPS = list(range(0, 145, 3)) + list(range(150, 361, 6))  # IFS open data: 3-hourly to 144 h, 6-hourly to 360 h


def load_model():
    return json.load(open(MODEL_PATH))


def _t2m_at_points(date, cycle, step, lats, lons):
    buf = fetch.ifs_fetch(date, cycle, step, {("sfc", "2t")})
    for h in grib.messages(buf):
        v, _ = grib.sample(h, lats, lons)
        return v - 273.15
    raise RuntimeError(f"no 2t message for step {step}")


def fetch_t2m(date, cycle, workers=6):
    """DataFrame [valid_time_utc x city] of forecast 2 m temperature (deg C) at the load-centre points."""
    pts = regions.all_points()
    lats, lons = [p[2] for p in pts], [p[3] for p in pts]
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(lambda s: _t2m_at_points(date, cycle, s, lats, lons), STEPS))
    init = pd.Timestamp(f"{date} {cycle:02d}:00", tz="UTC")
    idx = [init + pd.Timedelta(hours=s) for s in STEPS]
    return pd.DataFrame(np.array(rows), index=pd.DatetimeIndex(idx), columns=[f"{p[0]}|{p[1]}" for p in pts])


def city_daily_means(t):
    """Local-civil-day mean temperature per city from the (3/6-hourly) series, linearly interpolated to hourly.
    Only days fully inside the forecast span are kept."""
    hourly = t.resample("1h").interpolate("linear")
    out = {}
    for col in hourly.columns:
        reg, city = col.split("|")
        tz = regions.city_tz(reg, city)
        s = hourly[col].tz_convert(tz)
        g = s.groupby(s.index.date)
        d = g.mean()[g.count() == 24]
        out[col] = pd.Series(d.values, index=pd.to_datetime(d.index))
    return pd.DataFrame(out)


def region_daily(daily):
    """Population-weighted regional daily mean temperature (deg C), for dates complete in every city of the region."""
    res = {}
    for reg, spec in regions.REGIONS.items():
        cols = [f"{reg}|{c}" for c in spec["cities"]]
        w = np.array([spec["cities"][c][2] for c in spec["cities"]], float)
        sub = daily[cols].dropna()
        res[reg] = pd.Series((sub.values * (w / w.sum())).sum(axis=1), index=sub.index)
    return res


def impact(reg_temps, model, issue_date):
    """Per region/day: forecast and normal temperature, degree days, and demand forecast vs normal."""
    rows = []
    for reg, s in reg_temps.items():
        m = model["regions"][reg]
        normal = np.array(m["normal_temp_c_by_doy"])
        dates = s.index
        t_norm = normal[np.minimum(dates.dayofyear, 366) - 1]
        d_fc = demand.predict(m["beta"], dates, s.values)
        d_norm = demand.predict(m["beta"], dates, t_norm)
        hdd, cdd = demand.degree_days(s.values)
        for i, d in enumerate(dates):
            rows.append({"region": reg, "valid_date": d.strftime("%Y-%m-%d"),
                         "lead_days": int((d.date() - issue_date).days),
                         "t_fc_c": round(float(s.values[i]), 2), "t_normal_c": round(float(t_norm[i]), 2),
                         "hdd_fc": round(float(hdd[i]), 1), "cdd_fc": round(float(cdd[i]), 1),
                         "demand_fc_mwh": round(float(d_fc[i]), 0), "demand_normal_mwh": round(float(d_norm[i]), 0)})
    return pd.DataFrame(rows)


def run(date, cycle=0, workers=6):
    """Fetch one IFS cycle and return the impact table (issue_date = init date)."""
    t = fetch_t2m(date, cycle, workers)
    reg_temps = region_daily(city_daily_means(t))
    issue = datetime.strptime(date, "%Y%m%d").date()
    df = impact(reg_temps, load_model(), issue)
    df.insert(0, "issue_date", issue.strftime("%Y-%m-%d"))
    df.insert(1, "model", f"IFS-{cycle:02d}z")
    return df


# ---------------------------------------------------------------------------
# Wind and solar
# ---------------------------------------------------------------------------
from . import renewables  # noqa: E402

RENEW_PATH = os.path.join(ROOT, "data", "renewables_model.json")
RENEW_FIELDS = {("sfc", "100u"), ("sfc", "100v"), ("sfc", "ssrd")}


def load_renewables():
    return json.load(open(RENEW_PATH))


def _renew_at_points(date, cycle, step, lats, lons):
    buf = fetch.ifs_fetch(date, cycle, step, RENEW_FIELDS)
    out = {}
    for h in grib.messages(buf):
        v, m = grib.sample(h, lats, lons)
        out[m["shortName"]] = v
    return out


def fetch_renewable_drivers(date, cycle, sites, workers=6):
    """Per site: hourly 100 m wind speed (m/s) and hourly-mean surface solar radiation (W/m2) over the forecast,
    indexed by hour-ending UTC time (the convention ERA5 'preceding hour' fields use)."""
    lats, lons = [s[3] for s in sites], [s[4] for s in sites]
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(lambda st: _renew_at_points(date, cycle, st, lats, lons), STEPS))
    init = pd.Timestamp(f"{date} {cycle:02d}:00", tz="UTC")
    steps = np.array(STEPS)
    speed = np.sqrt(np.array([r["100u"] for r in rows]) ** 2 + np.array([r["100v"] for r in rows]) ** 2)  # [step, site]
    ssrd = np.array([r["ssrd"] for r in rows])  # accumulated J/m2 since init
    hours = np.arange(0, STEPS[-1] + 1)
    idx = init + pd.to_timedelta(hours, unit="h")
    wind = pd.DataFrame({i: np.interp(hours, steps, speed[:, i]) for i in range(len(sites))}, index=idx)
    # mean flux over each step interval, assigned to every hour-ending label inside it
    flux = np.zeros((len(hours), len(sites)))
    for k in range(1, len(steps)):
        f = (ssrd[k] - ssrd[k - 1]) / (3600.0 * (steps[k] - steps[k - 1]))
        sel = (hours > steps[k - 1]) & (hours <= steps[k])
        flux[sel] = f
    flux[0] = np.nan
    ghi = pd.DataFrame(flux, index=idx)
    return wind, ghi


def renewable_daily(wind, ghi, sites):
    """Local-day driver per site: mean wind capacity factor (wind) and mean irradiance in kW/m2 (solar); complete days only."""
    res = {}
    for i, (ba, kind, name, lat, lon) in enumerate(sites):
        tz = regions.REGIONS[ba]["tz"]
        vals = wind[i].values if kind == "wind" else ghi[i].values
        df = pd.DataFrame(renewables.driver_matrix(np.nan_to_num(vals, nan=np.nan), kind),
                          index=(wind.index if kind == "wind" else ghi.index)).tz_convert(tz)
        g = df.groupby(df.index.date)
        d = g.mean()[g.count().iloc[:, 0] == 24]
        d.index = pd.to_datetime(d.index)
        res[(ba, kind, name)] = d
    return res


def renewables_impact(daily, rmodel, issue_date):
    rows = []
    for key, m in rmodel["models"].items():
        ba, kind = key.split("|")
        cols = [daily[(ba, kind, s)] for s in m["sites"]]
        X = pd.concat([c.add_prefix(f"{i}_") for i, c in enumerate(cols)], axis=1).dropna()
        if X.empty:
            continue
        dates = X.index
        gen = renewables.generate(m, dates, X.values)
        normal = np.array(m["normal_feature_by_doy"])[np.minimum(dates.dayofyear, 366) - 1]
        yrs = ((dates - pd.Timestamp(m["t0"])).days / 365.25).values
        gen_norm = normal * (1 + m["g"] * yrs)
        for i, d in enumerate(dates):
            rows.append({"region": ba, "resource": kind, "valid_date": d.strftime("%Y-%m-%d"),
                         "lead_days": int((d.date() - issue_date).days),
                         "gen_fc_mwh": round(float(gen[i]), 0), "gen_normal_mwh": round(float(gen_norm[i]), 0)})
    return pd.DataFrame(rows)


def run_renewables(date, cycle=0, workers=6):
    sites = regions.site_list()
    wind, ghi = fetch_renewable_drivers(date, cycle, sites, workers)
    daily = renewable_daily(wind, ghi, sites)
    issue = datetime.strptime(date, "%Y%m%d").date()
    df = renewables_impact(daily, load_renewables(), issue)
    df.insert(0, "issue_date", issue.strftime("%Y-%m-%d"))
    df.insert(1, "model", f"IFS-{cycle:02d}z")
    return df
