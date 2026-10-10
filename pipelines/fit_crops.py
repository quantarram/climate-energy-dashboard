"""
One-off fit of weather -> weekly change in NASS crop condition (good + excellent %), corn and soybeans.

History: ERA5 2015 onward at each state's points, NASS weekly condition 2015-2025 for training (weeks 22-38), held out
on 2026. Weekly drivers (Mon-Sun): heat-stress degree days above 30 C, hot days (>35 C), afternoon VPD, rainfall.
Pooled across states, per crop, ridge regression of the week-on-week change in good+excellent on the drivers
(standardised) plus a seasonal term. Baselines on the holdout: no change, and the mean change by week of year.
Stores coefficients, weekly-driver normals (by ISO week) and holdout scores.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from weatherdash import crops, truth  # noqa: E402

OUT = os.path.join(ROOT, "data", "crops_model.json")
NASS = os.path.join(ROOT, "data", "nass_condition.csv")
HIST_START, TRAIN_END = "2015-01-01", 2025
RIDGE = 20.0


def state_weekly_history(end):
    out = {}
    for st, (tz, pts) in crops.CROP_STATES.items():
        pdaily = []
        for lat, lon in pts:
            print("ERA5", st, lat, lon, flush=True)
            h = truth.point_hourly(lat, lon, tz, HIST_START, end, cache_dir=os.path.join(ROOT, ".cache", "era5"))
            pdaily.append(crops.daily_from_hourly(h, tz))
        out[st] = crops.weekly(crops.state_daily(pdaily))
    return out


def design(df, feats):
    X = df[feats].values.astype(float)
    return X


def ridge_fit(X, y, alpha):
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
    Z = (X - mu) / sd
    A = np.column_stack([np.ones(len(Z)), Z])
    reg = alpha * np.eye(A.shape[1]); reg[0, 0] = 0.0
    beta = np.linalg.solve(A.T @ A + reg, A.T @ y)
    return beta, mu, sd


def predict(beta, mu, sd, X):
    Z = (X - mu) / sd
    return beta[0] + Z @ beta[1:]


def main():
    end = (pd.Timestamp.today().normalize() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    wk = state_weekly_history(end)
    nass = pd.read_csv(NASS)
    nass["week_ending"] = pd.to_datetime(nass["week_ending"])
    out = {"train_through": TRAIN_END, "features": crops.FEATURES + ["season"], "models": {}, "normals": {}}
    # weekly driver normals by ISO week (2015-2025), per state
    for st, w in wk.items():
        tr = w[w.index.year <= TRAIN_END]
        iso = tr.index.isocalendar().week.astype(int)
        out["normals"][st] = {f: {int(k): round(float(v), 3) for k, v in tr[f].groupby(iso.values).mean().items()}
                              for f in crops.FEATURES}
    for crop in crops.CROPS:
        n = nass[(nass.commodity == crop) & (nass.state.isin(crops.CROP_STATES))].copy()
        n["ge"] = n["good"] + n["excellent"]
        rows = []
        for st, g in n.groupby("state"):
            g = g.sort_values("week_ending").set_index("week_ending")["ge"]
            d = g.diff()[g.index.to_series().diff().dt.days == 7]
            df = pd.DataFrame({"dge": d}).join(wk[st], how="inner").dropna()
            rows.append(df)
        # ten-state average per week: state-level weekly changes are mostly survey noise, the average carries the signal
        D = pd.concat(rows)
        cnt = D.groupby(D.index)["dge"].count()
        A = D.groupby(D.index).mean()[crops.FEATURES + ["dge"]]
        A = A[cnt.reindex(A.index) >= 8]
        A["week"] = A.index.isocalendar().week.astype(int).values
        A["year"] = A.index.year
        A = A[(A.week >= crops.SEASON_WEEKS[0]) & (A.week <= crops.SEASON_WEEKS[1])].copy()
        A["season"] = (A["week"] - 30) / 8.0
        feats = crops.FEATURES + ["season"]
        # leave-one-year-out over every season 2015-2026
        pe, be, ze, pp, oo = [], [], [], [], []
        for y in sorted(A.year.unique()):
            tr, te = A[A.year != y], A[A.year == y]
            b_, m_, s_ = ridge_fit(tr[feats].values, tr["dge"].values, RIDGE)
            p = predict(b_, m_, s_, te[feats].values)
            cl = te["week"].map(tr.groupby("week")["dge"].mean()).values
            pe.append(np.abs(p - te["dge"].values)); be.append(np.abs(cl - te["dge"].values)); ze.append(np.abs(te["dge"].values))
            pp.append(p); oo.append(te["dge"].values)
        pe, be, ze = map(np.concatenate, (pe, be, ze))
        corr = float(np.corrcoef(np.concatenate(pp), np.concatenate(oo))[0, 1])
        # final model: all years through TRAIN_END; 2026 held out and scored separately
        tr, te = A[A.year <= TRAIN_END], A[A.year > TRAIN_END]
        beta, mu, sd = ridge_fit(tr[feats].values, tr["dge"].values, RIDGE)
        full_b, full_mu, full_sd = beta, mu, sd
        clim = tr.groupby("week")["dge"].mean()
        h26 = {}
        if len(te):
            p26 = predict(beta, mu, sd, te[feats].values)
            h26 = {"n": int(len(te)), "mae_model": round(float(np.mean(np.abs(p26 - te["dge"].values))), 3),
                   "mae_clim": round(float(np.mean(np.abs(te["week"].map(clim).values - te["dge"].values))), 3),
                   "mae_zero": round(float(np.mean(np.abs(te["dge"].values))), 3)}
        out["models"][crop] = {"beta": [float(b) for b in full_b], "mu": [float(m) for m in full_mu], "sd": [float(s) for s in full_sd],
                               "clim_dge_by_week": {int(k): round(float(v), 3) for k, v in clim.items()},
                               "n_weeks": int(len(A)), "seasons": f"{int(A.year.min())}-{int(A.year.max())}",
                               "loyo_mae_model": round(float(pe.mean()), 3), "loyo_mae_clim": round(float(be.mean()), 3),
                               "loyo_mae_zero": round(float(ze.mean()), 3), "loyo_corr": round(corr, 3), "holdout_2026": h26,
                               "coef_std": {f: round(float(b), 3) for f, b in zip(feats, full_b[1:])}}
        print(f"{crop}: weeks {len(A)}  LOYO MAE(pp/week) model {pe.mean():.3f} clim {be.mean():.3f} zero {ze.mean():.3f} corr {corr:.2f}  2026 {h26}  coefs {out['models'][crop]['coef_std']}", flush=True)
    json.dump(out, open(OUT, "w"))
    print("saved", OUT)


if __name__ == "__main__":
    main()
