"""
One-off fit of the physical-exposure models:

  1. Gas burn: daily gas-fired generation of each balancing authority (EIA-930, 2019-2025) from its net load (demand - wind - solar), the gas price, day of week, season and trend.
  2. Storage: weekly change in EIA regional working gas (East, Midwest, Pacific) from weekly heating and cooling degree-days of the six regions' temperatures (ERA5 history cached
     by the demand fit), season harmonics; refit on all weeks; with the five-year norm for the same ISO week.
  3. Power price sensitivities: percent change of the next-day peak price per +10 degree-days at the hubs EIA publishes (ICE data, 2017-2025), copied from the research results.

  python pipelines/fit_exposure.py [path/to/eia930_daily.parquet] [path/to/NG.zip] [path/to/universe_prices.parquet] [path/to/power_price_results.json]
Writes data/exposure_model.json.
"""
import json
import os
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pipelines"))
from weatherdash import exposure, regions  # noqa: E402
from weatherdash.calendar_utils import doy366  # noqa: E402

RES = os.path.join(os.path.dirname(ROOT), "quant-regime-research", "notebooks", "weather_finance")
A = sys.argv[1:]
EIA930 = A[0] if len(A) > 0 else os.path.join(RES, "data", "eia930_daily.parquet")
NGZIP = A[1] if len(A) > 1 else os.path.join(RES, "data", "eia", "NG.zip")
PRICES = A[2] if len(A) > 2 else os.path.join(RES, "data", "universe_all.parquet")
POWER = A[3] if len(A) > 3 else os.path.join(RES, "power_price_results.json")
OUT = os.path.join(ROOT, "data", "exposure_model.json")
TEST_YEARS = range(2022, 2026)


def fit_burn():
    d = pd.read_parquet(EIA930)
    d["date"] = pd.to_datetime(d["date"])
    px = pd.read_parquet(PRICES)["NG=F"].dropna()
    out = {}
    for ba in regions.REGIONS:
        g = d[(d.ba == ba) & (d.date >= "2019-01-01") & (d.date <= "2025-12-31")].copy()
        g = g[(g.hours >= 23) & (g.hours <= 25) & (g.gas_hours >= 23)]
        for c in ("wind", "solar"):
            g[c] = g[c].fillna(0.0)
        g = g.set_index("date")
        g["nl"] = g.demand - g.wind - g.solar
        g["lg"] = np.log(px.reindex(g.index, method="ffill"))
        g = g.dropna(subset=["nl", "gas", "lg"])
        g = g[g.gas > 0]
        y = g.gas.values / 1000.0  # GWh
        X = exposure.burn_design(g.index, g.nl.values / 1000.0, g.lg.values)
        # out-of-sample: expanding window, test years
        err, errc, act = [], [], []
        for Y in TEST_YEARS:
            tr, te = g.index.year < Y, g.index.year == Y
            if tr.sum() < 300 or te.sum() < 100:
                continue
            b = np.linalg.lstsq(X[tr], y[tr], rcond=None)[0]
            clim = pd.Series(y[tr], index=g.index[tr]).groupby(doy366(g.index[tr])).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
            clim = clim.rolling(15, center=True, min_periods=1).mean()
            p = X[te] @ b
            pc = clim.loc[doy366(g.index[te])].values
            err.append(np.abs(p - y[te]) / y[te] * 100)
            errc.append(np.abs(pc - y[te]) / y[te] * 100)
            act.append(y[te])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        clim = pd.Series(y, index=g.index).groupby(doy366(g.index)).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
        clim = clim.rolling(15, center=True, min_periods=1).mean()
        out[ba] = {"beta": [float(b) for b in beta], "clim_gwh_by_doy": [round(float(v), 2) for v in clim.values],
                   "test_mape_model_obs_netload": round(float(np.concatenate(err).mean()), 2), "test_mape_climatology": round(float(np.concatenate(errc).mean()), 2),
                   "n_test": int(sum(len(a) for a in act)), "mean_gwh": round(float(y.mean()), 1), "n_fit": int(len(y))}
        print(f"burn {ba}: n {len(y)}  mean {y.mean():.0f} GWh  holdout MAPE with observed net load {out[ba]['test_mape_model_obs_netload']}%  climatology {out[ba]['test_mape_climatology']}%", flush=True)
    return out


