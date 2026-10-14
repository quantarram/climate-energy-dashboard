"""Registered decision experiment: what the frozen climate conditions imply, and what that earns.

The rule (frozen 2026-10-11 and re-registered unchanged on 2026-10-14 for the rebuilt trading-day tables, scored from 2026-10-14; nothing below changes after that date):
  * every entry event of the frozen tables registered with the rule (batches 1, 3 and 4; the watch-tier table of 2026-10-12 is a condition ledger only and is outside the rule) opens a vote on (target, direction) for each row of its condition, from the next row of the price calendar until that row's horizon expires;
  * one vote per (target, direction); opposite votes on a target cancel; equal weight 1/N over the N targets with a nonzero vote; positions are recomputed daily from the event logs;
  * cost 10 bp per unit of one-way turnover; log returns; weekend rows are rolled into the next weekday, so 252 trading days make a year.
Benchmarks: the same targets held long at the same equal weights over the same windows (same-instrument buy and hold), SPY, and the drift-adjusted excess (each position's return minus the target's own mean daily return
since 2013, signed by the position). Reviews at 125, 250 and 500 trading days. Evidence of an edge only if, at a review, the net annualised return is positive, the drift-adjusted excess is positive, the beta-adjusted
alpha against SPY is positive, and both halves of the sample are positive. Otherwise: no evidence of an edge. No significance test is used; a null result does not show that no edge exists anywhere.
The same rule, run on rows admitted causally (each 1 January, from outcomes already resolved), is in data/cpe_climate/decision_backtest.json; it shows no historical edge, so the live record is the test."""
import json
import os

import numpy as np
import pandas as pd

from weatherdash import cpe_climate as cc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "data", "climate_decisions_daily.csv")
BACKTEST = os.path.join(ROOT, "data", "cpe_climate", "decision_backtest.json")
REGISTRATION_DATE = pd.Timestamp("2026-10-14")
COST = 0.0010
REVIEWS = [125, 250, 500]
DRIFT_FROM, DRIFT_TO = pd.Timestamp("2013-01-02"), pd.Timestamp("2026-10-09")
REGISTRY = {
    "registered": "2026-10-11", "re_registered": "2026-10-14", "re_registration_reason": "The tables were rebuilt with horizons in trading days (the first versions counted calendar-day rows); the rule is unchanged and the two days scored under the first tables are kept in data/cpe_climate/legacy_union_calendar/.", "first_scored_day": str(REGISTRATION_DATE.date()),
    "hypothesis": "Positions implied by the frozen climate conditions earn no more, after costs, than holding the same targets, and no more than the drift of each target explains.",
    "rule": __doc__.split("The rule (frozen 2026-10-11 and re-registered unchanged on 2026-10-14 for the rebuilt trading-day tables, scored from 2026-10-14; nothing below changes after that date):")[1].split("Benchmarks:")[0].strip(),
    "benchmarks": "same targets held long at the same weights over the same windows; SPY; drift-adjusted excess (position return minus the target's own mean daily return since 2013, signed by the position)",
    "reviews_trading_days": REVIEWS,
    "evidence_of_edge": "At a review: positive net annualised return, positive drift-adjusted excess, positive beta-adjusted alpha against SPY, and positive in both halves. Otherwise no evidence of an edge.",
    "history": "The same rule on causally admitted rows (2016-2026) returned -1.4% a year in the extreme tail (Sharpe -0.08) and -2.4% a year for all admitted rows; see the backtest panel. The live record is the test.",
    "not_claimed": "No significance test is used, positions are paper positions, and a null result does not show that no edge exists anywhere.",
}


def _spy():
    from weatherdash import prices
    w = prices.wide()
    return w["SPY"].dropna() if "SPY" in w else pd.Series(dtype=float)


def _inputs():
    """Union price panel (all books share one calendar) and, per book, the table and events."""
    books, panels = [], []
    for bid, b in cc.BOOKS.items():
        if not b.get("decisions", True):
            continue   # the registered rule covers the books frozen before it was registered; later books are condition ledgers only
        cc.use(bid)
        prices_b, table = cc.load_inputs()
        books.append((bid, table, cc.load_events()))
        panels.append(prices_b)
    cc.use("b1")
    idx = panels[0].index
    P = pd.concat([p.reindex(idx) for p in panels], axis=1)
    P = P.loc[:, ~P.columns.duplicated()]
    return books, P


