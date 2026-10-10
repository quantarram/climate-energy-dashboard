"""
Crop stress: heat, dryness and rainfall over the US corn/soybean states, and their link to NASS weekly crop condition.

Each state is represented by three points in its main production areas (equal weights; approximate county-seat
coordinates). Daily drivers per point -- Tmax, heat-stress degree days above 30 C, afternoon vapour-pressure
deficit (12-18 local) and rainfall -- are averaged over the state's points and summed over NASS weeks (Monday to
Sunday, week ending Sunday).
"""
import numpy as np
import pandas as pd

# state: (tz, [(lat, lon), ...])
CROP_STATES = {
    "IA": ("America/Chicago", [(42.0, -93.6), (42.9, -95.5), (41.0, -92.4)]),
    "IL": ("America/Chicago", [(40.5, -89.0), (40.1, -88.2), (39.1, -88.5)]),
    "NE": ("America/Chicago", [(40.9, -98.3), (40.8, -96.7), (42.0, -97.4)]),
    "MN": ("America/Chicago", [(44.2, -94.0), (45.1, -95.0), (43.7, -93.0)]),
    "IN": ("America/New_York", [(40.4, -86.9), (41.1, -85.1), (39.2, -86.5)]),
    "SD": ("America/Chicago", [(44.3, -96.8), (43.7, -98.0), (45.0, -98.5)]),
    "OH": ("America/New_York", [(41.0, -83.65), (40.1, -84.6), (40.7, -82.5)]),
    "KS": ("America/Chicago", [(38.8, -97.6), (37.75, -100.0), (39.2, -96.6)]),
    "ND": ("America/Chicago", [(46.9, -96.8), (46.9, -98.7), (48.2, -100.5)]),
    "MO": ("America/Chicago", [(38.95, -92.3), (39.8, -94.4), (36.9, -89.6)]),
}
CROPS = ["CORN", "SOYBEANS"]
KDD_BASE_C = 30.0
HOT_DAY_C = 35.0
# The forecast's 3-hour window maximum runs about 0.5 C above ERA5's hourly maximum, and its afternoon VPD about 0.1 kPa
# above ERA5's (measured on lead 0-2 days of four archived cycles at twelve of the points); removed so that forecast drivers
# sit on the same scale as the ERA5 history the condition model was fitted on.
TMAX_BIAS_C = 0.5
VPD_BIAS_KPA = 0.1
SEASON_WEEKS = (22, 38)  # ISO week range over which condition changes are modelled and scored (about June to mid-September)


def crop_points():
    """[(state, lat, lon)] in a stable order."""
    return [(s, la, lo) for s, (tz, pts) in CROP_STATES.items() for la, lo in pts]


def es_kpa(t_c):
    t_c = np.asarray(t_c, float)
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def vpd_kpa(t_c, td_c):
    return np.maximum(es_kpa(t_c) - es_kpa(td_c), 0.0)


def daily_from_hourly(h, tz):
    """h: DataFrame indexed by local hourly time with t2m, d2m (deg C) and precip (mm). Returns daily tmax, vpd_pm, rain."""
    d = pd.DataFrame({"t2m": h["t2m"], "vpd": vpd_kpa(h["t2m"], h["d2m"]), "precip": h["precip"]}, index=h.index)
    g = d.groupby(d.index.date)
    full = g["t2m"].count() >= 23
    tmax = g["t2m"].max()
    pm = d[(d.index.hour >= 12) & (d.index.hour < 18)].groupby(lambda x: x.date())["vpd"].mean()
    rain = g["precip"].sum()
    out = pd.DataFrame({"tmax": tmax, "vpd_pm": pm, "rain": rain})[full]
    out.index = pd.to_datetime(out.index)
    return out


def state_daily(point_daily):
    """Average a list of per-point daily frames and add heat-stress degree days."""
    df = pd.concat(point_daily, axis=1, keys=range(len(point_daily)))
    m = pd.concat({c: df.xs(c, axis=1, level=1).mean(axis=1) for c in ("tmax", "vpd_pm", "rain")}, axis=1).dropna()
    # degree days are nonlinear in Tmax: compute per point, then average
    kdd = pd.concat([np.maximum(p["tmax"] - KDD_BASE_C, 0.0) for p in point_daily], axis=1).mean(axis=1)
    hot = pd.concat([(p["tmax"] > HOT_DAY_C).astype(float) for p in point_daily], axis=1).mean(axis=1)
    m["kdd"], m["hot"] = kdd.reindex(m.index), hot.reindex(m.index)
    return m


def weekly(daily):
    """Sum/mean daily state drivers over NASS weeks (Mon-Sun, labelled by the Sunday); complete weeks only."""
    d = daily.copy()
    d["week_ending"] = d.index + pd.to_timedelta(6 - d.index.dayofweek, unit="D")
    g = d.groupby("week_ending")
    w = pd.DataFrame({"kdd": g["kdd"].sum(), "hot_days": g["hot"].sum(), "vpd": g["vpd_pm"].mean(),
                      "rain": g["rain"].sum(), "n": g["kdd"].count()})
    return w[w["n"] == 7].drop(columns="n")


FEATURES = ["kdd", "hot_days", "vpd", "rain"]