def storage_series():
    z = zipfile.ZipFile(NGZIP)
    got = {}
    with z.open("NG.txt") as fh:
        for line in fh:
            d = json.loads(line)
            sid = d.get("series_id", "")
            if sid.startswith("NG.NW2_EPG0_SWO_R") and sid.endswith("_BCF.W"):
                got[sid.split("_")[3]] = pd.Series({pd.Timestamp(a): float(b) for a, b in d["data"]}).sort_index()
    return got


def weekly_dd(temp_c):
    """Weekly (Saturday-Friday, labelled by the Friday) HDD and CDD sums of a daily mean temperature series in deg C."""
    f = temp_c * 9 / 5 + 32
    h, c = np.maximum(65 - f, 0), np.maximum(f - 65, 0)
    out = {}
    for F in pd.date_range(f.index.min() + pd.Timedelta(days=6), f.index.max(), freq="W-FRI"):
        w = f.loc[F - pd.Timedelta(days=6):F]
        if len(w) == 7:
            out[F] = (float(h.loc[w.index].sum()), float(c.loc[w.index].sum()))
    return pd.DataFrame(out, index=["H", "C"]).T


def fit_storage():
    import fit_demand_model as fdm
    temps = {r: fdm.region_temp_history(r, "2025-12-31") for r in regions.REGIONS}
    W = {r: weekly_dd(t) for r, t in temps.items()}
    ser = storage_series()
    out = {}
    for code, label in exposure.STORAGE_REGIONS.items():
        s = ser[code]
        chg = s.diff().dropna()
        D = pd.DataFrame({"chg": chg})
        for r in regions.REGIONS:
            D[f"H_{r}"] = W[r]["H"]
            D[f"C_{r}"] = W[r]["C"]
        D = D.dropna()
        D["doy"] = doy366(D.index)
        D["year"] = D.index.year
        X = exposure.storage_design(D)
        y = D.chg.values
        # out of sample (expanding, test 2016-2025) and five-year norm baseline
        norm = exposure.five_year_norm(chg)
        err, errn = [], []
        for Y in range(2016, 2026):
            tr, te = (D.year < Y).values, (D.year == Y).values
            if tr.sum() < 150:
                continue
            b = np.linalg.lstsq(X[tr], y[tr], rcond=1e-6)[0]
            err.append(y[te] - X[te] @ b)
            nn = norm.reindex(D.index[te]).values
            errn.append(y[te] - nn)
        e, en = np.concatenate(err), np.concatenate([x for x in errn])
        m = ~np.isnan(en)
        beta = np.linalg.lstsq(X, y, rcond=1e-6)[0]
        out[code] = {"label": label, "beta": [float(b) for b in beta], "test_rmse_model": round(float(np.sqrt((e ** 2).mean())), 2),
                     "test_rmse_norm": round(float(np.sqrt((en[m] ** 2).mean())), 2), "test_mae_model": round(float(np.abs(e).mean()), 2),
                     "test_mae_norm": round(float(np.abs(en[m]).mean()), 2), "n_test": int(len(e)), "n_fit": int(len(y))}
        print(f"storage {label}: weeks {len(y)}  OOS RMSE model {out[code]['test_rmse_model']} Bcf  norm {out[code]['test_rmse_norm']}", flush=True)
    return out


def main():
    model = {"burn": fit_burn(), "storage": fit_storage()}
    if os.path.exists(POWER):
        model["power_price"] = json.load(open(POWER))
    json.dump(model, open(OUT, "w"))
    print("saved", OUT)


if __name__ == "__main__":
    main()
