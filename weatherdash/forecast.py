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
    """Per region/day: forecast and climatological temperature, degree days, and demand forecast vs climatology."""
    rows = []
    for reg, s in reg_temps.items():
        m = model["regions"][reg]
        clim = np.array(m["clim_temp_c_by_doy"])
        dates = s.index
        t_clim = clim[np.minimum(dates.dayofyear, 366) - 1]
        d_fc = demand.predict(m["beta"], dates, s.values)
        d_clim = demand.predict(m["beta"], dates, t_clim)
        hdd, cdd = demand.degree_days(s.values)
        for i, d in enumerate(dates):
            rows.append({"region": reg, "valid_date": d.strftime("%Y-%m-%d"),
                         "lead_days": int((d.date() - issue_date).days),
                         "t_fc_c": round(float(s.values[i]), 2), "t_clim_c": round(float(t_clim[i]), 2),
                         "hdd_fc": round(float(hdd[i]), 1), "cdd_fc": round(float(cdd[i]), 1),
                         "demand_fc_mwh": round(float(d_fc[i]), 0), "demand_clim_mwh": round(float(d_clim[i]), 0)})
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
        clim = np.array(m["clim_feature_by_doy"])[np.minimum(dates.dayofyear, 366) - 1]
        yrs = ((dates - pd.Timestamp(m["t0"])).days / 365.25).values
        gen_clim = clim * (1 + m["g"] * yrs)
        for i, d in enumerate(dates):
            rows.append({"region": ba, "resource": kind, "valid_date": d.strftime("%Y-%m-%d"),
                         "lead_days": int((d.date() - issue_date).days),
                         "gen_fc_mwh": round(float(gen[i]), 0), "gen_clim_mwh": round(float(gen_clim[i]), 0)})
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


# ---------------------------------------------------------------------------
# Crop stress
# ---------------------------------------------------------------------------
from . import crops  # noqa: E402

CROP_MODEL_PATH = os.path.join(ROOT, "data", "crops_model.json")
CROP_FIELDS = {("sfc", "2t"), ("sfc", "2d"), ("sfc", "tp"), ("sfc", "mx2t3"), ("sfc", "mx2t6")}


def load_crop_model():
    return json.load(open(CROP_MODEL_PATH))


def _crop_at_points(date, cycle, step, lats, lons):
    buf = fetch.ifs_fetch(date, cycle, step, CROP_FIELDS)
    out = {}
    for h in grib.messages(buf):
        v, m = grib.sample(h, lats, lons)
        out[m["shortName"]] = v
    return out


def fetch_crop_drivers(date, cycle, points, workers=6):
    """Per point: hourly 2 m temperature and dew point (deg C), hourly rain (mm), and window-maximum temperature,
    indexed by hour-ending UTC time."""
    lats, lons = [p[1] for p in points], [p[2] for p in points]
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(lambda st: _crop_at_points(date, cycle, st, lats, lons), STEPS))
    init = pd.Timestamp(f"{date} {cycle:02d}:00", tz="UTC")
    steps = np.array(STEPS)
    hours = np.arange(0, STEPS[-1] + 1)
    idx = init + pd.to_timedelta(hours, unit="h")
    t = np.array([r["2t"] for r in rows]) - 273.15
    d = np.array([r["2d"] for r in rows]) - 273.15
    t_h = pd.DataFrame({i: np.interp(hours, steps, t[:, i]) for i in range(len(points))}, index=idx)
    d_h = pd.DataFrame({i: np.interp(hours, steps, d[:, i]) for i in range(len(points))}, index=idx)
    tp = np.array([r["tp"] for r in rows]) * 1000.0  # accumulated mm since init
    rain = np.zeros((len(hours), len(points)))
    for k in range(1, len(steps)):
        sel = (hours > steps[k - 1]) & (hours <= steps[k])
        rain[sel] = np.maximum(tp[k] - tp[k - 1], 0.0) / (steps[k] - steps[k - 1])
    rain_h = pd.DataFrame(rain, index=idx)
    # window maxima: mx2t3 (3 h windows, steps <= 144) / mx2t6 (6 h windows after), labelled at the window end
    tmax = np.full((len(steps), len(points)), np.nan)
    for k, r in enumerate(rows):
        if "mx2t3" in r:
            tmax[k] = r["mx2t3"] - 273.15
        elif "mx2t6" in r:
            tmax[k] = r["mx2t6"] - 273.15
    tmax_w = pd.DataFrame(tmax, index=init + pd.to_timedelta(steps, unit="h"))
    return t_h, d_h, rain_h, tmax_w


