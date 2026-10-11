"""EIA-930 hourly grid data (free, no key): the six-month CSVs published on the Grid Monitor page."""
import io
import time

import pandas as pd
import requests

BASE = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles"
USECOLS = ["Balancing Authority", "Data Date", "Hour Number", "Demand (MW)", "Demand (MW) (Adjusted)",
           "Net Generation (MW) from Wind without Integrated Battery Storage",
           "Net Generation (MW) from Solar without Integrated Battery Storage"]


def six_month_files(years):
    return [f"EIA930_BALANCE_{y}_{h}" for y in years for h in ("Jan_Jun", "Jul_Dec")]


_CACHE = {}


def _download(name, tries=5):
    if name in _CACHE:
        return _CACHE[name]
    out = _download_uncached(name, tries)
    _CACHE.clear()  # keep only the most recent file: they are 40+ MB each
    _CACHE[name] = out
    return out


def _download_uncached(name, tries=5):
    url = f"{BASE}/{name}.csv"
    for a in range(tries):
        try:
            r = requests.get(url, timeout=180)
            if r.status_code == 200:
                return r.content
        except requests.RequestException:
            pass
        time.sleep(2 ** a)
    raise RuntimeError(f"could not download {url}")


def daily_demand(name, bas):
    """Daily total demand (MWh) per BA for one six-month file; only days with 23-25 reported hours."""
    raw = _download(name)
    df = pd.read_csv(io.BytesIO(raw), usecols=lambda c: c in USECOLS or c == "Balancing Authority", low_memory=False)
    df = df[df["Balancing Authority"].isin(bas)].copy()
    dem = df["Demand (MW) (Adjusted)"].where(df["Demand (MW) (Adjusted)"].notna(), df["Demand (MW)"])
    df["demand"] = pd.to_numeric(dem, errors="coerce")
    df["date"] = pd.to_datetime(df["Data Date"], format="%m/%d/%Y")
    g = df.groupby(["Balancing Authority", "date"])["demand"].agg(["sum", "count"]).reset_index()
    g = g[(g["count"] >= 23) & (g["count"] <= 25)]
    return g.rename(columns={"Balancing Authority": "ba", "sum": "demand_mwh"})[["ba", "date", "demand_mwh"]]


GEN_COLS = {  # column names changed over the years; first match wins
    "wind": ["Net Generation (MW) from Wind without Integrated Battery Storage (Adjusted)",
             "Net Generation (MW) from Wind (Adjusted)"],
    "solar": ["Net Generation (MW) from Solar without Integrated Battery Storage (Adjusted)",
              "Net Generation (MW) from Solar (Adjusted)"],
}


def daily_generation(name, bas):
    """Daily wind and solar generation (MWh) per BA for one six-month file (local data date, 23-25 valid hours)."""
    raw = _download(name)
    wanted = {c for cs in GEN_COLS.values() for c in cs} | {"Balancing Authority", "Data Date"}
    df = pd.read_csv(io.BytesIO(raw), usecols=lambda c: c in wanted, low_memory=False)
    df = df[df["Balancing Authority"].isin(bas)].copy()
    df["date"] = pd.to_datetime(df["Data Date"], format="%m/%d/%Y")
    out = []
    for res, cands in GEN_COLS.items():
        col = next((c for c in cands if c in df), None)
        if col is None:
            continue
        x = df[["Balancing Authority", "date"]].copy()
        x["v"] = pd.to_numeric(df[col], errors="coerce")
        g = x.groupby(["Balancing Authority", "date"])["v"].agg(["sum", "count"]).reset_index()
        g = g[(g["count"] >= 23) & (g["count"] <= 25)]
        g["resource"] = res
        out.append(g.rename(columns={"Balancing Authority": "ba", "sum": "gen_mwh"})[["ba", "resource", "date", "gen_mwh"]])
    return pd.concat(out)


GAS_COLS = ["Net Generation (MW) from Natural Gas (Adjusted)", "Net Generation (MW) from Natural Gas"]


def daily_gas(name, bas):
    """Daily gas-fired generation (MWh) per BA for one six-month file (local data date, 23-25 valid hours)."""
    raw = _download(name)
    wanted = set(GAS_COLS) | {"Balancing Authority", "Data Date"}
    df = pd.read_csv(io.BytesIO(raw), usecols=lambda c: c in wanted, low_memory=False)
    df = df[df["Balancing Authority"].isin(bas)].copy()
    df["date"] = pd.to_datetime(df["Data Date"], format="%m/%d/%Y")
    v = pd.to_numeric(df[GAS_COLS[1]], errors="coerce") if GAS_COLS[1] in df else pd.Series(float("nan"), index=df.index)
    if GAS_COLS[0] in df:
        v = pd.to_numeric(df[GAS_COLS[0]], errors="coerce").where(lambda x: x.notna(), v)
    df["v"] = v
    g = df.groupby(["Balancing Authority", "date"])["v"].agg(["sum", "count"]).reset_index()
    g = g[(g["count"] >= 23) & (g["count"] <= 25)]
    return g.rename(columns={"Balancing Authority": "ba", "sum": "gas_mwh"})[["ba", "date", "gas_mwh"]]
