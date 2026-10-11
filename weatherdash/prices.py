"""Daily closes for the live decision experiment, from Yahoo's public chart endpoint, kept in a small log (data/prices_log.csv).
A failed fetch (rate limit, blocked CI address) leaves the log as it was; the next run refetches the last three months and fills the gap."""
import os
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data", "prices_log.csv")
UA = {"User-Agent": "Mozilla/5.0 (weather-impacts-dashboard)"}


def fetch_one(sym, rng="3mo"):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", params={"range": rng, "interval": "1d"}, headers=UA, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(res["meta"].get("exchangeTimezoneName", "America/New_York")).normalize().tz_localize(None)
    q = res["indicators"]["quote"][0]["close"]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose", q)
    df = pd.DataFrame({"date": ts, "ticker": sym, "close": q, "adjclose": adj}).dropna(subset=["close"])
    return df


def load():
    if os.path.exists(LOG):
        d = pd.read_csv(LOG, parse_dates=["date"])
        return d
    return pd.DataFrame(columns=["date", "ticker", "close", "adjclose"])


def update(symbols, rng="3mo"):
    """Fetch and merge; returns (log, list of symbols that failed)."""
    log = load()
    failed = []
    new = []
    for s in symbols:
        try:
            new.append(fetch_one(s, rng))
        except Exception as e:  # noqa: BLE001
            failed.append(f"{s}: {type(e).__name__}")
        time.sleep(0.4)
    if new:
        log = pd.concat([log] + new).drop_duplicates(["date", "ticker"], keep="last").sort_values(["ticker", "date"])
        log.to_csv(LOG, index=False)
    return log, failed


def wide(log=None, col="adjclose"):
    log = load() if log is None else log
    return log.pivot(index="date", columns="ticker", values=col).sort_index()
