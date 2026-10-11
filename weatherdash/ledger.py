"""Forecast ledger: every issued forecast (kilobytes), scored against ERA5 temperature and EIA demand when due."""
import os

import numpy as np
import pandas as pd

from . import demand, eia, regions, truth

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "ledger_temp_demand.csv")
KEY = ["issue_date", "model", "region", "valid_date"]
FC_COLS = ["issue_date", "model", "region", "valid_date", "lead_days", "t_fc_c", "t_clim_c",
           "hdd_fc", "cdd_fc", "demand_fc_mwh", "demand_clim_mwh"]
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
    """Regional pop-weighted daily mean temperature (deg C) from ERA5 for the given date range (one batched request)."""
    start, end = min(dates), max(dates)
    flat = [(reg, c, v) for reg, spec in regions.REGIONS.items() for c, v in spec["cities"].items()]
    frames = truth.hourly_batch([(v[0], v[1]) for _, _, v in flat], ["temperature_2m"], start, end)
    daily = {}
    for (reg, c, v), f in zip(flat, frames):
        h = truth.to_local(f, regions.city_tz(reg, c))["temperature_2m"]
        g = h.groupby(h.index.date)
        d = g.mean()[g.count() >= 23]
        d.index = pd.to_datetime(d.index)
        daily[(reg, c)] = d
    out = {}
    for reg, spec in regions.REGIONS.items():
        cols = [daily[(reg, c)] for c in spec["cities"]]
        w = [spec["cities"][c][2] for c in spec["cities"]]
        df = pd.concat(cols, axis=1).dropna()
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


def _anchor_factors(res, col, lag=7, window=28):
    """Trailing level factor sum(observed)/sum(model) per region over `window` valid days that were already known `lag`
    days before each issue date; returns a Series aligned to res (NaN where no factor exists yet)."""
    out = pd.Series(np.nan, index=res.index)
    for reg, g in res.groupby("region"):
        d = g.assign(v=pd.to_datetime(g["valid_date"])).groupby("v")[["demand_obs_mwh", col]].sum()
        idx = pd.date_range(d.index.min(), d.index.max())
        roll = d.reindex(idx).rolling(window, min_periods=14).sum()
        ratio = (roll["demand_obs_mwh"] / roll[col])
        for i, row in g.iterrows():
            s = ratio[:pd.Timestamp(row["issue_date"]) - pd.Timedelta(days=lag)].dropna()
            out[i] = s.iloc[-1] if len(s) else np.nan
    return out


def stats(led=None):
    """Verification vs climatology, by lead day and by region (resolved rows only).

    The 30-year climatology reads low in a warm year (and a model run at the mean temperature sits below the mean of its
    runs), which would flatter any forecast. So the baseline scored here is the climatology re-anchored to the demand
    seen over the last 28 days (valid days at least a week old at issue time, the same anchoring the wind and solar
    baselines get); the unanchored figure is kept as mape_clim_raw. Forecasts are scored as issued."""
    led = load() if led is None else led
    res = led[led["status"] == "RESOLVED"].copy()
    if res.empty:
        return {"n_logged": int(len(led)), "n_resolved": 0, "by_lead": [], "by_region": []}
    for c in ("t_fc_c", "t_clim_c", "t_obs_c", "demand_fc_mwh", "demand_clim_mwh", "demand_obs_mwh",
              "demand_from_obs_t_mwh"):
        res[c] = res[c].astype(float)
    res["f_clim"] = _anchor_factors(res, "demand_clim_mwh")
    n_all = len(res)
    res = res.dropna(subset=["f_clim"])
    res["t_err_fc"] = (res["t_fc_c"] - res["t_obs_c"]).abs()
    res["t_err_clim"] = (res["t_clim_c"] - res["t_obs_c"]).abs()
    ape = lambda p, o: (p - o).abs() / o * 100
    res["ape_fc"] = ape(res["demand_fc_mwh"], res["demand_obs_mwh"])
    res["ape_clim"] = ape(res["demand_clim_mwh"] * res["f_clim"], res["demand_obs_mwh"])
    res["ape_clim_raw"] = ape(res["demand_clim_mwh"], res["demand_obs_mwh"])
    res["ape_oracle"] = ape(res["demand_from_obs_t_mwh"], res["demand_obs_mwh"])

    def block(g):
        return {"n": int(len(g)),
                "t_mae_fc": round(float(g["t_err_fc"].mean()), 3), "t_mae_clim": round(float(g["t_err_clim"].mean()), 3),
                "mape_fc": round(float(g["ape_fc"].mean()), 3), "mape_clim": round(float(g["ape_clim"].mean()), 3),
                "mape_clim_raw": round(float(g["ape_clim_raw"].mean()), 3), "mape_oracle": round(float(g["ape_oracle"].mean()), 3)}
    by_lead = [dict(lead=int(l), **block(g)) for l, g in res.groupby("lead_days")]
    by_region = [dict(region=r, **block(g)) for r, g in res.groupby("region")]
    return {"n_logged": int(len(led)), "n_resolved": int(n_all), "n_scored": int(len(res)),
            "first_issue": str(res["issue_date"].min()), "last_issue": str(res["issue_date"].max()),
            "by_lead": by_lead, "by_region": by_region, "overall": block(res)}


