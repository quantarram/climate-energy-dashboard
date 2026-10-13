#!/usr/bin/env python3
"""
CPE climate signal ledger (moved here from the finance repo on 2026-10-11; logic, thresholds and the frozen table are unchanged).

The 43 climate rows in data/cpe_climate/cpe_climate_table.parquet are the survivors of an engine-faithful pairwise CPE run on climate predictors (ONI, Nino 3.4, SOI, AO, NAO, PDO as slow
state series): rows that cleared the engine's gates and the economic prior, rested on at least four separated formation episodes (through 2012), and held up in a chronological
test (>= 3 test episodes with a hit rate of at least two thirds and a test CPE at least ten points above the test base rate). The survivor filter used data through
2026-10-10, so nothing before the freeze date is out-of-sample for this table; this ledger records and scores only what happens after it.

What is stored (data/cpe_climate/cpe_climate_events.csv): one row per (entry_date, X, tau_past, q_X, direction): the first day on which the climate state crossed its frozen threshold after
a day on which it had not (plus, for conditions already in the tail on the freeze date, an 'ongoing' entry dated at the freeze). Thresholds for X and Y are frozen in the table
(from formation data through 2012-12-31). Each event fans out to every table row of that condition; scoring uses the engine's definitions: Y's forward tau_future log move beyond
the frozen Y threshold (above for bullish, below for bearish), horizons in the target's own trading days (its bars on the seven-day price calendar), an outcome counts once its closing bar is dated before today (UTC).

Climate indices are refetched from NOAA each run (cached copies in data/cpe_climate/indices/ if the fetch fails); the monthly values are lagged for publication (ONI ~10 days into month m+2,
every other index the 15th of month m+1). Y closes live in data/cpe_climate/prices.parquet (the finance repo's panel calendar up to the freeze, extended daily from Yahoo's chart endpoint).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "data", "cpe_climate")
TABLE_PATH = os.path.join(HERE, "cpe_climate_table.parquet")
EVENTS_PATH = os.path.join(HERE, "cpe_climate_events.csv")
DATA_DIR = os.path.join(HERE, "indices")
PRICES_PATH = os.path.join(HERE, "prices.parquet")
TABLE_END = pd.Timestamp("2026-10-10")
# Each frozen table is a "book" with its own events log and price store. Batch 1 (ONI, Nino 3.4, SOI, AO, NAO, PDO) was frozen 2026-10-10; batch 3 (more slow climate states) 2026-10-11.
# Both survivor filters ran on data through 2026-10-10, so both books score only what happens after that date.
BOOKS = {
    "b1": {"label": "Batch 1: ENSO, Arctic and Atlantic oscillations", "table": "cpe_climate_table.parquet", "events": "cpe_climate_events.csv", "prices": "prices.parquet", "frozen": "2026-10-10", "decisions": True},
    "b3": {"label": "Batch 3: Nino regions, MEI, tropical Atlantic, PNA, Southern Annular Mode", "table": "cpe_climate_table_b3.parquet", "events": "cpe_climate_events_b3.csv",
           "prices": "prices_b3.parquet", "frozen": "2026-10-11", "decisions": True},
    "b4": {"label": "Batch 4: regional drought, Pacific modes, global temperature, snow cover", "table": "cpe_climate_table_b4.parquet", "events": "cpe_climate_events_b4.csv",
           "prices": "prices_b4.parquet", "frozen": "2026-10-11", "decisions": True},
    "b5": {"label": "Batch 5: watch tier, distinct non-ENSO conditions", "table": "cpe_climate_table_b5.parquet", "events": "cpe_climate_events_b5.csv",
           "prices": "prices_b5.parquet", "frozen": "2026-10-12", "decisions": False,
           "note": "Watch tier: weaker evidence (three formation and two test episodes are enough). One row per predictor family, target and direction, ENSO family excluded (already frozen in 224 rows). "
                   "Scored as a condition and outcome ledger only; it is not part of the registered decision rule."},
}
# Tables frozen later (the weekly watch-tier freezes) are listed in data/cpe_climate/books.json, so adding one needs no code change.
if os.path.exists(os.path.join(HERE, "books.json")):
    for _b in json.load(open(os.path.join(HERE, "books.json"))):
        BOOKS[_b["id"]] = {"label": _b["label"], "table": _b["table"], "events": _b["events"], "prices": _b["prices"], "frozen": _b["frozen"],
                           "decisions": _b.get("decisions", False), "note": _b.get("note", "")}
BOOK = "b1"


def use(book):
    """Point the module-level paths at one book."""
    global TABLE_PATH, EVENTS_PATH, PRICES_PATH, BOOK
    b = BOOKS[book]
    TABLE_PATH, EVENTS_PATH, PRICES_PATH, BOOK = os.path.join(HERE, b["table"]), os.path.join(HERE, b["events"]), os.path.join(HERE, b["prices"]), book
COND = ["X", "tau_past", "q_X", "direction"]
EVENT_COLS = ["entry_date", "X", "tau_past", "q_X", "direction", "kind", "x_move", "x_threshold", "table_sha"]
URLS = {
    "oni.txt": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "sstoi.txt": "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
    "ao.txt": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/monthly.ao.index.b50.current.ascii",
    "nao.txt": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii.table",
    "pdo.txt": "https://psl.noaa.gov/data/correlation/pdo.data",
    "soi.txt": "https://www.cpc.ncep.noaa.gov/data/indices/soi",
    "meiv2.txt": "https://psl.noaa.gov/data/correlation/meiv2.data",
    "aao.txt": "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/aao/monthly.aao.index.b79.current.ascii",
    "tna.txt": "https://psl.noaa.gov/data/correlation/tna.data",
    "tsa.txt": "https://psl.noaa.gov/data/correlation/tsa.data",
    "whwp.txt": "https://psl.noaa.gov/data/correlation/whwp.data",
    "pna.txt": "https://psl.noaa.gov/data/correlation/pna.data",
    "tni.txt": "https://psl.noaa.gov/data/correlation/tni.data",
    "npgo.txt": "https://psl.noaa.gov/data/correlation/npgo.data",
    "gistemp.csv": "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
    "snow.txt": "https://climate.rutgers.edu/snowcover/files/moncov.nhland.txt",
}
NCEI_DIR = "https://www.ncei.noaa.gov/pub/data/cirs/climdiv/"
# drought regions (state-mean Palmer Drought Severity Index, NCEI nClimDiv): NCEI state code -> abbreviation
PDSI_REGIONS = {"CBPDSI": ["IL", "IN", "IA", "KS", "MN", "MO", "NE", "ND", "OH", "SD"], "HRWPDSI": ["KS", "OK", "NE", "CO", "TX"], "NPLPDSI": ["ND", "SD", "MN", "MT"], "DLTPDSI": ["AR", "LA", "MS", "TN"], "SEPDSI": ["GA", "FL", "AL", "SC"], "TXPDSI": ["TX"],
                "WSTPDSI": ["CA", "OR", "WA", "ID", "NV", "UT", "AZ"]}
NCEI_CODE = {"011": "IL", "012": "IN", "013": "IA", "023": "MO", "033": "OH", "003": "AR", "016": "LA", "022": "MS", "040": "TN", "009": "GA", "008": "FL", "001": "AL", "038": "SC", "041": "TX", "004": "CA", "035": "OR", "045": "WA", "010": "ID", "026": "NV",
             "042": "UT", "002": "AZ", "014": "KS", "034": "OK", "025": "NE", "005": "CO", "032": "ND", "039": "SD", "021": "MN", "024": "MT"}
INDEX_FILES = {"ONI": "oni.txt", "NINO34": "sstoi.txt", "AO": "ao.txt", "NAO": "nao.txt", "PDO": "pdo.txt", "SOI": "soi.txt",
               "NINO12": "sstoi.txt", "NINO3": "sstoi.txt", "NINO4": "sstoi.txt", "MEI2": "meiv2.txt", "AAO": "aao.txt", "TNA": "tna.txt", "TSA": "tsa.txt", "WHWP": "whwp.txt", "PNA": "pna.txt",
               "TNI": "tni.txt", "NPGO": "npgo.txt", "GLBT": "gistemp.csv", "SNOW": "snow.txt", **{k: "climdiv-pdsist.txt" for k in PDSI_REGIONS}}


def table_sha():
    with open(TABLE_PATH, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


# ----------------------------------------------------------------------------- climate series
def fetch_indices(names):
    """Refetch the NOAA files needed; keep the cached copy if the fetch fails."""
    import requests
    os.makedirs(DATA_DIR, exist_ok=True)
    if any(n in PDSI_REGIONS for n in names):
        try:   # the NCEI file name carries a version and the release date, so read the directory listing for the current one
            lst = requests.get(NCEI_DIR, timeout=40, headers={"User-Agent": "Mozilla/5.0"}).text
            found = sorted(set(re.findall(r"climdiv-pdsist-v[0-9.]+-[0-9]+", lst)))
            if found:
                r = requests.get(NCEI_DIR + found[-1], timeout=60, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.text) > 100000:
                    with open(os.path.join(DATA_DIR, "climdiv-pdsist.txt"), "w") as fh:
                        fh.write(r.text)
        except Exception as e:  # noqa: BLE001
            print(f"  NCEI drought fetch failed ({type(e).__name__}); using cached copy")
    for n in names:
        fn = INDEX_FILES[n]
        if fn == "climdiv-pdsist.txt":
            continue
        try:
            r = requests.get(URLS[fn], timeout=40, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.text) > 2000:
                with open(os.path.join(DATA_DIR, fn), "w") as fh:
                    fh.write(r.text)
        except Exception as e:  # noqa: BLE001
            print(f"  index fetch failed for {fn} ({type(e).__name__}); using cached copy")


def _next15(vals, months=1):
    s = pd.Series(vals).dropna()
    idx = [pd.Timestamp(y, m, 1) + pd.DateOffset(months=months) + pd.Timedelta(days=14) for (y, m) in s.index]
    return pd.Series(s.values, index=pd.DatetimeIndex(idx)).sort_index()


def _table_ym(path, missing):
    out = {}
    for line in open(path):
        parts = line.split()
        if len(parts) >= 13 and re.fullmatch(r"\d{4}", parts[0]):
            for m, v in enumerate(parts[1:13], 1):
                try:
                    x = float(v)
                except ValueError:
                    continue
                if abs(x) < missing:
                    out[(int(parts[0]), m)] = x
    return out


def index_series(name):
    p = lambda f: os.path.join(DATA_DIR, f)
    if name == "ONI":
        seas = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6, "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
        o = pd.read_csv(p("oni.txt"), sep=r"\s+")
        idx = [pd.Timestamp(int(y), seas[s], 1) + pd.DateOffset(months=2) + pd.Timedelta(days=9) for y, s in zip(o.YR, o.SEAS)]
        return pd.Series(o.ANOM.values, index=pd.DatetimeIndex(idx)).sort_index()
    if name == "NINO34":
        d = pd.read_csv(p("sstoi.txt"), sep=r"\s+")
        d.columns = ["YR", "MON", "N12", "N12A", "N3", "N3A", "N4", "N4A", "N34", "N34A"]
        return _next15({(int(r.YR), int(r.MON)): r.N34A for r in d.itertuples()})
    if name == "AO":
        d = pd.read_csv(p("ao.txt"), sep=r"\s+", header=None)
        return _next15({(int(r[0]), int(r[1])): r[2] for r in d.itertuples(index=False)})
    if name == "NAO":
        return _next15(_table_ym(p("nao.txt"), 99))
    if name == "PDO":
        return _next15(_table_ym(p("pdo.txt"), 9.0))
    if name == "SOI":
        txt = open(p("soi.txt")).read().splitlines()
        start = [i for i, l in enumerate(txt) if "STANDARDIZED" in l][0]
        out = {}
        for l in txt[start:]:
            if re.match(r"^\d{4}", l):
                y = int(l[:4])
                for m in range(12):
                    try:
                        x = float(l[4 + m * 6:4 + (m + 1) * 6].strip())
                    except ValueError:
                        continue
                    if abs(x) < 99:
                        out[(y, m + 1)] = x
        return _next15(out)
    if name in ("NINO12", "NINO3", "NINO4"):   # CPC OISST regional anomalies, public on the 15th of month m+1
        d = pd.read_csv(p("sstoi.txt"), sep=r"\s+")
        d.columns = ["YR", "MON", "N12", "N12A", "N3", "N3A", "N4", "N4A", "N34", "N34A"]
        col = {"NINO12": "N12A", "NINO3": "N3A", "NINO4": "N4A"}[name]
        return _next15({(int(r.YR), int(r.MON)): getattr(r, col) for r in d.itertuples()})
    if name == "MEI2":
        return _next15(_table_ym(p("meiv2.txt"), 99))
    if name == "AAO":
        out = {}
        for l in open(p("aao.txt")):
            t = l.split()
            if len(t) == 3:
                out[(int(t[0]), int(t[1]))] = float(t[2])
        return _next15(out)
    if name in ("TNA", "TSA", "WHWP", "PNA"):   # NOAA PSL files, updated irregularly: taken as public on the 15th of month m+2
        return _next15(_table_ym(p(name.lower() + ".txt"), 99), months=2)
    if name in PDSI_REGIONS:   # NCEI state PDSI, region mean; public on the 12th of month m+1
        rows = {}
        for line in open(p("climdiv-pdsist.txt")):
            code = line[:3]
            if len(line) < 20 or code not in NCEI_CODE:
                continue
            year, vals = int(line[6:10]), line[10:].split()
            if len(vals) < 12:
                continue
            for m, v in enumerate(vals[:12], 1):
                x = float(v)
                if x > -99:
                    rows.setdefault(NCEI_CODE[code], {})[pd.Timestamp(year, m, 1)] = x
        df = pd.DataFrame(rows).sort_index()
        sr = df[PDSI_REGIONS[name]].mean(axis=1).dropna()
        return pd.Series(sr.values, index=pd.DatetimeIndex([d + pd.DateOffset(months=1) + pd.Timedelta(days=11) for d in sr.index])).sort_index()
    if name == "TNI":
        return _next15(_table_ym(p("tni.txt"), 99), months=5)
    if name == "NPGO":
        return _next15(_table_ym(p("npgo.txt"), 99), months=2)
    if name == "GLBT":
        out = {}
        for l in open(p("gistemp.csv")):
            t = l.strip().split(",")
            if t and re.fullmatch(r"\d{4}", t[0]):
                for m, v in enumerate(t[1:13], 1):
                    try:
                        out[(int(t[0]), m)] = float(v)
                    except ValueError:
                        pass
        return _next15(out)
    if name == "SNOW":   # Northern Hemisphere snow-cover extent anomaly vs fixed 1981-2010 monthly normals, million km2
        raw = {}
        for l in open(p("snow.txt")):
            t = l.split()
            if len(t) == 3:
                raw[pd.Timestamp(int(t[0]), int(t[1]), 1)] = float(t[2]) / 1e6
        sr = pd.Series(raw).sort_index()
        base = sr[(sr.index.year >= 1981) & (sr.index.year <= 2010)]
        clim = base.groupby(base.index.month).mean()
        an = sr - sr.index.month.map(clim).values
        return _next15({(d.year, d.month): v for d, v in an.items()})
    raise KeyError(name)


def climate_series(x, price_index):
    """Daily series for a predictor name like ONI_chg (the level; increment = change over tau) or ONI_mean (cumulative sum; increment = sum over tau days)."""
    idx_name, form = x.rsplit("_", 1)
    s = index_series(idx_name)
    daily = s.reindex(s.index.union(price_index)).ffill().reindex(price_index)
    daily[daily.index < s.index.min()] = np.nan
    return daily if form == "chg" else daily.cumsum()


# ----------------------------------------------------------------------------- prices
def update_prices(today_utc=None):
    """Append calendar rows (every day through yesterday, UTC) to the stored panel and fill closes from Yahoo's chart endpoint.
    Only dates after the last stored row are written; stored history is never revised. A failed ticker leaves NaN for the new rows."""
    sys.path.insert(0, ROOT)
    from weatherdash import prices as px_mod
    today_utc = today_utc or datetime.now(timezone.utc).date()
    p = pd.read_parquet(PRICES_PATH)
    last = p.index.max()
    want = pd.date_range(last + pd.Timedelta(days=1), pd.Timestamp(today_utc) - pd.Timedelta(days=1))
    if len(want) == 0:
        return p, []
    new = pd.DataFrame(np.nan, index=want, columns=p.columns)
    failed = []
    for t in p.columns:
        try:
            d = px_mod.fetch_one(t, "1mo").set_index("date")["adjclose"]
            d = d[~d.index.duplicated(keep="last")]
            new[t] = d.reindex(want).values
        except Exception as e:  # noqa: BLE001
            failed.append(f"{t}: {type(e).__name__}")
    p = pd.concat([p, new])
    p.to_parquet(PRICES_PATH)
    return p, failed


def load_inputs(today_utc=None, asof=None):
    today_utc = today_utc or datetime.now(timezone.utc).date()
    table = pd.read_parquet(TABLE_PATH)
    prices = pd.read_parquet(PRICES_PATH)
    prices = prices[prices.index.date < today_utc]
    if asof is not None:
        prices = prices[prices.index <= pd.Timestamp(asof)]
    return prices, table


def x_increment(x, tau, price_index):
    s = climate_series(x, price_index)
    return s - s.shift(tau)


# ----------------------------------------------------------------------------- events
def find_entry_events(prices, table, after, include_ongoing_at=None):
    conds = table[COND + ["x_threshold"]].drop_duplicates(COND)
    sha = table_sha()
    rows = []
    for r in conds.itertuples():
        inc = x_increment(r.X, int(r.tau_past), prices.index)
        thr = float(r.x_threshold)
        fire = (inc > thr) if r.direction == "bullish" else (inc < thr)
        fire = fire.fillna(False)
        onset = fire & ~fire.shift(1, fill_value=False)
        for dt in onset[(onset) & (onset.index > after)].index:
            rows.append((dt.strftime("%Y-%m-%d"), r.X, int(r.tau_past), float(r.q_X), r.direction, "onset", float(inc.loc[dt]), thr, sha))
        if include_ongoing_at is not None and include_ongoing_at in fire.index and bool(fire.loc[include_ongoing_at]):
            rows.append((include_ongoing_at.strftime("%Y-%m-%d"), r.X, int(r.tau_past), float(r.q_X), r.direction, "ongoing_at_freeze",
                         float(inc.loc[include_ongoing_at]), thr, sha))
    return pd.DataFrame(rows, columns=EVENT_COLS)


def load_events():
    if not os.path.exists(EVENTS_PATH):
        return pd.DataFrame(columns=EVENT_COLS)
    return pd.read_csv(EVENTS_PATH, dtype={"entry_date": str})


def log_new_events():
    prices, table = load_inputs()
    ev = load_events()
    first_run = len(ev) == 0
    last_logged = max(pd.Timestamp(ev["entry_date"].max()), TABLE_END) if len(ev) else TABLE_END
    new = find_entry_events(prices, table, after=last_logged, include_ongoing_at=TABLE_END if first_run else None)
    if len(new):
        ev = pd.concat([ev, new], ignore_index=True).drop_duplicates(COND + ["entry_date"])
        ev = ev.sort_values(["entry_date", "X", "tau_past", "q_X", "direction"])
        ev.to_csv(EVENTS_PATH, index=False)
    print(f"CPE climate ledger: {len(new)} new entry event(s) (after {last_logged.date()}; through {prices.index.max().date()}); {len(ev)} total")
    return ev


# ----------------------------------------------------------------------------- scoring
def score(ev=None, asof=None):
    prices, table = load_inputs(asof=asof)
    ev = load_events() if ev is None else ev
    if asof is not None:
        ev = ev[pd.to_datetime(ev["entry_date"]) <= pd.Timestamp(asof)]
    if ev.empty:
        return pd.DataFrame(), prices.index.max()
    ev = ev.copy()
    ev["entry_date"] = pd.to_datetime(ev["entry_date"])
    rows = ev[["entry_date", "kind"] + COND].merge(table, on=COND, how="inner")
    rows["event"], rows["live_base"] = np.nan, np.nan
    rows["outcome_date"] = pd.NaT
    # Horizons are in the TARGET's own trading days: the price panel is a seven-day calendar (weekend rows are NaN for FX, futures and
    # ETFs), so counting rows would make a 252-day horizon 252 calendar days. The outcome opens on the first bar of the target on or after the
    # entry date (a climate state that crosses on a weekend is traded on the next bar) and closes tau of the target's own bars later.
    for (y, tf), g in rows.groupby(["Y", "tau_future"]):
        if y not in prices.columns:
            continue
        tf = int(tf)
        own = prices[y].dropna()
        fwd = np.log(own.shift(-tf) / own)
        ent = own.index.searchsorted(g["entry_date"].values)
        ok = (ent < len(own)) & (ent + tf <= len(own) - 1)
        w_all = fwd[own.index > TABLE_END].dropna().values   # the same event on every resolved bar of the live window
        for (qy, d, thr), gg in g.groupby(["q_Y", "direction", "y_threshold"]):
            sel = ok[g.index.get_indexer(gg.index)]
            r = gg[sel]
            if r.empty:
                continue
            e = ent[g.index.get_indexer(r.index)]
            f = fwd.values[e]
            flag = (f > thr) if d == "bullish" else (f < thr)
            flag = np.where(np.isnan(f), np.nan, flag.astype(float))
            rows.loc[r.index, "event"] = flag
            rows.loc[r.index, "live_base"] = float(((w_all > thr) if d == "bullish" else (w_all < thr)).mean()) if len(w_all) else np.nan
            rows.loc[r.index, "outcome_date"] = own.index[e + tf]
    rows["resolved"] = rows["event"].notna()
    return rows, prices.index.max()


def live_stats(rows=None, last_bar=None, ev=None):
    if rows is None:
        rows, last_bar = score(ev)
    ev = load_events() if ev is None else ev
    out = {"table_end": str(TABLE_END.date()), "table_sha": table_sha(), "n_table_rows": int(len(pd.read_parquet(TABLE_PATH))),
           "n_events": int(len(ev)), "n_rows": int(len(rows)), "last_bar": str(last_bar.date()) if last_bar is not None else None,
           "n_resolved": 0, "n_pending": 0, "by_horizon": []}
    if rows.empty:
        return out
    res = rows[rows["resolved"]]
    out["n_resolved"], out["n_pending"] = int(len(res)), int(len(rows) - len(res))
    for tf, g in rows.groupby("tau_future"):
        r = res[res["tau_future"] == tf]
        row = {"horizon": int(tf), "n_pending": int(len(g) - len(r)), "n": int(len(r))}
        pend = g[~g["resolved"]]
        if len(pend):
            est = pend["entry_date"] + pd.to_timedelta((pend["tau_future"] * 1.4).round().astype(int), unit="D")   # trading days ~ 1.4 calendar days (approximate)
            row["first_pending"] = str(est.min().date())
        if len(r):
            row.update({"claimed": round(float(r["CPE"].mean()), 4), "hit": round(float(r["event"].mean()), 4), "base": round(float(r["uncond_prob"].mean()), 4),
                        "live_base": round(float(r["live_base"].mean()), 4), "events": int(r.groupby(["entry_date"] + COND).ngroups), "targets": int(r["Y"].nunique())})
        out["by_horizon"].append(row)
    return out


def status():
    """Watchlist: each distinct condition's current value against its frozen threshold."""
    prices, table = load_inputs()
    conds = table[COND + ["x_threshold"]].drop_duplicates(COND)
    print(f"\nWatchlist as of {prices.index.max().date()} (state of the climate series against the frozen thresholds)")
    print(f"{'condition':<44}{'now':>9}{'threshold':>11}{'gap':>9}  state")
    for r in conds.itertuples():
        inc = x_increment(r.X, int(r.tau_past), prices.index)
        v = float(inc.dropna().iloc[-1])
        thr = float(r.x_threshold)
        firing = (v > thr) if r.direction == "bullish" else (v < thr)
        gap = (thr - v) if r.direction == "bullish" else (v - thr)   # amount the state still has to move to fire
        tl = "bullish: tail above" if r.direction == "bullish" else "bearish: tail below"
        ys = sorted(set(table[(table.X == r.X) & (table.tau_past == r.tau_past) & (table.q_X == r.q_X) & (table.direction == r.direction)]["Y"]))
        print(f"{r.X + ' tau=' + str(int(r.tau_past)) + ' q=' + str(r.q_X) + ' ' + tl:<44}{v:>9.2f}{thr:>11.2f}{(0 if firing else gap):>9.2f}  {'FIRING' if firing else 'waiting'}  -> {', '.join(ys)}")


