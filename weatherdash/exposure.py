"""Physical-exposure layer: what the forecast weather means for the gas burned in power plants, for the weekly change in regional gas storage, and for next-day power prices.

These are physical translations scored against what happened (gas-fired generation from EIA-930; the weekly EIA storage report), not trading rules. The decision experiment
lives in decisions.py and is deliberately separate."""
import json
import os

import numpy as np
import pandas as pd

from .calendar_utils import doy366

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "data", "exposure_model.json")
STORAGE_REGIONS = {"R31": "East", "R32": "Midwest", "R35": "Pacific"}
REGION_LIST = ["ERCO", "PJM", "CISO", "NYIS", "ISNE", "MISO"]
T0 = pd.Timestamp("2019-01-01")


def load_model():
    return json.load(open(MODEL_PATH))


def burn_design(dates, nl_gwh, lg):
    dates = pd.DatetimeIndex(dates)
    a = 2 * np.pi * doy366(dates) / 366
    nl = np.asarray(nl_gwh, float)
    cols = [np.ones(len(dates)), nl / 100, (nl / 100) ** 2, np.asarray(lg, float), np.sin(a), np.cos(a), np.sin(2 * a), np.cos(2 * a), (dates - T0).days.values / 365.25]
    cols += [(dates.dayofweek == k).astype(float) for k in range(6)]
    return np.column_stack(cols)


def burn_predict(model, ba, dates, nl_gwh, lg):
    m = model["burn"][ba]
    return burn_design(dates, nl_gwh, lg) @ np.array(m["beta"])


def storage_design(D):
    a = 2 * np.pi * np.asarray(D["doy"]) / 366
    cols = [np.ones(len(D)), np.sin(a), np.cos(a), np.sin(2 * a), np.cos(2 * a)]
    for r in REGION_LIST:
        cols += [D[f"H_{r}"].values / 100, D[f"C_{r}"].values / 100]
    H = sum(D[f"H_{r}"].values for r in REGION_LIST) / 600
    C = sum(D[f"C_{r}"].values for r in REGION_LIST) / 600
    cols += [H ** 2, C ** 2]
    return np.column_stack(cols)


def five_year_norm(chg):
    """Average change of the same ISO week in the previous five years (at least three); chg indexed by the week-ending Friday."""
    out = {}
    iso = {d: d.isocalendar()[1] for d in chg.index}
    for d in chg.index:
        prev = [chg[x] for x in chg.index if x.year < d.year and x.year >= d.year - 5 and iso[x] == iso[d]]
        out[d] = float(np.mean(prev)) if len(prev) >= 3 else np.nan
    return pd.Series(out)


# ============================================================================ gas burn ledger
import io  # noqa: E402
import zipfile  # noqa: E402

import requests  # noqa: E402

from . import eia  # noqa: E402

LED_BURN = os.path.join(ROOT, "data", "ledger_burn.csv")
LED_STOR = os.path.join(ROOT, "data", "ledger_storage.csv")
BURN_COLS = ["issue_date", "region", "valid_date", "lead_days", "burn_fc_gwh", "burn_clim_gwh", "status", "burn_obs_gwh", "source"]
STOR_COLS = ["issue_date", "code", "week_ending", "lead_days", "chg_fc_bcf", "norm_bcf", "status", "chg_obs_bcf", "source"]
BURN_KEY = ["issue_date", "region", "valid_date"]
STOR_KEY = ["issue_date", "code", "week_ending"]
HUB_MAP = {"PJM": "PJM West", "ISNE": "Mass Hub", "CISO": "SP15", "MISO": "Indiana Hub"}


def _load(path, cols):
    if os.path.exists(path):
        return pd.read_csv(path, dtype={"issue_date": str, "valid_date": str, "week_ending": str})
    return pd.DataFrame(columns=cols)


def _append(path, cols, key, new, source):
    old = _load(path, cols)
    new = new.copy()
    new["status"], new["source"] = "PENDING", source
    for c in cols:
        if c not in new:
            new[c] = np.nan
    both = pd.concat([old, new[cols]], ignore_index=True)
    both = both.drop_duplicates(subset=key, keep="first")  # first-issued forecast is kept
    n = len(both) - len(old)
    both.sort_values(key).to_csv(path, index=False)
    return n


def gas_log_price(price_wide, date):
    """Log of the latest front-month gas close on or before `date` (a constant when the price log is empty)."""
    if price_wide is None or "NG=F" not in price_wide or price_wide["NG=F"].dropna().empty:
        return float(np.log(3.0))
    s = price_wide["NG=F"].dropna()
    s = s[s.index <= pd.Timestamp(date)]
    return float(np.log(s.iloc[-1] if len(s) else price_wide["NG=F"].dropna().iloc[0]))