# ---------------------------------------------------------------------------
# Wind and solar ledger (same discipline as above, separate file)
# ---------------------------------------------------------------------------
RPATH = os.path.join(ROOT, "data", "ledger_wind_solar.csv")
RKEY = ["issue_date", "model", "region", "resource", "valid_date"]
RFC = ["issue_date", "model", "region", "resource", "valid_date", "lead_days", "gen_fc_mwh", "gen_clim_mwh"]
ROUT = ["status", "gen_obs_mwh", "gen_from_obs_weather_mwh", "source"]
RCOLS = RFC + ROUT


def rload():
    if not os.path.exists(RPATH):
        return pd.DataFrame(columns=RCOLS)
    return pd.read_csv(RPATH, dtype={"issue_date": str, "valid_date": str}).reindex(columns=RCOLS)


def rsave(df):
    df.sort_values(["issue_date", "model", "region", "resource", "valid_date"]).to_csv(RPATH, index=False)


def rappend(new, source="live"):
    led = rload()
    new = new.copy()
    new["status"], new["source"] = "PENDING", source
    for c in ROUT:
        if c not in new:
            new[c] = np.nan
    new = new.reindex(columns=RCOLS)
    have = set(map(tuple, led[RKEY].astype(str).values))
    new = new[[tuple(map(str, k)) not in have for k in new[RKEY].values]]
    if len(new):
        rsave(pd.concat([led, new], ignore_index=True) if len(led) else new)
    return len(new)


def rscore(rmodel, today=None):
    """Fill outcomes for pending wind/solar rows: EIA daily generation, plus the generation the model gives
    from ERA5 observed weather (the model's own limit)."""
    from . import renewables
    led = rload()
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.utcnow().tz_localize(None).normalize()
    due = led[(led["status"] == "PENDING") &
              (pd.to_datetime(led["valid_date"]) <= today - pd.Timedelta(days=ERA5_LAG_DAYS))]
    if due.empty:
        return 0
    dates = sorted(due["valid_date"].unique())
    start, end = dates[0], dates[-1]
    need = {(d[:4], "Jan_Jun" if int(d[5:7]) <= 6 else "Jul_Dec") for d in dates}
    gen = pd.concat([eia.daily_generation(f"EIA930_BALANCE_{y}_{h}", list(regions.SITES)) for y, h in sorted(need)])
    obs = {(r.ba, r.resource, r.date): r.gen_mwh for r in gen.itertuples()}
    # observed weather drivers at each site (ERA5 hourly) -> model-implied generation
    feats = {}
    sites = regions.site_list()
    frames = truth.hourly_batch([(x[3], x[4]) for x in sites], ["wind_speed_100m", "shortwave_radiation"], start, end,
                                extra={"wind_speed_unit": "ms"})
    for (ba, kind, site, lat, lon), f in zip(sites, frames):
        h = truth.to_local(f.rename(columns={"wind_speed_100m": "wind100", "shortwave_radiation": "ghi"}), regions.REGIONS[ba]["tz"])
        feats[(ba, kind, site)] = renewables.daily_features(h, kind)
    n = 0
    for idx, r in due.iterrows():
        vd = pd.Timestamp(r["valid_date"])
        g = obs.get((r["region"], r["resource"], vd))
        m = rmodel["models"].get(f"{r['region']}|{r['resource']}")
        if g is None or m is None or pd.isna(g):
            continue
        rows_ = [feats[(r["region"], r["resource"], s)].loc[vd] if vd in feats[(r["region"], r["resource"], s)].index else None
                 for s in m["sites"]]
        if any(x is None or x.isna().any() for x in rows_):
            continue
        oracle = float(renewables.generate(m, [vd], np.concatenate([x.values for x in rows_])[None, :])[0])
        led.loc[idx, ["gen_obs_mwh", "gen_from_obs_weather_mwh", "status"]] = [round(float(g), 0), round(oracle, 0), "RESOLVED"]
        n += 1
    if n:
        rsave(led)
    return n