def _returns(P):
    R = {}
    for y in P.columns:
        s = P[y].dropna()
        R[y] = np.log(s / s.shift(1)).dropna().reindex(P.index).fillna(0.0)
    return pd.DataFrame(R)


def _votes(books, P):
    """Per target: (bull count, bear count) arrays over the calendar rows, and the list of supporting rows with their entry."""
    n = len(P.index) + 460   # vote windows run past the last bar: the extra rows hold the positions in force from the next row on
    pos_of = lambda ts: int(P.index.searchsorted(pd.Timestamp(ts)))
    own_cache = {}

    def expiry_row(y, entry_date, tau):
        """Calendar row on which a position opened at the entry holds its last day: tau of the target's OWN trading days after its first
        bar on or after the entry date. Beyond the last bar the date is extrapolated (5/7 of the days are bars for a weekday market)."""
        if y not in own_cache:
            o = P[y].dropna()
            own_cache[y] = (o.index, 1.0 if len(o) and o.index[-400:].dayofweek.nunique() == 7 else 7.0 / 5.0)
        oi, cal_per_bar = own_cache[y]
        ent = int(oi.searchsorted(pd.Timestamp(entry_date)))
        tgt = ent + int(tau)
        if tgt <= len(oi) - 1:
            return pos_of(oi[tgt])
        return pos_of(oi[-1]) + int(np.ceil((tgt - (len(oi) - 1)) * cal_per_bar))

    votes, support = {}, {}
    for bid, table, ev in books:
        if ev.empty:
            continue
        rows = ev[["entry_date", "kind"] + cc.COND].merge(table, on=cc.COND, how="inner")
        for r in rows.itertuples():
            if r.Y not in P.columns:
                continue
            e = pos_of(r.entry_date)
            x = expiry_row(r.Y, r.entry_date, r.tau_future)
            a = votes.setdefault(r.Y, np.zeros((2, n), dtype=np.int32))
            a[0 if r.direction == "bullish" else 1, e + 1:min(n, x + 1)] += 1
            support.setdefault(r.Y, []).append({"book": bid, "x": r.X, "tau_past": int(r.tau_past), "q_X": float(r.q_X), "direction": r.direction, "horizon": int(r.tau_future),
                                                 "entry": str(pd.Timestamp(r.entry_date).date()), "expires_row": x, "claimed": float(r.CPE), "test": float(r.cpe_test), "test_base": float(r.base_test)})
    return votes, support


def _weights(votes, P):
    ys = sorted(votes)
    W = np.zeros((len(ys), next(iter(votes.values())).shape[1] if votes else len(P.index)))
    for i, y in enumerate(ys):
        a = votes[y]
        W[i] = np.where((a[0] > 0) & (a[1] == 0), 1.0, np.where((a[1] > 0) & (a[0] == 0), -1.0, 0.0))
    N = np.maximum((W != 0).sum(0), 1)
    return ys, W / N, W


def _bday(s):
    bd = pd.Series([d if d.weekday() < 5 else d + pd.offsets.BDay(1) for d in s.index], index=s.index)
    return s.groupby(bd).sum()


def _stats(p, spy):
    p = p.dropna()
    n = len(p)
    if n < 5:
        return {"n_days": n}
    sd = p.std()
    s = spy.reindex(p.index).fillna(0.0)
    var = s.var()
    beta = float(p.cov(s) / var) if var > 0 else 0.0
    half = n // 2
    cum = p.cumsum()
    return {"n_days": n, "ann_return": float(p.mean() * 252), "ann_vol": float(sd * np.sqrt(252)), "sharpe": float(p.mean() / sd * np.sqrt(252)) if sd > 0 else None, "beta": beta,
            "alpha_md_ann": float((p.mean() - beta * s.mean()) * 252), "maxdd": float((cum - cum.cummax()).min()), "first_half": float(p.iloc[:half].sum()),
            "second_half": float(p.iloc[half:].sum()), "total": float(p.sum())}