def burn_rows(dem, ren, model, price_wide):
    """Forecast gas-fired generation (GWh/day) per region and valid day from the demand and wind/solar forecast rows of one or more issue dates."""
    rows = []
    for issue, g in dem.groupby("issue_date"):
        lg = gas_log_price(price_wide, issue)
        r_i = ren[ren.issue_date == issue]
        for ba in REGION_LIST:
            d = g[g.region == ba].sort_values("lead_days")
            if d.empty or ba not in model["burn"]:
                continue
            def res(kind):
                x = r_i[(r_i.region == ba) & (r_i.resource == kind)].set_index("lead_days")
                return x.gen_fc_mwh.reindex(d.lead_days).fillna(0.0).values.astype(float)
            nl = (d.demand_fc_mwh.values.astype(float) - res("wind") - res("solar")) / 1000.0
            dates = pd.to_datetime(d.valid_date)
            fc = np.clip(burn_predict(model, ba, dates, nl, np.full(len(d), lg)), 0, None)
            clim = np.array(model["burn"][ba]["clim_gwh_by_doy"])[doy366(dates) - 1]
            for i, (_, r) in enumerate(d.iterrows()):
                rows.append({"issue_date": issue, "region": ba, "valid_date": r.valid_date, "lead_days": int(r.lead_days),
                             "burn_fc_gwh": round(float(fc[i]), 1), "burn_clim_gwh": round(float(clim[i]), 1)})
    return pd.DataFrame(rows)


def burn_load():
    return _load(LED_BURN, BURN_COLS)


def burn_append(df, source="live"):
    return _append(LED_BURN, BURN_COLS, BURN_KEY, df, source)


def burn_score(today=None):
    led = burn_load()
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today)
    pend = led[(led.status == "PENDING") & (pd.to_datetime(led.valid_date) <= today - pd.Timedelta(days=4))]
    if pend.empty:
        return 0
    need = sorted({(d[:4], "Jan_Jun" if int(d[5:7]) <= 6 else "Jul_Dec") for d in pend.valid_date})
    parts = []
    for y, h in need:
        try:
            parts.append(eia.daily_gas(f"EIA930_BALANCE_{y}_{h}", REGION_LIST))
        except RuntimeError:
            continue
    if not parts:
        return 0
    obs = pd.concat(parts)
    obs["valid_date"] = obs["date"].dt.strftime("%Y-%m-%d")
    obs = obs.set_index(["ba", "valid_date"])["gas_mwh"] / 1000.0
    n = 0
    for i, r in pend.iterrows():
        k = (r.region, r.valid_date)
        if k in obs.index:
            led.loc[i, "burn_obs_gwh"] = round(float(obs[k]), 1)
            led.loc[i, "status"] = "RESOLVED"
            n += 1
    if n:
        led.to_csv(LED_BURN, index=False)
    return n


UNMODELLED = ["CISO"]  # the gas fleet there has been restructured by solar and batteries; the 2019-2025 fit does not describe 2026 (see verification)


def _anchor_factors(res, col, lag=7, window=28):
    """Trailing level factor sum(observed)/sum(model) per region over `window` valid days that were known `lag` days before each issue date (NaN until one exists)."""
    out = pd.Series(np.nan, index=res.index)
    for reg, g in res.groupby("region"):
        d = g.assign(v=pd.to_datetime(g["valid_date"])).groupby("v")[["burn_obs_gwh", col]].mean()
        idx = pd.date_range(d.index.min(), d.index.max())
        roll = d.reindex(idx).rolling(window, min_periods=14).sum()
        ratio = roll["burn_obs_gwh"] / roll[col]
        for i, row in g.iterrows():
            sr = ratio[:pd.Timestamp(row["issue_date"]) - pd.Timedelta(days=lag)].dropna()
            out[i] = sr.iloc[-1] if len(sr) else np.nan
    return out


def latest_factors(led=None):
    """Level factors to apply to today's forecast and climatology (trailing 28 resolved days), per region."""
    led = burn_load() if led is None else led
    res = led[led.status == "RESOLVED"].copy()
    out = {}
    for reg, g in res.groupby("region"):
        g = g.assign(v=pd.to_datetime(g["valid_date"]), o=g.burn_obs_gwh.astype(float), f=g.burn_fc_gwh.astype(float), c=g.burn_clim_gwh.astype(float))
        d = g.groupby("v")[["o", "f", "c"]].mean().sort_index().iloc[-28:]
        if len(d) >= 14:
            out[reg] = {"fc": round(float(d.o.sum() / d.f.sum()), 3), "clim": round(float(d.o.sum() / d.c.sum()), 3)}
    return out