def rstats(led=None):
    led = rload() if led is None else led
    res = led[led["status"] == "RESOLVED"].copy()
    out = {"n_logged": int(len(led)), "n_resolved": int(len(res)), "by_lead": [], "by_series": []}
    if res.empty:
        return out
    for c in ("gen_fc_mwh", "gen_clim_mwh", "gen_obs_mwh", "gen_from_obs_weather_mwh"):
        res[c] = res[c].astype(float)
    den = np.maximum(res["gen_obs_mwh"], 1.0)
    for k, col in (("fc", "gen_fc_mwh"), ("clim", "gen_clim_mwh"), ("oracle", "gen_from_obs_weather_mwh")):
        res[f"ape_{k}"] = (res[col] - res["gen_obs_mwh"]).abs() / den * 100

    def block(g):
        return {"n": int(len(g)), "mape_fc": round(float(g["ape_fc"].mean()), 2),
                "mape_clim": round(float(g["ape_clim"].mean()), 2), "mape_oracle": round(float(g["ape_oracle"].mean()), 2)}
    out["first_issue"], out["last_issue"] = str(res["issue_date"].min()), str(res["issue_date"].max())
    for res_kind, gk in res.groupby("resource"):
        for lead, g in gk.groupby("lead_days"):
            out["by_lead"].append(dict(resource=res_kind, lead=int(lead), **block(g)))
    for (reg, kind), g in res.groupby(["region", "resource"]):
        out["by_series"].append(dict(region=reg, resource=kind, **block(g)))
    return out


# ---------------------------------------------------------------------------
# Level calibration for wind/solar. Weather -> generation maps drift as capacity is added, and a 0.25 degree
# forecast grid can read systematically lower or higher than the reanalysis the map was fitted on (mountain-pass
# wind sites especially). Each series is therefore rescaled to the last 28 days of observed output, separately for
# the forecast, the climatology baseline and the observed-weather model, using only days already known at
# issue time (valid date at least 7 days old). Correlation with observed output is untouched; only the level moves.
# ---------------------------------------------------------------------------
CAL_WINDOW_DAYS = 28
CAL_LAG_DAYS = 7
_SRC = {"fc": "gen_fc_mwh", "clim": "gen_clim_mwh", "oracle": "gen_from_obs_weather_mwh"}


def _ratio_tables(res):
    """{(region, resource): DataFrame(index=valid date; columns fc/clim/oracle)} of trailing observed/modelled ratios."""
    out = {}
    d = res.copy()
    for c in list(_SRC.values()) + ["gen_obs_mwh"]:
        d[c] = d[c].astype(float)
    d["valid_date"] = pd.to_datetime(d["valid_date"])
    for (reg, kind), g in d.groupby(["region", "resource"]):
        daily = g.groupby("valid_date")[list(_SRC.values()) + ["gen_obs_mwh"]].sum()
        # per-valid-date sums across leads: the obs column counts once per lead row, matching the model columns
        idx = pd.date_range(daily.index.min(), daily.index.max())
        daily = daily.reindex(idx)
        roll = daily.rolling(CAL_WINDOW_DAYS, min_periods=14).sum()
        out[(reg, kind)] = pd.DataFrame({k: roll["gen_obs_mwh"] / roll[col] for k, col in _SRC.items()})
    return out


