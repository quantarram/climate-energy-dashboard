"""The live hypothesis test: do free weather forecasts, turned into decisions, make money?

H0 (registered 2026-10-11, scored from the first signal on REGISTRATION_DATE): decisions driven by the dashboard's own demand / net-load / wind forecasts earn no more,
after costs, than (a) holding nothing, (b) holding the same instruments, and (c) the same decisions driven by climatology alone (the seasonal ramp, no forecast information).

Everything is frozen in REGISTRY: signals, orientation (more weather-driven demand or tighter net load = long, never chosen from data), instruments, thresholds, holds, costs and the
rule for what would count as evidence of an edge. Positions are recomputed from the logged signals and the price log on every run, so the record is auditable from git history.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIG_LOG = os.path.join(ROOT, "data", "ledger_decision_signals.csv")
REGISTRATION_DATE = pd.Timestamp("2026-10-12")  # first issue date whose signal is scored (the first trading day after registration)
INSTRUMENTS = ["NG=F", "UNG", "XLU", "VST", "NRG", "CEG", "ICLN"]
CONTROL = "SPY"
HOLDS = [1, 5]
RULES = ["long_short", "market_neutral"]
THRESH = 0.5  # in expanding standard deviations
COST = 0.0005  # per side, on every change of position
MIN_SD_OBS = 60
WEATHER_SIGNALS = ["NAT_netload_13", "NAT_demand_17", "ERCO_netload_17", "NAT_lowwind_17", "PJM_demand_13"]
TWIN_SIGNALS = ["TWIN_ramp_17"]
REGIONS = ["ERCO", "PJM", "CISO", "NYIS", "ISNE", "MISO"]
DECISION_DAYS = [60, 125, 250]  # review points
N_REGISTERED = (len(WEATHER_SIGNALS) + len(TWIN_SIGNALS)) * len(INSTRUMENTS) * len(HOLDS) * len(RULES)

REGISTRY = {
    "registered": "2026-10-11", "first_scored_signal": str(REGISTRATION_DATE.date()),
    "hypothesis": "Free weather forecasts, converted into decisions, earn no more after costs than the same decisions without a forecast or with climatology only.",
    "signals": {
        "NAT_netload_13": "demand-weighted six-region net-load anomaly (demand - wind - solar, forecast minus climatology, % of climatological demand), mean over leads 1-3",
        "NAT_demand_17": "demand-weighted six-region demand anomaly, mean over leads 1-7",
        "ERCO_netload_17": "ERCOT net-load anomaly, mean over leads 1-7",
        "NAT_lowwind_17": "minus the demand-weighted wind anomaly (low wind = long), mean over leads 1-7",
        "PJM_demand_13": "PJM demand anomaly, mean over leads 1-3",
        "TWIN_ramp_17": "climatology twin: climatological net load over the coming 7 days minus the previous 7 days (the seasonal ramp; no forecast information)"},
    "instruments": INSTRUMENTS, "control": CONTROL, "rules": RULES, "holds_trading_days": HOLDS, "threshold_sd": THRESH, "cost_per_side": COST,
    "standardisation": "centred on the expanding mean and scaled by the expanding standard deviation of all earlier values of the signal (history from the 2026-06-01 backfill included), at least %d observations" % MIN_SD_OBS,
    "timing": "signal from the 00z IFS cycle of the issue date; position entered at that day's close and earned from the next trading day; issue dates that are not trading days are skipped",
    "evidence_of_edge": ("Reviewed at %s trading days. Evidence of an edge only if, at the review, the equal-weight weather family has a positive annualised net return, exceeds the "
                         "climatology twin family, has a positive beta-adjusted mean-difference alpha against SPY, and is positive in both halves of the sample. Otherwise: no evidence of an edge.") % DECISION_DAYS,
    "mechanics_check": "The scoring code was exercised on 2026-08-15 to 2026-10-09 data to test the mechanics only; those days are not part of the test and no rule was changed after seeing them, except that signals are centred (see standardisation) after an uncentred version was found to stay long almost all the time.",
    "not_claimed": "No result is tested for statistical significance, and a null result is not proof that no edge exists anywhere, only that none shows up in this registered set."}


# ----------------------------------------------------------------------------- signals
def _anoms(dem, ren, issue):
    """dem: demand ledger rows of one issue date; ren: wind/solar rows. Returns dict of per-region lead->value arrays."""
    out = {}
    for reg in REGIONS:
        d = dem[dem.region == reg].set_index("lead_days")
        w = ren[(ren.region == reg) & (ren.resource == "wind")].set_index("lead_days")
        s = ren[(ren.region == reg) & (ren.resource == "solar")].set_index("lead_days")
        if d.empty:
            continue
        wf, wc = w.gen_fc_mwh.reindex(d.index).fillna(0.0), w.gen_clim_mwh.reindex(d.index).fillna(0.0)
        sf, sc = s.gen_fc_mwh.reindex(d.index).fillna(0.0), s.gen_clim_mwh.reindex(d.index).fillna(0.0)
        nlf, nlc = d.demand_fc_mwh - wf - sf, d.demand_clim_mwh - wc - sc
        out[reg] = pd.DataFrame({"nl": (nlf - nlc) / d.demand_clim_mwh * 100, "dem": (d.demand_fc_mwh - d.demand_clim_mwh) / d.demand_clim_mwh * 100,
                                 "wind": -(wf - wc) / d.demand_clim_mwh * 100, "w": d.demand_clim_mwh, "nlc": nlc, "demc": d.demand_clim_mwh})
    return out


def signals_for_issue(dem, ren, prev_clim=None):
    """Signal values of one issue date. prev_clim: climatological net load (MWh, six regions summed) for each of the previous 7 days, if known."""
    a = _anoms(dem, ren, None)
    if not a:
        return None
    def nat(col, lo, hi):
        num = sum(v.loc[lo:hi, col].mean() * v.loc[lo:hi, "w"].mean() for v in a.values())
        den = sum(v.loc[lo:hi, "w"].mean() for v in a.values())
        return float(num / den)
    sig = {"NAT_netload_13": nat("nl", 1, 3), "NAT_demand_17": nat("dem", 1, 7), "NAT_lowwind_17": nat("wind", 1, 7),
           "ERCO_netload_17": float(a["ERCO"].loc[1:7, "nl"].mean()) if "ERCO" in a else np.nan,
           "PJM_demand_13": float(a["PJM"].loc[1:3, "dem"].mean()) if "PJM" in a else np.nan}
    fut = sum(v.loc[1:7, "nlc"].mean() for v in a.values())
    tot = sum(v.loc[1:7, "demc"].mean() for v in a.values())
    sig["TWIN_ramp_17"] = float((fut - prev_clim) / tot * 100) if prev_clim is not None else np.nan
    return sig


def history_from_ledgers(dem_led, ren_led):
    """Signals for every issue date in the demand and wind/solar ledgers (first-issued forecasts), for standardisation and the audit trail."""
    dem_led, ren_led = dem_led.copy(), ren_led.copy()
    for c in ("demand_fc_mwh", "demand_clim_mwh"):
        dem_led[c] = dem_led[c].astype(float)
    for c in ("gen_fc_mwh", "gen_clim_mwh"):
        ren_led[c] = ren_led[c].astype(float)
    dem_led["issue_date"] = pd.to_datetime(dem_led["issue_date"])
    ren_led["issue_date"] = pd.to_datetime(ren_led["issue_date"])
    # climatological net load of each (past) day, six regions, from lead-0 rows
    cl = {}
    for d, g in dem_led[dem_led.lead_days == 0].groupby("issue_date"):
        r = ren_led[(ren_led.issue_date == d) & (ren_led.lead_days == 0)]
        cl[d] = float(g.demand_clim_mwh.sum() - r.gen_clim_mwh.sum())
    rows = {}
    dem_g, ren_g = dem_led.groupby("issue_date"), ren_led.groupby("issue_date")
    for d in sorted(set(dem_g.groups) & set(ren_g.groups)):
        prev = [cl.get(d - pd.Timedelta(days=k)) for k in range(1, 8)]
        pc = float(np.sum(prev)) / 7 if all(p is not None for p in prev) else None
        s = signals_for_issue(dem_g.get_group(d), ren_g.get_group(d), pc)
        if s:
            rows[d] = s
    return pd.DataFrame(rows).T.sort_index()


def load_signals():
    if os.path.exists(SIG_LOG):
        return pd.read_csv(SIG_LOG, index_col=0, parse_dates=True)
    return pd.DataFrame(columns=WEATHER_SIGNALS + TWIN_SIGNALS)


def save_signals(df):
    df.index.name = "issue_date"
    df.round(5).to_csv(SIG_LOG)


# ----------------------------------------------------------------------------- scoring
def zscores(sig):
    """Centred on the expanding mean and scaled by the expanding standard deviation of all earlier values: the 30-year climatology reads low in a warm year, and an
    uncentred anomaly would keep every rule long (market exposure, not weather information)."""
    mu = sig.expanding(min_periods=MIN_SD_OBS).mean().shift(1)
    sd = sig.expanding(min_periods=MIN_SD_OBS).std().shift(1)
    return (sig - mu) / sd


def positions(z, days, rule, hold):
    s = z.reindex(days)
    pos = pd.Series(np.where(s > THRESH, 1.0, np.where(s < -THRESH, -1.0, 0.0)), index=days)
    pos[s.isna()] = 0.0
    return pos.rolling(hold, min_periods=1).mean().shift(1).fillna(0.0)


def stream_pnl(pos, ret, spy, rule):
    d = pos.diff().abs().fillna(0.0)
    if rule == "market_neutral":
        return pos * (ret - spy) - COST * 2 * d
    return pos * ret - COST * d


def score(sig_all, price_wide):
    """Recompute every registered stream. Returns dict of DataFrames: pnl streams (columns 'sig|inst|hold|rule'), plus baselines."""
    rets = np.log(price_wide / price_wide.shift(1))
    days = rets.index[rets.index >= REGISTRATION_DATE]
    z = zscores(sig_all)
    if len(days) < 2:
        return {"streams": None, "base": None, "z": z}
    full_days = rets.index
    spy = rets[CONTROL].fillna(0.0)
    streams = {}
    for sname in WEATHER_SIGNALS + TWIN_SIGNALS:
        if sname not in z:
            continue
        for tk in INSTRUMENTS:
            if tk not in rets:
                continue
            r = rets[tk].fillna(0.0)
            for rule in RULES:
                for h in HOLDS:
                    pos = positions(z[sname].where(z.index >= REGISTRATION_DATE), full_days, rule, h)
                    streams[f"{sname}|{tk}|{h}|{rule}"] = stream_pnl(pos, r, spy, rule)
    P = pd.DataFrame(streams).loc[days]
    base = {"spy": rets[CONTROL].loc[days].fillna(0.0), "hold_instruments": rets[INSTRUMENTS].loc[days].fillna(0.0).mean(axis=1),
            "flat": pd.Series(0.0, index=days)}
    return {"streams": P, "base": pd.DataFrame(base), "z": z}


def _stats(p, spy):
    p = p.dropna()
    n = len(p)
    if n < 5:
        return {"n_days": n}
    sd = p.std()
    s = spy.reindex(p.index).fillna(0.0)
    var = s.var()
    beta = float(p.cov(s) / var) if var > 0 else None
    cum = p.cumsum()
    half = n // 2
    return {"n_days": n, "ann_return": float(p.mean() * 252), "ann_vol": float(sd * np.sqrt(252)), "sharpe": float(p.mean() / sd * np.sqrt(252)) if sd > 0 else None,
            "beta": beta, "alpha_md_ann": float((p.mean() - (beta or 0) * s.mean()) * 252), "maxdd": float((cum - cum.cummax()).min()),
            "hit_active": None, "first_half": float(p.iloc[:half].sum()), "second_half": float(p.iloc[half:].sum()), "total": float(p.sum())}


def _latest(z):
    return {s: (None if pd.isna(z[s].iloc[-1]) else round(float(z[s].iloc[-1]), 2)) for s in WEATHER_SIGNALS + TWIN_SIGNALS if s in z and len(z)}


def summarise(res):
    if res is None or res.get("streams") is None:
        z = None if res is None else res["z"]
        return {"status": "collecting", "n_days": 0, "review_points": DECISION_DAYS, "reached_reviews": [], "families": {}, "curves": {"dates": []}, "streams": [], "n_streams": 0,
                "latest_z": _latest(z) if z is not None else {}, "latest_issue": str(z.index[-1].date()) if z is not None and len(z) else "", "n_streams_registered": N_REGISTERED,
                "registry": REGISTRY}
    P, B = res["streams"], res["base"]
    w_cols = [c for c in P.columns if c.split("|")[0] in WEATHER_SIGNALS]
    t_cols = [c for c in P.columns if c.split("|")[0] in TWIN_SIGNALS]
    fam = {"weather": P[w_cols].mean(axis=1), "twin": P[t_cols].mean(axis=1) if t_cols else pd.Series(0.0, index=P.index)}
    spy = B["spy"]
    stats = {k: _stats(v, spy) for k, v in fam.items()}
    stats["hold_instruments"] = _stats(B["hold_instruments"], spy)
    stats["spy"] = _stats(spy, spy)
    stats["flat"] = _stats(B["flat"], spy)
    n = len(P)
    reached = [d for d in DECISION_DAYS if n >= d]
    w, t = stats["weather"], stats["twin"]
    verdict = "collecting"
    if reached:
        ok = (w.get("ann_return", -1) > 0 and w.get("ann_return", -1) > t.get("ann_return", 1e9) and w.get("alpha_md_ann", -1) > 0
              and w.get("first_half", -1) > 0 and w.get("second_half", -1) > 0)
        verdict = "evidence_of_edge" if ok else "no_evidence_of_edge"
    per = []
    for c in P.columns:
        sname, tk, h, rule = c.split("|")
        p = P[c]
        act = p.abs() > 0
        per.append({"signal": sname, "inst": tk, "hold": int(h), "rule": rule, "n_days": int(len(p)), "total": float(p.sum()), "ann_return": float(p.mean() * 252),
                    "family": "twin" if sname in TWIN_SIGNALS else "weather"})
    cum = {"dates": [d.strftime("%Y-%m-%d") for d in P.index], "weather": fam["weather"].cumsum().round(5).tolist(), "twin": fam["twin"].cumsum().round(5).tolist(),
           "hold_instruments": B["hold_instruments"].cumsum().round(5).tolist(), "spy": spy.cumsum().round(5).tolist()}
    # latest signal values and today's implied position per weather signal (z of the most recent issue)
    z = res["z"]
    latest = {s: (None if pd.isna(z[s].iloc[-1]) else round(float(z[s].iloc[-1]), 2)) for s in WEATHER_SIGNALS + TWIN_SIGNALS if s in z}
    return {"status": verdict, "n_days": n, "review_points": DECISION_DAYS, "reached_reviews": reached, "families": stats, "curves": cum, "streams": per,
            "latest_z": latest, "latest_issue": str(z.index[-1].date()), "n_streams": len(P.columns), "n_streams_registered": N_REGISTERED, "registry": REGISTRY}