def crop_state_daily(t_h, d_h, rain_h, tmax_w, points):
    """Per-state daily drivers from the forecast, same definitions as crops.daily_from_hourly (complete local days only)."""
    per_state = {}
    for st, (tz, pts) in crops.CROP_STATES.items():
        pdaily = []
        for i, (s, la, lo) in enumerate(points):
            if s != st:
                continue
            h = pd.DataFrame({"t2m": t_h[i], "d2m": d_h[i], "precip": rain_h[i]}).iloc[1:].tz_convert(tz)  # drop h=0 (no preceding-hour rain)
            vpd = crops.vpd_kpa(h["t2m"], h["d2m"])
            g = h.groupby(h.index.date)
            full = g["t2m"].count() == 24
            pm = pd.Series(np.asarray(vpd), index=h.index)
            pm = pm[(pm.index.hour >= 12) & (pm.index.hour < 18)].groupby(lambda x: x.date()).mean()
            mx = tmax_w[i].dropna().tz_convert(tz)
            tmax = mx.groupby(mx.index.date).max()
            df = pd.DataFrame({"tmax": tmax - crops.TMAX_BIAS_C, "vpd_pm": np.maximum(pm - crops.VPD_BIAS_KPA, 0.0),
                               "rain": g["precip"].sum()})[full].dropna()
            df.index = pd.to_datetime(df.index)
            pdaily.append(df)
        common = pdaily[0].index
        for p in pdaily[1:]:
            common = common.intersection(p.index)
        per_state[st] = crops.state_daily([p.loc[common] for p in pdaily])
    return per_state


def _predict_dge(cmodel, crop, feats, iso):
    m = cmodel["models"][crop]
    if not (crops.SEASON_WEEKS[0] <= iso <= crops.SEASON_WEEKS[1]):
        return np.nan, np.nan
    x = np.array([[feats[f] for f in crops.FEATURES] + [(iso - 30) / 8.0]])
    z = (x - np.array(m["mu"])) / np.array(m["sd"])
    return round(float(m["beta"][0] + (z @ np.array(m["beta"][1:]))[0]), 2), m["clim_dge_by_week"].get(str(iso), np.nan)


def crop_impact(per_state_daily, cmodel, issue_date):
    """Per state and week: forecast weather drivers vs climatology. Plus an 'ALL' row (ten-state average) carrying the
    predicted week-on-week change in good+excellent condition for corn and soybeans, in season only."""
    rows = []
    by_week = {}
    for st, daily in per_state_daily.items():
        w = crops.weekly(daily)
        for we, r in w.iterrows():
            if (we - pd.Timedelta(days=6)).date() < issue_date:
                continue
            iso = int(we.isocalendar().week)
            row = {"state": st, "week_ending": we.strftime("%Y-%m-%d"), "lead_days": int((we.date() - issue_date).days)}
            for f in crops.FEATURES:
                row[f"{f}_fc"] = round(float(r[f]), 2)
                row[f"{f}_clim"] = cmodel["climatology_drivers"][st][f].get(str(iso), np.nan)
            for crop in crops.CROPS:
                row[f"dge_{crop.lower()}_fc"] = np.nan
                row[f"dge_{crop.lower()}_clim"] = np.nan
            rows.append(row)
            by_week.setdefault(we, []).append(row)
    for we, rs in by_week.items():
        if len(rs) < len(crops.CROP_STATES):
            continue
        iso = int(we.isocalendar().week)
        row = {"state": "ALL", "week_ending": we.strftime("%Y-%m-%d"), "lead_days": rs[0]["lead_days"]}
        for f in crops.FEATURES:
            row[f"{f}_fc"] = round(float(np.mean([r[f"{f}_fc"] for r in rs])), 2)
            row[f"{f}_clim"] = round(float(np.nanmean([r[f"{f}_clim"] for r in rs])), 3)
        feats = {f: row[f"{f}_fc"] for f in crops.FEATURES}
        for crop in crops.CROPS:
            row[f"dge_{crop.lower()}_fc"], row[f"dge_{crop.lower()}_clim"] = _predict_dge(cmodel, crop, feats, iso)
        rows.append(row)
    return pd.DataFrame(rows)


def run_crops(date, cycle=0, workers=6):
    points = crops.crop_points()
    t_h, d_h, rain_h, tmax_w = fetch_crop_drivers(date, cycle, points, workers)
    per_state = crop_state_daily(t_h, d_h, rain_h, tmax_w, points)
    issue = datetime.strptime(date, "%Y%m%d").date()
    df = crop_impact(per_state, load_crop_model(), issue)
    df.insert(0, "issue_date", issue.strftime("%Y-%m-%d"))
    df.insert(1, "model", f"IFS-{cycle:02d}z")
    return df