def summary():
    rows, last_bar = score()
    s = live_stats(rows, last_bar)
    print(f"\nTable: {s['n_table_rows']} frozen rows (sha {s['table_sha']}, frozen {s['table_end']}); entry events {s['n_events']}, scored rows {s['n_rows']}, "
          f"resolved {s['n_resolved']}, pending {s['n_pending']}; last bar {s['last_bar']}.")
    for r in s["by_horizon"]:
        if r["n"]:
            print(f"  tau_future={r['horizon']:>3}: n={r['n']:>4}  claimed {r['claimed']:.3f}  realised {r['hit']:.3f}  table base {r['base']:.3f}  live base {r['live_base']:.3f}  pending {r['n_pending']}")
        else:
            print(f"  tau_future={r['horizon']:>3}: no outcomes yet, {r['n_pending']} pending (first about {r.get('first_pending')})")


# ----------------------------------------------------------------------------- dashboard payload
INDEX_NAMES = {"ONI": "Oceanic Nino Index", "NINO34": "Nino 3.4 sea-surface anomaly", "AO": "Arctic Oscillation", "NAO": "North Atlantic Oscillation", "PDO": "Pacific Decadal Oscillation",
               "SOI": "Southern Oscillation Index",
               "NINO12": "Nino 1+2 (Peru coast) sea-surface anomaly", "NINO3": "Nino 3 sea-surface anomaly", "NINO4": "Nino 4 sea-surface anomaly", "MEI2": "Multivariate ENSO Index v2",
               "AAO": "Southern Annular Mode", "TNA": "Tropical North Atlantic sea-surface anomaly", "TSA": "Tropical South Atlantic sea-surface anomaly",
               "WHWP": "Atlantic warm pool", "PNA": "Pacific-North American pattern",
               "HRWPDSI": "Wheat-belt drought index (PDSI)", "NPLPDSI": "Northern-plains drought index (PDSI)", "DLTPDSI": "Mississippi Delta drought index (PDSI)", "SEPDSI": "Southeast drought index (PDSI)",
               "TXPDSI": "Texas drought index (PDSI)", "CBPDSI": "Corn Belt drought index (PDSI)", "WSTPDSI": "Western drought index (PDSI)", "TNI": "Trans-Nino index", "NPGO": "North Pacific Gyre Oscillation",
               "GLBT": "Global temperature anomaly", "SNOW": "Northern Hemisphere snow-cover anomaly"}