def burn_stats(led=None):
    led = burn_load() if led is None else led
    res = led[led.status == "RESOLVED"].copy()
    out = {"n_logged": int(len(led)), "n_resolved": int(len(res)), "by_lead": [], "by_region": [], "total_by_lead": [], "unmodelled": UNMODELLED}
    if res.empty:
        return out
    for c in ("burn_fc_gwh", "burn_clim_gwh", "burn_obs_gwh"):
        res[c] = res[c].astype(float)
    res["lead_days"] = res.lead_days.astype(int)
    res["f_fc"], res["f_cl"] = _anchor_factors(res, "burn_fc_gwh"), _anchor_factors(res, "burn_clim_gwh")
    out["n_scored"] = int(res[["f_fc", "f_cl"]].dropna().shape[0])
    res = res.dropna(subset=["f_fc", "f_cl"])
    # the forecast and the climatology are both re-anchored to the recent observed level, so the comparison is about timing and weather, not level
    res["ape_fc"] = (res.burn_fc_gwh * res.f_fc - res.burn_obs_gwh).abs() / res.burn_obs_gwh * 100
    res["ape_clim"] = (res.burn_clim_gwh * res.f_cl - res.burn_obs_gwh).abs() / res.burn_obs_gwh * 100
    res["ape_fc_raw"] = (res.burn_fc_gwh - res.burn_obs_gwh).abs() / res.burn_obs_gwh * 100
    res["ape_clim_raw"] = (res.burn_clim_gwh - res.burn_obs_gwh).abs() / res.burn_obs_gwh * 100
    out["first_issue"], out["last_issue"] = str(res.issue_date.min()), str(res.issue_date.max())
    blk = lambda g: {"n": int(len(g)), "mape_fc": round(float(g.ape_fc.mean()), 2), "mape_clim": round(float(g.ape_clim.mean()), 2),
                     "mape_fc_raw": round(float(g.ape_fc_raw.mean()), 2), "mape_clim_raw": round(float(g.ape_clim_raw.mean()), 2)}
    m = res[~res.region.isin(UNMODELLED)]
    out["by_lead"] = [dict(lead=int(l), **blk(g)) for l, g in m.groupby("lead_days")]
    out["by_region"] = [dict(region=r, modelled=r not in UNMODELLED, **blk(g)) for r, g in res.groupby("region")]
    out["overall"] = blk(m)
    full = m.groupby(["issue_date", "valid_date", "lead_days"]).filter(lambda g: len(g) == len(REGION_LIST) - len(UNMODELLED))
    if len(full):
        t = full.assign(fa=full.burn_fc_gwh * full.f_fc, ca=full.burn_clim_gwh * full.f_cl).groupby(["issue_date", "valid_date", "lead_days"])[["fa", "ca", "burn_obs_gwh"]].sum().reset_index()
        t["ape_fc"] = (t.fa - t.burn_obs_gwh).abs() / t.burn_obs_gwh * 100
        t["ape_clim"] = (t.ca - t.burn_obs_gwh).abs() / t.burn_obs_gwh * 100
        tb = lambda g: {"n": int(len(g)), "mape_fc": round(float(g.ape_fc.mean()), 2), "mape_clim": round(float(g.ape_clim.mean()), 2)}
        out["total_by_lead"] = [dict(lead=int(l), **tb(g)) for l, g in t.groupby("lead_days")]
        out["total_overall"] = tb(t)
    return out


# ============================================================================ storage
def storage_series():
    """Regional weekly working gas (Bcf) from EIA's bulk natural gas file (4 MB, no key)."""
    r = requests.get("https://www.eia.gov/opendata/bulk/NG.zip", timeout=180)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    got = {}
    with z.open("NG.txt") as fh:
        for line in fh:
            d = json.loads(line)
            sid = d.get("series_id", "")
            if sid.startswith("NG.NW2_EPG0_SWO_R") and sid.endswith("_BCF.W"):
                got[sid.split("_")[3]] = pd.Series({pd.Timestamp(a): float(b) for a, b in d["data"]}).sort_index()
    return got


def norm_for(F, chg):
    """Five-year norm for the week ending F from a series of weekly changes (indexed by Friday)."""
    wk = F.isocalendar()[1]
    prev = [chg[x] for x in chg.index if x.year < F.year and x.year >= F.year - 5 and x.isocalendar()[1] == wk]
    return float(np.mean(prev)) if len(prev) >= 3 else np.nan


