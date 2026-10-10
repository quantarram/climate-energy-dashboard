"""Wind and solar potential from weather, and the learned map to regional generation."""
import numpy as np
import pandas as pd

# Generic utility-scale turbine curve on 100 m wind: cubic ramp 3 -> 12 m/s, flat to 25 m/s, then cut out.
CUT_IN, RATED, CUT_OUT = 3.0, 12.0, 25.0


def wind_cf(v):
    v = np.asarray(v, float)
    cf = np.clip((v - CUT_IN) / (RATED - CUT_IN), 0.0, 1.0) ** 3
    return np.where(v >= CUT_OUT, 0.0, cf)


# Wind: a learned power curve. The generic cubic above reads far too stiff against real output (daily error
# ~30% of mean output even with observed weather); a piecewise-linear "hat" basis in wind speed, with
# non-negative learned weights per site, brings that to ~8-17% for most regions on the 2026 holdout.
KNOTS = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0]


def hat_basis(v):
    """(n, len(KNOTS)) piecewise-linear hat functions of wind speed; they sum to 1 inside the knot range."""
    v = np.asarray(v, float)
    cols = []
    for i, c in enumerate(KNOTS):
        lo = KNOTS[i - 1] if i > 0 else None
        hi = KNOTS[i + 1] if i < len(KNOTS) - 1 else None
        if lo is None:
            x = np.where(v <= c, 1.0, np.where(v < hi, (hi - v) / (hi - c), 0.0))
        elif hi is None:
            x = np.where(v >= c, 1.0, np.where(v > lo, (v - lo) / (c - lo), 0.0))
        else:
            x = np.where((v > lo) & (v <= c), (v - lo) / (c - lo), np.where((v > c) & (v < hi), (hi - v) / (hi - c), 0.0))
        cols.append(x)
    return np.column_stack(cols)


def driver_matrix(values, kind):
    """Hourly drivers -> (n, k) feature matrix: wind speed through the hat basis, or solar irradiance (kW/m2)."""
    if kind == "wind":
        return hat_basis(values)
    return (np.asarray(values, float) / 1000.0)[:, None]


def n_features(kind):
    return len(KNOTS) if kind == "wind" else 1


def daily_features(hourly, kind):
    """Local-civil-day mean of each hourly driver feature, as a DataFrame (days x features)."""
    vals = hourly["wind100"].values if kind == "wind" else hourly["ghi"].values
    m = driver_matrix(vals, kind)
    df = pd.DataFrame(m, index=hourly.index)
    g = df.groupby(df.index.date)
    d = g.mean()[g.count().iloc[:, 0] >= 23]
    d.index = pd.to_datetime(d.index)
    return d


def nnls(A, y, iters=3000):
    """Non-negative least squares by projected gradient (small problems; avoids a SciPy dependency)."""
    A, y = np.asarray(A, float), np.asarray(y, float)
    L = np.linalg.norm(A, 2) ** 2 + 1e-12
    w = np.full(A.shape[1], max(y.mean(), 1e-9) / max(A.mean() * A.shape[1], 1e-9))
    for _ in range(iters):
        w = np.maximum(w - (A.T @ (A @ w - y)) / L, 0.0)
    return w


def fit_with_growth(dates, X, y, t0, grid=np.linspace(0.0, 0.6, 31)):
    """y_d ~ (1 + g*(years since t0)) * sum_i w_i x_i,d  with w >= 0 ; g chosen on the training sample."""
    yrs = ((pd.DatetimeIndex(dates) - pd.Timestamp(t0)).days / 365.25).values
    best = None
    for g in grid:
        A = X * (1 + g * yrs)[:, None]
        w = nnls(A, y)
        sse = float(((A @ w - y) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, g, w)
    return {"g": float(best[1]), "w": best[2], "t0": t0}


def generate(model, dates, X):
    yrs = ((pd.DatetimeIndex(dates) - pd.Timestamp(model["t0"])).days / 365.25).values
    return (X @ np.asarray(model["w"])) * (1 + model["g"] * yrs)