TARGET_NAMES = {"ZL=F": "Soybean oil", "CC=F": "Cocoa", "LE=F": "Live cattle", "CL=F": "Crude oil", "CT=F": "Cotton", "DBB": "Base metals ETF (DBB)", "DJP": "Broad commodities ETN (DJP)", "HE=F": "Lean hogs", "HO=F": "Heating oil",
                "KE=F": "KC wheat", "NG=F": "Natural gas", "OJ=F": "Orange juice", "SB=F": "Sugar", "UGA": "Gasoline ETF (UGA)", "UNG": "Natural gas ETF (UNG)", "USO": "Oil ETF (USO)",
                "ZC=F": "Corn", "ZM=F": "Soybean meal", "ZO=F": "Oats", "ZW=F": "Chicago wheat", "EWY": "South Korea equities (EWY)", "EWZ": "Brazil equities (EWZ)", "FXI": "China equities (FXI)", "HG=F": "Copper", "INRUSD=X": "Indian rupee", "KC=F": "Coffee",
                "RB=F": "Gasoline", "ZARUSD=X": "South African rand", "ZS=F": "Soybeans"}


def describe(x, tau, q, direction):
    idx, form = x.rsplit("_", 1)
    what = f"{INDEX_NAMES.get(idx, idx)}, {'average over' if form == 'mean' else 'change over'} the last {int(tau)} days"
    tail = round((1 - q) * 100)
    return f"{what}, in its {'highest' if direction == 'bullish' else 'lowest'} {tail}% of readings through 2012"