def storage_rows(dem, model, chg_by_code, max_weeks=3, only=None):
    """Forecast weekly storage change for the next report weeks from each issue date's regional temperatures (past days of the week from the lead-0 forecasts of their own issue dates)."""
    dem = dem.copy()
    dem["valid_date"] = pd.to_datetime(dem["valid_date"])
    dem["issue_ts"] = pd.to_datetime(dem["issue_date"])
    lead0 = {(r.region, r.valid_date): float(r.t_fc_c) for r in dem[dem.lead_days.astype(int) == 0].itertuples()}
    rows = []
    for issue, g in dem.groupby("issue_ts"):
        if only is not None and issue.strftime("%Y-%m-%d") not in only:
            continue
        fc = {(r.region, r.valid_date): float(r.t_fc_c) for r in g.itertuples()}
        f0 = issue + pd.Timedelta(days=(4 - issue.dayofweek) % 7)  # first Friday on or after issue
        targets = [f0 - pd.Timedelta(days=7) + pd.Timedelta(days=7 * k) for k in range(max_weeks + 1)]
        targets = [F for F in targets if F + pd.Timedelta(days=6) > issue]  # report not yet published
        for F in targets[:max_weeks]:
            days = [F - pd.Timedelta(days=k) for k in range(6, -1, -1)]
            D = {"doy": int(doy366([F])[0])}
            ok = True
            for r in REGION_LIST:
                hs = cs = 0.0
                for d in days:
                    t = fc.get((r, d)) if d >= issue else lead0.get((r, d))
                    if t is None:
                        ok = False
                        break
                    f = t * 9 / 5 + 32
                    hs += max(65 - f, 0)
                    cs += max(f - 65, 0)
                if not ok:
                    break
                D[f"H_{r}"], D[f"C_{r}"] = hs, cs
            if not ok:
                continue
            X = storage_design(pd.DataFrame([D]))
            for code in STORAGE_REGIONS:
                b = np.array(model["storage"][code]["beta"])
                chg = chg_by_code[code].diff().dropna() if chg_by_code else None
                rows.append({"issue_date": issue.strftime("%Y-%m-%d"), "code": code, "week_ending": F.strftime("%Y-%m-%d"), "lead_days": int((F - issue).days),
                             "chg_fc_bcf": round(float(X[0] @ b), 1), "norm_bcf": round(norm_for(F, chg), 1) if chg is not None else np.nan})
    return pd.DataFrame(rows)


def storage_load():
    return _load(LED_STOR, STOR_COLS)


def storage_append(df, source="live"):
    return _append(LED_STOR, STOR_COLS, STOR_KEY, df, source)


def storage_score(chg_by_code):
    led = storage_load()
    n = 0
    for i, r in led[led.status == "PENDING"].iterrows():
        s = chg_by_code.get(r.code)
        F = pd.Timestamp(r.week_ending)
        if s is not None and F in s.index and (F - pd.Timedelta(days=7)) in s.index:
            led.loc[i, "chg_obs_bcf"] = round(float(s[F] - s[F - pd.Timedelta(days=7)]), 1)
            led.loc[i, "status"] = "RESOLVED"
            n += 1
    if n:
        led.to_csv(LED_STOR, index=False)
    return n


def storage_stats(led=None):
    led = storage_load() if led is None else led
    res = led[led.status == "RESOLVED"].copy()
    out = {"n_logged": int(len(led)), "n_resolved": int(len(res)), "by_region": [], "by_lead": []}
    if res.empty:
        return out
    for c in ("chg_fc_bcf", "norm_bcf", "chg_obs_bcf"):
        res[c] = res[c].astype(float)
    res["lead_days"] = res.lead_days.astype(int)
    res["e_fc"] = (res.chg_fc_bcf - res.chg_obs_bcf).abs()
    res["e_norm"] = (res.norm_bcf - res.chg_obs_bcf).abs()
    res["lb"] = pd.cut(res.lead_days, [-10, 0, 3, 7, 14], labels=["0", "1-3", "4-7", "8-14"])
    blk = lambda g: {"n": int(len(g)), "weeks": int(g.week_ending.nunique()), "mae_fc": round(float(g.e_fc.mean()), 2), "mae_norm": round(float(g.e_norm.mean()), 2)}
    out["by_region"] = [dict(region=STORAGE_REGIONS[c], **blk(g)) for c, g in res.groupby("code")]
    out["by_lead"] = [dict(lead=str(l), **blk(g)) for l, g in res.groupby("lb", observed=True)]
    out["first_issue"], out["last_issue"] = str(res.issue_date.min()), str(res.issue_date.max())
    return out


