"""Shock and policy monitor: weather shock -> institutional reaction -> price.

Inputs (data/shocks/): policy_events.csv (12 verified export-policy events with sources), reaction_ledger.csv (13 shock episodes with stocks, price pressure and the response),
event_study_results.csv (price paths around the announcements), prices.csv (daily closes of the watched futures, seeded from the research stores and extended daily from Yahoo).

What the record says (computed below, not asserted): restrictions followed high domestic price pressure with thin buffers and no institutional constraint; rainfall alone did not decide it,
and the price had already run up before the announcement. The live panel therefore tracks the observable part, the size of the price run-up against its own history, next to the slow
climate state that drives the shock (ENSO), and the last policy action on file.
"""
import io
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "shocks")
PRICES = os.path.join(DIR, "prices.csv")
WATCH = {  # ticker: (label, countries whose policy it informs)
    "SB=F": ("Sugar", "India"),
    "ZW=F": ("Wheat", "India, Russia"),
    "ZL=F": ("Soy oil", "Indonesia, India"),
}
RICE_FRED = "PRICENPQUSDM"  # Thai 5% broken rice, monthly, USD/t
WINDOW = 60  # rows of the stored daily series: the run-up window used in the event study
RUNUP_FLOOR = 70  # lowest pre-announcement run-up percentile among the restrictions that have daily futures (71)


def _csv(name, **kw):
    return pd.read_csv(os.path.join(DIR, name), **kw)


def update_prices(tickers=None, rng="3mo"):
    from weatherdash import prices as px
    tickers = tickers or list(WATCH)
    old = pd.read_csv(PRICES, index_col=0, parse_dates=True) if os.path.exists(PRICES) else pd.DataFrame(columns=tickers)
    failed = []
    for t in tickers:
        try:
            d = px.fetch_one(t, rng).drop_duplicates("date", keep="last").set_index("date")["close"]
            old = old.reindex(old.index.union(d.index))
            if t not in old.columns:
                old[t] = np.nan
            old.loc[d.index, t] = d.values
        except Exception as e:  # noqa: BLE001
            failed.append(f"{t}: {type(e).__name__}")
    old.sort_index().to_csv(PRICES)
    return old, failed


def rice_monthly():
    """Thai 5% rice, monthly (FRED); stored copy if the fetch fails."""
    path = os.path.join(DIR, "fred_PRICENPQUSDM.csv")
    try:
        import requests
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={RICE_FRED}", timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.text) > 500:
            open(path, "w").write(r.text)
    except Exception:  # noqa: BLE001
        pass
    d = pd.read_csv(path, parse_dates=["observation_date"]).set_index("observation_date").iloc[:, 0].dropna()
    return d


def _runup(s, window):
    """Trailing log return over `window` rows, and its percentile among every such return in the series so far."""
    s = s.dropna()
    r = np.log(s / s.shift(window))
    cur = r.dropna()
    pct = cur.rank(pct=True) * 100  # expanding history would be stricter; the full-sample rank matches how the event study ranked its windows
    return r, pct


def gauges():
    px = pd.read_csv(PRICES, index_col=0, parse_dates=True)
    out = []
    for t, (label, who) in WATCH.items():
        s = px[t].dropna()
        r, pct = _runup(s, WINDOW)
        out.append({"ticker": t, "name": label, "countries": who, "last_date": str(s.index[-1].date()), "last": round(float(s.iloc[-1]), 2),
                    "runup_pct_return": round(float(r.iloc[-1]) * 100, 1), "runup_percentile": round(float(pct.iloc[-1]), 0),
                    "elevated": bool(pct.iloc[-1] >= RUNUP_FLOOR), "frequency": "daily, 60 trading days",
                    "series": [[str(d.date()), round(float(v) * 100, 1)] for d, v in r.dropna().iloc[-780:].iloc[::5].items()]})
    rm = rice_monthly()
    rr = np.log(rm / rm.shift(3)).dropna()
    rp = rr.rank(pct=True) * 100
    out.append({"ticker": "THAI-5%", "name": "Rice (Thai 5%, monthly)", "countries": "India", "last_date": str(rm.index[-1].date()), "last": round(float(rm.iloc[-1]), 1),
                "runup_pct_return": round(float(rr.iloc[-1]) * 100, 1), "runup_percentile": round(float(rp.iloc[-1]), 0), "elevated": bool(rp.iloc[-1] >= RUNUP_FLOOR),
                "frequency": "monthly, 3 months", "series": [[str(d.date()), round(float(v) * 100, 1)] for d, v in rr.iloc[-150:].items()]})
    return out


def enso_state():
    from weatherdash import cpe_climate as cc
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    oni = cc.index_series("ONI").dropna()
    n34 = cc.index_series("NINO34").dropna()
    oni, n34 = oni[oni.index <= today], n34[n34.index <= today]  # the lagged series carry future publication dates
    v = float(oni.iloc[-1])
    cls = "strong El Nino" if v >= 1.5 else "El Nino" if v >= 0.5 else "strong La Nina" if v <= -1.5 else "La Nina" if v <= -0.5 else "neutral"
    return {"oni": round(v, 2), "oni_available": str(oni.index[-1].date()), "nino34_anom": round(float(n34.iloc[-1]), 2), "nino34_available": str(n34.index[-1].date()),
            "state": cls, "note": "ONI is published about ten days into the second month after its three-month window; Nino 3.4 monthly on the 15th of the following month."}


def record():
    ev = _csv("policy_events.csv")
    led = _csv("reaction_ledger.csv", keep_default_na=False)
    study = _csv("event_study_results.csv")
    cnt = led["response_class"].value_counts().to_dict()
    daily = study[study["pre 60d to -1 pct"].notna()]
    rs = daily[daily["class"] == "restrict"]
    return {
        "events": ev[["id", "country", "commodity", "action", "class", "official_date", "weather_link", "trigger_note", "verification"]].fillna("").to_dict("records"),
        "ledger": led[["episode", "country", "shock_severity", "stocks_position", "domestic_price_pressure", "response", "response_class"]].fillna("").to_dict("records"),
        "response_counts": {k: int(v) for k, v in cnt.items()},
        "runup": [{"event": r["event"], "instr": r["instr"], "date": r["date"], "class": r["class"], "pre_pct": float(r["pre 60d to -1 pct"]), "pre_ret": float(r["pre 60d to -1"]),
                   "post20_ret": float(r["post +2..+20"]), "post120_ret": float(r["post +21..+120"])} for _, r in daily.iterrows()],
        "restrict_runup_min": float(rs["pre 60d to -1 pct"].min()) if len(rs) else None,
        "restrict_runup_n": int(len(rs)),
    }


def payload():
    rec = record()
    g = gauges()
    return {"record": rec, "gauges": g, "enso": enso_state(), "runup_floor": RUNUP_FLOOR, "window": WINDOW}
