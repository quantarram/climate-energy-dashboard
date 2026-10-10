"""Temperature -> daily electricity demand model, one per balancing authority."""
import numpy as np
import pandas as pd

BASE_F = 65.0
DOW = [0, 1, 2, 3, 4, 5]  # Monday..Saturday dummies; Sunday is the baseline


def to_f(c):
    return np.asarray(c, float) * 9.0 / 5.0 + 32.0


def degree_days(t_c):
    f = to_f(t_c)
    return np.maximum(BASE_F - f, 0.0), np.maximum(f - BASE_F, 0.0)


def design(dates, t_c, origin="2023-01-01"):
    """Feature matrix for dates (DatetimeIndex) and daily mean temps (deg C)."""
    dates = pd.DatetimeIndex(dates)
    hdd, cdd = degree_days(t_c)
    X = [np.ones(len(dates)), hdd / 10, cdd / 10, (hdd / 10) ** 2, (cdd / 10) ** 2]
    for d in DOW:
        X.append((dates.dayofweek == d).astype(float))
    X.append(((dates - pd.Timestamp(origin)).days / 365.25).values)
    return np.column_stack(X)


def fit(dates, t_c, y):
    X = design(dates, t_c)
    beta, *_ = np.linalg.lstsq(X, np.asarray(y, float), rcond=None)
    return beta


def predict(beta, dates, t_c):
    return design(dates, t_c) @ np.asarray(beta, float)