def payload():
    prices, table = load_inputs()
    ev = load_events()
    rows, last_bar = score(ev)
    stats = live_stats(rows, last_bar, ev)
    conds = table[COND + ["x_threshold"]].drop_duplicates(COND)
    watch = []
    for r in conds.itertuples():
        tau = int(r.tau_past)
        inc = x_increment(r.X, tau, prices.index).dropna()
        v, thr = float(inc.iloc[-1]), float(r.x_threshold)
        scale = tau if r.X.endswith("_mean") else 1  # _mean increments are sums over tau days: show the average anomaly
        firing = (v > thr) if r.direction == "bullish" else (v < thr)
        sub = table[(table.X == r.X) & (table.tau_past == r.tau_past) & (table.q_X == r.q_X) & (table.direction == r.direction)]
        watch.append({"condition": describe(r.X, tau, float(r.q_X), r.direction), "x": r.X, "tau_past": tau, "q_X": float(r.q_X), "direction": r.direction,
                      "now": round(v / scale, 3), "threshold": round(thr / scale, 3), "gap": 0.0 if firing else round(abs(thr - v) / scale, 3), "firing": bool(firing),
                      "n_rows": int(len(sub)), "claimed_cpe": round(float(sub["CPE"].mean()), 3), "test_cpe": round(float(sub["cpe_test"].mean()), 3),
                      "test_base": round(float(sub["base_test"].mean()), 3),
                      "targets": [{"y": y, "name": TARGET_NAMES.get(y, y), "horizons": sorted({int(h) for h in g["tau_future"]})} for y, g in sub.groupby("Y")]})
    watch.sort(key=lambda w: (not w["firing"], w["gap"] / (abs(w["threshold"]) + 1e-9)))
    frozen = [{"condition": describe(r.X, int(r.tau_past), float(r.q_X), r.direction), "target": TARGET_NAMES.get(r.Y, r.Y), "horizon": int(r.tau_future), "direction": r.direction,
               "q_Y": float(r.q_Y), "claimed": round(float(r.CPE), 3), "lift": round(float(r.lift), 2), "n_ep_f": int(r.n_ep_f), "test_cpe": round(float(r.cpe_test), 3),
               "test_base": round(float(r.base_test), 3), "n_ep_t": int(r.n_ep_t), "tier": r.tier} for r in table.sort_values(["Y", "tau_future", "X"]).itertuples()]
    events = ev.to_dict("records")
    for e in events:
        e["targets"] = sorted(table[(table.X == e["X"]) & (table.tau_past == e["tau_past"]) & (table.q_X == e["q_X"]) & (table.direction == e["direction"])]["Y"].map(lambda y: TARGET_NAMES.get(y, y)).unique())
        e["condition"] = describe(e["X"], int(e["tau_past"]), float(e["q_X"]), e["direction"])
        scale = int(e["tau_past"]) if e["X"].endswith("_mean") else 1   # show averages, as the watchlist does, not the engine's cumulative sums
        e["x_move"], e["x_threshold"] = float(e["x_move"]) / scale, float(e["x_threshold"]) / scale
    return {"asof": str(prices.index.max().date()), "enso": enso_state(), "stats": stats, "watch": watch, "frozen": frozen, "events": events}