def calibrated_forecast(rdf, led=None):
    """Latest forecast rows with the level calibration applied (records for the dashboard payload)."""
    led = rload() if led is None else led
    res = led[led["status"] == "RESOLVED"]
    tabs = _ratio_tables(res) if len(res) else {}
    rows = []
    for r in rdf.to_dict(orient="records"):
        t = tabs.get((r["region"], r["resource"]))
        f_fc = f_cl = 1.0
        if t is not None and t.dropna().shape[0]:
            last = t.dropna().iloc[-1]
            f_fc, f_cl = float(last["fc"]), float(last["clim"])
        rows.append(dict(r, factor=round(f_fc, 3), gen_fc_mwh=round(r["gen_fc_mwh"] * f_fc, 0),
                         gen_clim_mwh=round(r["gen_clim_mwh"] * f_cl, 0)))
    return rows


def rstats_calibrated(led=None):
    """Verification of wind/solar forecasts after level calibration (rows with factors known at issue time only)."""
    led = rload() if led is None else led
    res = led[led["status"] == "RESOLVED"].copy()
    out = {"n_logged": int(len(led)), "n_resolved": int(len(res)), "n_scored": 0, "by_lead": [], "by_series": []}
    if res.empty:
        return out
    for c in list(_SRC.values()) + ["gen_obs_mwh"]:
        res[c] = res[c].astype(float)
    tabs = _ratio_tables(res)
    f = {k: [] for k in _SRC}
    for r in res.itertuples():
        t = tabs.get((r.region, r.resource))
        d = pd.Timestamp(r.issue_date) - pd.Timedelta(days=CAL_LAG_DAYS)
        s = t[:d].dropna() if t is not None else None
        for k in _SRC:
            f[k].append(float(s[k].iloc[-1]) if s is not None and len(s) else np.nan)
    for k in _SRC:
        res[f"f_{k}"] = f[k]
    res = res.dropna(subset=["f_fc", "f_clim", "f_oracle"])
    out["n_scored"] = int(len(res))
    if res.empty:
        return out
    # normalised mean absolute error: absolute error as a % of the series' mean daily output (robust to low-output days)
    den = res.groupby(["region", "resource"])["gen_obs_mwh"].transform("mean")
    for k, col in _SRC.items():
        res[f"ape_{k}"] = (res[col] * res[f"f_{k}"] - res["gen_obs_mwh"]).abs() / den * 100

    def block(g):
        return {"n": int(len(g)), "nmae_fc": round(float(g["ape_fc"].mean()), 2),
                "nmae_clim": round(float(g["ape_clim"].mean()), 2), "nmae_oracle": round(float(g["ape_oracle"].mean()), 2)}
    out["first_issue"], out["last_issue"] = str(res["issue_date"].min()), str(res["issue_date"].max())
    for kind, gk in res.groupby("resource"):
        for lead, g in gk.groupby("lead_days"):
            out["by_lead"].append(dict(resource=kind, lead=int(lead), **block(g)))
    for (reg, kind), g in res.groupby(["region", "resource"]):
        out["by_series"].append(dict(region=reg, resource=kind, **block(g)))
    return out


# ---------------------------------------------------------------------------
# Crop-stress ledger: weekly (Mon-Sun) state drivers and the predicted change in NASS good+excellent condition
# ---------------------------------------------------------------------------
CPATH = os.path.join(ROOT, "data", "ledger_crops.csv")
CKEY = ["issue_date", "model", "state", "week_ending"]
FEATS = ["kdd", "hot_days", "vpd", "rain"]
CFC = (["issue_date", "model", "state", "week_ending", "lead_days"] + [f"{f}_fc" for f in FEATS] + [f"{f}_clim" for f in FEATS] +
       ["dge_corn_fc", "dge_corn_clim", "dge_soybeans_fc", "dge_soybeans_clim"])
