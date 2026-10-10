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


def _download(name, tries=5):
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