def enso_state():
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    oni = index_series("ONI").dropna()
    n34 = index_series("NINO34").dropna()
    oni, n34 = oni[oni.index <= today], n34[n34.index <= today]  # the lagged series carry future publication dates
    v = float(oni.iloc[-1])
    cls = "strong El Nino" if v >= 1.5 else "El Nino" if v >= 0.5 else "strong La Nina" if v <= -1.5 else "La Nina" if v <= -0.5 else "neutral"
    return {"oni": round(v, 2), "oni_available": str(oni.index[-1].date()), "nino34_anom": round(float(n34.iloc[-1]), 2), "nino34_available": str(n34.index[-1].date()),
            "state": cls, "note": "ONI is published about ten days into the second month after its three-month window; Nino 3.4 monthly on the 15th of the following month."}


def payload_all():
    """Payload for every book (frozen table); each is computed with the module paths pointed at that book."""
    out = []
    for bid, b in BOOKS.items():
        use(bid)
        pl = payload()
        tb = pd.read_parquet(TABLE_PATH)
        fam = tb["X"].str.split("_").str[0]
        enso = fam.isin(["ONI", "NINO34", "NINO12", "NINO3", "NINO4", "MEI2", "SOI"])
        keys = tb.groupby(["Y", "direction", "tau_future"]).ngroups
        pl.update({"id": bid, "label": b["label"], "note": b.get("note", ""), "frozen_on": b["frozen"], "frozen_rows_n": int(len(tb)),
                   "redundancy": (f"{int(enso.sum())} of the {len(tb)} rows come from ENSO indices that move together, so they restate one ocean state and reduce to {keys} distinct target, direction and horizon keys, "
                                  f"not {len(tb)} independent findings." if enso.sum() > 0.5 * len(tb) else "")})
        out.append(pl)
    use("b1")
    return out


def run_all():
    """Daily step for every book: refresh indices, extend the price store, log new entry events."""
    names = set()
    for bid in BOOKS:
        use(bid)
        names |= {x.rsplit("_", 1)[0] for x in pd.read_parquet(TABLE_PATH)["X"]}
    fetch_indices(sorted(names))
    for bid in BOOKS:
        use(bid)
        try:
            _, failed = update_prices()
            if failed:
                print(f"[{bid}] price fetch incomplete:", failed)
            log_new_events()
        except Exception as e:  # noqa: BLE001
            print(f"[{bid}] ledger step failed: {type(e).__name__}: {str(e)[:150]}")
    use("b1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if not (args.summary or args.status):
        run_all()
    for bid in BOOKS:
        use(bid)
        print(f"\n==== {BOOKS[bid]['label']} ====")
        summary()
        status()
    use("b1")


if __name__ == "__main__":
    sys.exit(main())