COUT = [f"{f}_obs" for f in FEATS] + ["dge_corn_obs", "dge_soybeans_obs", "status", "source"]
CCOLS = CFC + COUT
NASS_PATH = os.path.join(ROOT, "data", "nass_condition.csv")


def cload():
    if not os.path.exists(CPATH):
        return pd.DataFrame(columns=CCOLS)
    return pd.read_csv(CPATH, dtype={"issue_date": str, "week_ending": str}).reindex(columns=CCOLS)


def csave(df):
    df.sort_values(["issue_date", "model", "state", "week_ending"]).to_csv(CPATH, index=False)


def cappend(new, source="live"):
    led = cload()
    new = new.copy()
    new["status"], new["source"] = "PENDING", source
    for c in COUT:
        if c not in new:
            new[c] = np.nan
    new = new.reindex(columns=CCOLS)
    have = set(map(tuple, led[CKEY].astype(str).values))
    new = new[[tuple(map(str, k)) not in have for k in new[CKEY].values]]
    if len(new):
        csave(pd.concat([led, new], ignore_index=True) if len(led) else new)
    return len(new)


def _nass_dge():
    """{(crop, state, week_ending str): week-on-week change in good+excellent} from the NASS table on disk."""
    if not os.path.exists(NASS_PATH):
        return {}
    n = pd.read_csv(NASS_PATH)
    n["week_ending"] = pd.to_datetime(n["week_ending"])
    n["ge"] = n["good"] + n["excellent"]
    out = {}
    for (crop, st), g in n[n["commodity"].isin(["CORN", "SOYBEANS"])].groupby(["commodity", "state"]):
        s = g.sort_values("week_ending").set_index("week_ending")["ge"]
        d = s.diff()[s.index.to_series().diff().dt.days == 7]
        for we, v in d.items():
            out[(crop, st, we.strftime("%Y-%m-%d"))] = float(v)
    from . import crops
    for crop in ("CORN", "SOYBEANS"):
        by_week = {}
        for (c, st, we), v in out.items():
            if c == crop and st in crops.CROP_STATES:
                by_week.setdefault(we, []).append(v)
        for we, vs in by_week.items():
            if len(vs) >= 8:
                out[(crop, "ALL", we)] = float(np.mean(vs))
    return out