# ============================================================================ power-price premium (an estimate; not scored)
def price_premium(dem_latest, model):
    """Weather-driven premium of the next-day peak power price over its climatological level, from the degree-day anomaly of the forecast and the hub sensitivities."""
    rows = []
    pp = model.get("power_price", {})
    for reg, hub in HUB_MAP.items():
        if hub not in pp:
            continue
        s = pp[hub]
        d = dem_latest[dem_latest.region == reg]
        for r in d.itertuples():
            fc_h, fc_c = float(r.hdd_fc), float(r.cdd_fc)
            tc = float(r.t_clim_c) * 9 / 5 + 32
            cl_h, cl_c = max(65 - tc, 0), max(tc - 65, 0)
            pct = (fc_c - cl_c) * s["pct_per_10cdd"] / 10 + (fc_h - cl_h) * s["pct_per_10hdd"] / 10
            rows.append({"region": reg, "hub": hub, "valid_date": r.valid_date, "lead_days": int(r.lead_days), "premium_pct": round(pct, 1),
                         "premium_usd_mwh": round(pct / 100 * s["mean_price"], 1)})
    return pd.DataFrame(rows)


# ============================================================================ daily orchestration and payload
def append_issue(date_iso, price_wide, source="live"):
    """Append the gas-burn and storage forecasts derived from the ledgers for one issue date (idempotent: first-issued rows are kept)."""
    from . import ledger
    model = load_model()
    dem, ren = ledger.load(), ledger.rload()
    dem["issue_date"], ren["issue_date"] = dem["issue_date"].astype(str), ren["issue_date"].astype(str)
    d1, r1 = dem[dem.issue_date == date_iso], ren[ren.issue_date == date_iso]
    out = {"burn": 0, "storage": 0}
    if len(d1):
        b = burn_rows(d1, r1, model, price_wide)
        out["burn"] = burn_append(b, source) if len(b) else 0
    chg = None
    try:
        chg = storage_series()
    except Exception as e:  # noqa: BLE001
        print(f"storage series unavailable: {type(e).__name__}: {str(e)[:100]}")
    if chg is not None and len(d1):
        rows = storage_rows(dem, model, chg, only=[date_iso])
        out["storage"] = storage_append(rows, source) if len(rows) else 0
    return out, chg


def payload(date_iso, chg, price_wide):
    from . import ledger
    model = load_model()
    out = {}
    # gas burn
    led = burn_load()
    fac = latest_factors(led)
    lat = led[(led.issue_date == date_iso) & (~led.region.isin(UNMODELLED))].copy()
    rows = []
    for r in lat.itertuples():
        f = fac.get(r.region, {"fc": 1.0, "clim": 1.0})
        rows.append({"region": r.region, "valid_date": r.valid_date, "lead_days": int(r.lead_days), "burn_fc_gwh": round(float(r.burn_fc_gwh) * f["fc"], 1),
                     "burn_clim_gwh": round(float(r.burn_clim_gwh) * f["clim"], 1)})
    out["burn"] = {"issue_date": date_iso, "rows": rows, "verification": burn_stats(led), "factors": fac,
                   "model": {k: {x: v[x] for x in ("test_mape_model_obs_netload", "test_mape_climatology", "mean_gwh")} for k, v in model["burn"].items()}}
    # storage
    sl = storage_load()
    latest = sl[sl.issue_date == date_iso].sort_values(["week_ending", "code"])
    srows = [{"label": STORAGE_REGIONS[r.code], "code": r.code, "week_ending": r.week_ending, "lead_days": int(r.lead_days), "chg_fc_bcf": float(r.chg_fc_bcf),
              "norm_bcf": None if pd.isna(r.norm_bcf) else float(r.norm_bcf)} for r in latest.itertuples() if not pd.isna(r.norm_bcf)]
    out["storage"] = {"rows": srows, "verification": storage_stats(sl), "model": {k: {x: v[x] for x in ("label", "test_rmse_model", "test_rmse_norm")} for k, v in model["storage"].items()}}
    # price premium
    dem = ledger.load()
    dem["issue_date"] = dem["issue_date"].astype(str)
    dl = dem[dem.issue_date == date_iso].copy()
    for c in ("hdd_fc", "cdd_fc", "t_clim_c"):
        dl[c] = dl[c].astype(float)
    pr = price_premium(dl, model)
    out["price"] = {"rows": pr.to_dict(orient="records"), "model": model.get("power_price", {})}
    return out