def compute():
    books, P = _inputs()
    R = _returns(P)
    votes, support = _votes(books, P)
    ys, w, W = _weights(votes, P)
    n = len(P.index)
    out = {"asof": str(P.index.max().date()), "last_row": n - 1}
    # today's implied positions: the votes in force on the next row (index n) of the calendar
    nxt = n
    today = []
    for i, y in enumerate(ys):
        if W[i, nxt] != 0:
            sup = [s for s in support[y] if s["expires_row"] >= nxt and s["direction"] == ("bullish" if W[i, nxt] > 0 else "bearish")]
            if not sup:
                continue
            last = n - 1
            today.append({"target": y, "name": cc.TARGET_NAMES.get(y, y), "side": "long" if W[i, nxt] > 0 else "short", "weight": float(w[i, nxt]), "supporting_rows": len(sup),
                          "conditions": sorted({cc.describe(s["x"], s["tau_past"], s["q_X"], s["direction"]) for s in sup}), "indices": sorted({s["x"].rsplit("_", 1)[0] for s in sup}),
                          "horizons": sorted({s["horizon"] for s in sup}), "first_entry": min(s["entry"] for s in sup),
                          "expires_about": str((P.index[last] + pd.Timedelta(days=int(round(max(s["expires_row"] - last for s in sup) * (1.0 if P.index.dayofweek.nunique() == 7 else 1.4))))).date()),
                          "claimed_cpe": round(float(np.mean([s["claimed"] for s in sup])), 3), "test_cpe": round(float(np.mean([s["test"] for s in sup])), 3),
                          "test_base": round(float(np.mean([s["test_base"] for s in sup])), 3)})
    out["today"] = sorted(today, key=lambda d: -abs(d["weight"]))
    # live P&L from the registration date
    Rm = R[ys].values.T if ys else np.zeros((0, n))
    mu = R.loc[DRIFT_FROM:DRIFT_TO, ys].mean().values if ys else np.zeros(0)
    w, W = w[:, :n], W[:, :n]    # drop the look-ahead rows for P&L
    gross = (w * Rm).sum(0)
    cost = COST * np.abs(np.diff(w, axis=1, prepend=0)).sum(0)
    strat = pd.Series(gross - cost, index=P.index)
    excess = pd.Series((w * (Rm - mu[:, None])).sum(0) - cost, index=P.index)
    wl = (W != 0).astype(float)
    wl = wl / np.maximum(wl.sum(0), 1)
    hold = pd.Series((wl * Rm).sum(0), index=P.index)
    spy_px = _spy()
    spy_r = np.log(spy_px / spy_px.shift(1)).dropna()
    live = P.index >= REGISTRATION_DATE
    s, x, h = _bday(strat[live]), _bday(excess[live]), _bday(hold[live])
    spy = spy_r.reindex(s.index).fillna(0.0) if len(s) else pd.Series(dtype=float)
    out["n_days"] = int(len(s))
    out["live"] = {"strategy": _stats(s, spy), "hold_same": _stats(h, spy), "excess_vs_drift": _stats(x, spy), "spy": _stats(spy, spy)} if len(s) >= 5 else {}
    out["curves"] = {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "strategy": s.cumsum().round(5).tolist(), "hold_same": h.cumsum().round(5).tolist(), "spy": spy.cumsum().round(5).tolist()}
    reached = [r for r in REVIEWS if len(s) >= r]
    verdict = "collecting"
    if reached:
        st, ex = out["live"]["strategy"], out["live"]["excess_vs_drift"]
        ok = st.get("ann_return", -1) > 0 and ex.get("ann_return", -1) > 0 and st.get("alpha_md_ann", -1) > 0 and st.get("first_half", -1) > 0 and st.get("second_half", -1) > 0
        verdict = "evidence_of_edge" if ok else "no_evidence_of_edge"
    out["status"], out["reached_reviews"] = verdict, reached
    out["n_targets_active"] = int(sum(1 for t in today))
    daily = pd.DataFrame({"strategy": s, "hold_same": h, "excess_vs_drift": x, "spy": spy}).round(6)
    daily.index.name = "date"
    return out, daily


def payload():
    out, daily = compute()
    daily.to_csv(DAILY)
    out["registry"] = REGISTRY
    out["review_points"] = REVIEWS
    out["backtest"] = json.load(open(BACKTEST)) if os.path.exists(BACKTEST) else {}
    return out