def cscore(today=None, refresh_nass=True):
    """Fill ERA5-observed weekly drivers (6 days after week end) and NASS condition changes (when published)."""
    from . import crops, nass
    led = cload()
    today = pd.Timestamp(today) if today is not None else pd.Timestamp.utcnow().tz_localize(None).normalize()
    we = pd.to_datetime(led["week_ending"])
    filled = 0
    # 1. observed weather
    need = led[led["kdd_obs"].isna() & (we <= today - pd.Timedelta(days=ERA5_LAG_DAYS))]
    if len(need):
        start = (pd.to_datetime(need["week_ending"]).min() - pd.Timedelta(days=6)).strftime("%Y-%m-%d")
        end = pd.to_datetime(need["week_ending"]).max().strftime("%Y-%m-%d")
        wk = {}
        flat = [(st, tz, la, lo) for st, (tz, pts) in crops.CROP_STATES.items() for la, lo in pts]
        frames = truth.hourly_batch([(x[2], x[3]) for x in flat], ["temperature_2m", "dew_point_2m", "precipitation"], start, end)
        by_state = {}
        for (st, tz, la, lo), f in zip(flat, frames):
            h = truth.to_local(f.rename(columns={"temperature_2m": "t2m", "dew_point_2m": "d2m", "precipitation": "precip"}), tz)
            by_state.setdefault(st, []).append(crops.daily_from_hourly(h, tz))
        for st, pdaily in by_state.items():
            common = pdaily[0].index
            for p in pdaily[1:]:
                common = common.intersection(p.index)
            wk[st] = crops.weekly(crops.state_daily([p.loc[common] for p in pdaily]))
        for idx, r in need.iterrows():
            t = pd.Timestamp(r["week_ending"])
            if r["state"] == "ALL":
                ws = [w for w in wk.values() if t in w.index]
                if len(ws) < len(wk):
                    continue
                vals = {f: float(np.mean([w.loc[t, f] for w in ws])) for f in FEATS}
            else:
                w = wk.get(r["state"])
                if w is None or t not in w.index:
                    continue
                vals = {f: float(w.loc[t, f]) for f in FEATS}
            for f in FEATS:
                led.loc[idx, f"{f}_obs"] = round(vals[f], 2)
            led.loc[idx, "status"] = "RESOLVED"
            filled += 1
    # 2. NASS condition changes (in-season rows only: the forecast column is empty otherwise)
    def due_nass():
        d = led[(led[["dge_corn_obs", "dge_soybeans_obs"]].isna().any(axis=1)) & led[["dge_corn_fc", "dge_soybeans_fc"]].notna().any(axis=1)
                & (pd.to_datetime(led["week_ending"]) <= today - pd.Timedelta(days=2))]
        return d
    pend = due_nass()
    dge = _nass_dge()
    missing = [r for r in pend.itertuples() if (("CORN", r.state, r.week_ending) not in dge) and (("SOYBEANS", r.state, r.week_ending) not in dge)]
    if refresh_nass and missing:
        nass.stream_condition().to_csv(NASS_PATH, index=False)
        dge = _nass_dge()
    for idx, r in pend.iterrows():
        for crop, col in (("CORN", "dge_corn_obs"), ("SOYBEANS", "dge_soybeans_obs")):
            v = dge.get((crop, r["state"], r["week_ending"]))
            if v is not None and pd.isna(led.loc[idx, col]):
                led.loc[idx, col] = v
                filled += 1
    if filled:
        csave(led)
    return filled


def cstats(led=None):
    led = cload() if led is None else led
    out = {"n_logged": int(len(led)), "weather": [], "condition": [], "n_weather": 0, "n_condition": 0}
    res = led[(led["status"] == "RESOLVED") & (led["state"] == "ALL")].copy()  # ten-state average
    if res.empty:
        return out
    for f in FEATS:
        for c in (f"{f}_fc", f"{f}_clim", f"{f}_obs"):
            res[c] = res[c].astype(float)
    out["n_weather"] = int(len(res))
    out["first_issue"], out["last_issue"] = str(res["issue_date"].min()), str(res["issue_date"].max())
    res["lead_bucket"] = ((res["lead_days"].astype(int) - 1) // 3) * 3 + 2  # 3-day buckets, labelled by the middle day
    for f in FEATS:
        for lead, g in res.groupby("lead_bucket"):
            if len(g) >= 10:
                out["weather"].append({"feature": f, "lead": int(lead), "n": int(len(g)),
                                       "mae_fc": round(float((g[f"{f}_fc"] - g[f"{f}_obs"]).abs().mean()), 3),
                                       "mae_clim": round(float((g[f"{f}_clim"] - g[f"{f}_obs"]).abs().mean()), 3)})
    for crop in ("corn", "soybeans"):
        c = res[res["state"] == "ALL"].dropna(subset=[f"dge_{crop}_fc", f"dge_{crop}_obs"]).copy()
        if c.empty:
            continue
        for k in ("fc", "clim", "obs"):
            c[f"dge_{crop}_{k}"] = c[f"dge_{crop}_{k}"].astype(float)
        e = lambda col: (c[col] - c[f"dge_{crop}_obs"]).abs()
        out["condition"].append({"crop": crop, "n": int(len(c)), "weeks": int(c["week_ending"].nunique()),
                                 "mae_fc": round(float(e(f"dge_{crop}_fc").mean()), 3),
                                 "mae_clim": round(float(e(f"dge_{crop}_clim").mean()), 3),
                                 "mae_zero": round(float(c[f"dge_{crop}_obs"].abs().mean()), 3),
                                 "corr": round(float(np.corrcoef(c[f"dge_{crop}_fc"], c[f"dge_{crop}_obs"])[0, 1]), 3)})
        out["n_condition"] += int(len(c))
    return out
