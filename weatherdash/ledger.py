"""Forecast ledger: every issued forecast (kilobytes), scored against ERA5 temperature and EIA demand when due."""
import os

import numpy as np
import pandas as pd

from . import demand, eia, regions, truth

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "ledger_temp_demand.csv")
KEY = ["issue_date", "model", "region", "valid_date"]
FC_COLS = ["issue_date", "model", "region", "valid_date", "lead_days", "t_fc_c", "t_normal_c",
           "hdd_fc", "cdd_fc", "demand_fc_mwh", "demand_normal_mwh"]
OUT_COLS = ["status", "t_obs_c", "demand_obs_mwh", "demand_from_obs_t_mwh", "source"]
COLS = FC_COLS + OUT_COLS
ERA5_LAG_DAYS = 6  # ERA5 reaches the archive API about 5 days behind


def load():
    if not os.path.exists(PATH):
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(PATH, dtype={"issue_date": str, "valid_date": str}).reindex(columns=COLS)


def save(df):
    df.sort_values(["issue_date", "model", "region", "valid_date"]).to_csv(PATH, index=False)


def append(new, source="live"):
    """Add forecast rows whose key is not in the ledger yet (first-issued version is kept)."""
    led = load()
    new = new.copy()
    new["status"], new["source"] = "PENDING", source
    for c in OUT_COLS:
        if c not in new:
            new[c] = np.nan
    new = new.reindex(columns=COLS)
    have = set(map(tuple, led[KEY].astype(str).values))
    keep = [tuple(map(str, k)) not in have for k in new[KEY].values]
    new = new[keep]
    if len(new):
        led = pd.concat([led, new], ignore_index=True) if len(led) else new
        save(led)
    return len(new)


def _obs_temps(dates, today):
    """Regional pop-weighted daily mean temperature (deg C) from ERA5 for the given date range."""
    start, end = min(dates), max(dates)
    out = {}
    for reg, spec in regions.REGIONS.items():
        ser, w = [], []
        for c, (lat, lon, wt) in spec["cities"].items():
            ser.append(truth.city_daily_history(lat, lon, regions.city_tz(reg, c), start, end))
            w.append(wt)
        df = pd.concat(ser, axis=1).dropna()
        out[reg] = pd.Series((df.values * (np.array(w) / sum(w))).sum(axis=1), index=df.index)
    return out


def _obs_demand(dates):
    years = sorted({int(d[:4]) for d in dates})
    names = [n for y in years for n in eia.six_month_files([y])
             if not (y == min(years) and False)]
    # only the half-years actually covered by the pending dates
    need = {(d[:4], "Jan_Jun" if int(d[5:7]) <= 6 else "Jul_Dec") for d in dates}
    names = [f"EIA930_BALANCE_{y}_{h}" for y, h in sorted(need)]
    parts = [eia.daily_demand(n, list(regions.REGIONS)) for n in names]
    d = pd.concat(parts)
    return {ba: g.set_index("date")["demand_mwh"] for ba, g in d.groupby("ba")}


def score(model, today=None):
    """Fill outcomes for pending rows whose valid_date has ERA5 temperature and EIA demand."""
    led = load()
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.utcnow().tz_localize(None).normalize()
    due = led[(led["status"] == "PENDING") &
              (pd.to_datetime(led["valid_date"]) <= today - pd.Timedelta(days=ERA5_LAG_DAYS))]
    if due.empty:
        return 0
    dates = sorted(due["valid_date"].unique())
    obs_t = _obs_temps(dates, today)
    obs_d = _obs_demand(dates)
    n = 0
    for idx, r in due.iterrows():
        vd = pd.Timestamp(r["valid_date"])
        t = obs_t.get(r["region"], pd.Series(dtype=float)).get(vd)
        d = obs_d.get(r["region"], pd.Series(dtype=float)).get(vd)
        if t is None or d is None or pd.isna(t) or pd.isna(d):
            continue
        beta = model["regions"][r["region"]]["beta"]
        led.loc[idx, ["t_obs_c", "demand_obs_mwh", "status"]] = [round(float(t), 2), round(float(d), 0), "RESOLVED"]
        led.loc[idx, "demand_from_obs_t_mwh"] = round(float(demand.predict(beta, [vd], [t])[0]), 0)
        n += 1
    if n:
        save(led)
    return n


def stats(led=None):
    """Verification vs climatology, by lead day and by region (resolved rows only)."""
    led = load() if led is None else led
    res = led[led["status"] == "RESOLVED"].copy()
    if res.empty:
        return {"n_logged": int(len(led)), "n_resolved": 0, "by_lead": [], "by_region": []}
    for c in ("t_fc_c", "t_normal_c", "t_obs_c", "demand_fc_mwh", "demand_normal_mwh", "demand_obs_mwh",
              "demand_from_obs_t_mwh"):
        res[c] = res[c].astype(float)
    res["t_err_fc"] = (res["t_fc_c"] - res["t_obs_c"]).abs()
    res["t_err_clim"] = (res["t_normal_c"] - res["t_obs_c"]).abs()
    for k, col in (("fc", "demand_fc_mwh"), ("clim", "demand_normal_mwh"), ("oracle", "demand_from_obs_t_mwh")):
        res[f"ape_{k}"] = (res[col] - res["demand_obs_mwh"]).abs() / res["demand_obs_mwh"] * 100

    def block(g):
        return {"n": int(len(g)),
                "t_mae_fc": round(float(g["t_err_fc"].mean()), 3), "t_mae_clim": round(float(g["t_err_clim"].mean()), 3),
                "mape_fc": round(float(g["ape_fc"].mean()), 3), "mape_clim": round(float(g["ape_clim"].mean()), 3),
                "mape_oracle": round(float(g["ape_oracle"].mean()), 3)}
    by_lead = [dict(lead=int(l), **block(g)) for l, g in res.groupby("lead_days")]
    by_region = [dict(region=r, **block(g)) for r, g in res.groupby("region")]
    return {"n_logged": int(len(led)), "n_resolved": int(len(res)),
            "first_issue": str(res["issue_date"].min()), "last_issue": str(res["issue_date"].max()),
            "by_lead": by_lead, "by_region": by_region, "overall": block(res)}
