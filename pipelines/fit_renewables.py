"""
One-off fit of weather -> regional wind and solar generation, per balancing authority.

For each BA and resource: daily weather drivers (wind: capacity factor of a generic turbine curve at 100 m;
solar: surface irradiance) at candidate generation areas, ERA5 hourly 2015 onward; learned non-negative
site weights plus a linear capacity-growth term, fitted on 2023-2025 EIA-930 daily generation and held out
on 2026. Stores weights, the weather normal (day-of-year, 2015-2025) and holdout scores only.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from weatherdash import eia, regions, renewables, truth  # noqa: E402

OUT = os.path.join(ROOT, "data", "renewables_model.json")
TRAIN_START, TRAIN_END, CLIM_START = "2023-01-01", "2025-12-31", "2015-01-01"


def main():
    end = (pd.Timestamp.today().normalize() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    bas = list(regions.SITES)
    gen = pd.concat([eia.daily_generation(n, bas) for n in eia.six_month_files(range(2023, 2027))])
    feats = {}  # (ba, res, site) -> daily feature series
    for ba, res, site, lat, lon in regions.site_list():
        tz = regions.REGIONS[ba]["tz"]
        print("ERA5", ba, res, site, flush=True)
        h = truth.site_hourly(lat, lon, tz, CLIM_START, end, cache_dir=os.path.join(ROOT, '.cache', 'era5'))
        feats[(ba, res, site)] = renewables.daily_features(h, res)
        time.sleep(0.3)
    out = {"trained": [TRAIN_START, TRAIN_END], "clim": [CLIM_START, TRAIN_END], "models": {}}
    for ba in bas:
        for res in regions.SITES[ba]:
            sites = list(regions.SITES[ba][res])
            F = pd.concat([feats[(ba, res, s)].add_prefix(f'{s}_') for s in sites], axis=1).dropna()
            y = gen[(gen["ba"] == ba) & (gen["resource"] == res)].set_index("date")["gen_mwh"].sort_index()
            y = y[~y.index.duplicated()]
            idx = F.index.intersection(y.index)
            tr = (idx >= pd.Timestamp(TRAIN_START)) & (idx <= pd.Timestamp(TRAIN_END))
            te = idx > pd.Timestamp(TRAIN_END)
            grid = np.linspace(0.0, 0.6, 31)  # growth is not extrapolated far; the daily level calibration absorbs the rest
            m = renewables.fit_with_growth(idx[tr], F.loc[idx[tr]].values, y.loc[idx[tr]].values, TRAIN_START, grid=grid)
            pred = renewables.generate(m, idx[te], F.loc[idx[te]].values)
            # weather normal: mean daily driver by day of year over 2015-2025, smoothed, mapped through the learned weights
            clim = F[(F.index >= pd.Timestamp(CLIM_START)) & (F.index <= pd.Timestamp(TRAIN_END))]
            doy = clim.groupby(clim.index.dayofyear).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
            sm = pd.concat([doy.iloc[-7:], doy, doy.iloc[:7]]).rolling(15, center=True).mean().iloc[7:-7]
            normal_feat = (sm.values @ m["w"])
            base = renewables.generate(m, idx[te], np.array([sm.iloc[min(d.dayofyear, 366) - 1].values for d in idx[te]]))
            actual = y.loc[idx[te]].values
            ape = lambda p: float(np.mean(np.abs(p - actual)) / np.mean(actual) * 100)  # NMAE: % of mean daily output
            wsum = float(m["w"].sum()) or 1.0
            k = renewables.n_features(res)
            out["models"][f"{ba}|{res}"] = {
                "sites": sites, "w": [float(x) for x in m["w"]], "g": m["g"], "t0": m["t0"],
                "normal_feature_by_doy": [round(float(v), 6) for v in normal_feat],
                "n_train": int(tr.sum()), "n_test": int(te.sum()),
                "test_nmae_model_obs_weather": round(ape(pred), 2), "test_nmae_normal_weather": round(ape(base), 2),
                "test_bias_pct": round(float((pred.sum() / actual.sum() - 1) * 100), 2),
                "mean_daily_gen_mwh_2026": round(float(actual.mean()), 0),
                "site_share": {s: round(float(sum(m["w"][i * k:(i + 1) * k]) / wsum), 3) for i, s in enumerate(sites)},
                "n_features_per_site": k,
            }
            print(f"{ba} {res}: g={m['g']:.2f}  holdout NMAE model(obs weather) {ape(pred):.1f}%  normal {ape(base):.1f}%  "
                  f"bias {(pred.sum() / actual.sum() - 1) * 100:+.1f}%", flush=True)
    json.dump(out, open(OUT, "w"))
    print("saved", OUT)


if __name__ == "__main__":
    main()
