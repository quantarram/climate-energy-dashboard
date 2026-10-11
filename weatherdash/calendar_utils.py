"""Calendar helpers shared by the climatology builders and the forecast code."""
import numpy as np
import pandas as pd


def doy366(index):
    """Day of year on a fixed 366-day calendar: in non-leap years, days after Feb 28 are shifted by one so that a given
    calendar date always maps to the same bucket (Mar 1 is 61 in every year; Feb 29 is 60 and exists only in leap years)."""
    idx = pd.DatetimeIndex(index)
    d = idx.dayofyear.values
    return np.where((~idx.is_leap_year) & (idx.month > 2), d + 1, d)


def us_federal_holidays(dates):
    """1.0 on US federal holidays (as observed, so a Saturday holiday counts on the Friday and a Sunday one on the Monday)."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    idx = pd.DatetimeIndex(dates)
    hol = USFederalHolidayCalendar().holidays(start=idx.min() - pd.Timedelta(days=3), end=idx.max() + pd.Timedelta(days=3))
    return idx.normalize().isin(hol).astype(float)
