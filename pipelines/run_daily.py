"""
Daily run (after the ECMWF 00z open-data cycle is published, ~07:35 UTC):
  1. fetch the IFS 2 m temperature forecast for the pilot load centres (in memory, nothing raw is stored)
  2. regional temperature -> degree days -> demand forecast vs normal
  3. append to the forecast ledger, score whatever has matured, write the dashboard payload

  python pipelines/run_daily.py               # latest 00z cycle
  python pipelines/run_daily.py --date 20260915 --backfill   # ledger rows only, for a past cycle
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from weatherdash import fetch, forecast, ledger  # noqa: E402


def latest_available_date(now):
    """00z cycle date whose files are published: try today, then yesterday."""
    for back in (0, 1, 2):
        d = (now - timedelta(days=back)).strftime("%Y%m%d")
        try:
            fetch.ifs_index(d, 0, 144)
            return d
        except RuntimeError:
            continue
    raise RuntimeError("no recent IFS 00z cycle found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--renewables-only", action="store_true", help="backfill the wind/solar ledger only")
    ap.add_argument("--crops-only", action="store_true", help="backfill the crop-stress ledger only")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    date = args.date or latest_available_date(now)
    src = "backfill" if args.backfill else "live"
    only = args.renewables_only or args.crops_only
    if not only:
        df = forecast.run(date, 0, workers=args.workers)
        n = ledger.append(df, source=src)
        print(f"IFS {date} 00z: {len(df)} temperature/demand rows, {n} new in ledger")
    if not args.crops_only:
        rdf = forecast.run_renewables(date, 0, workers=args.workers)
        rn = ledger.rappend(rdf, source=src)
        print(f"IFS {date} 00z: {len(rdf)} wind/solar rows, {rn} new in ledger")
    if not args.renewables_only:
        cdf = forecast.run_crops(date, 0, workers=args.workers)
        cn = ledger.cappend(cdf, source=src)
        print(f"IFS {date} 00z: {len(cdf)} crop-stress rows, {cn} new in ledger")
    if args.backfill:
        return
    if not args.no_score:
        print("scored", ledger.score(forecast.load_model()), "temperature/demand rows")
        print("scored", ledger.rscore(forecast.load_renewables()), "wind/solar rows")
        print("filled", ledger.cscore(), "crop-stress outcomes")
    renew_model = forecast.load_renewables()["models"]
    crop_model = forecast.load_crop_model()["models"]
    payload = {
        "generated_utc": now.strftime("%Y-%m-%d %H:%M"), "issue_date": df["issue_date"].iloc[0], "model": df["model"].iloc[0],
        "forecast": df.to_dict(orient="records"), "verification": ledger.stats(),
        "impact_model": {k: {x: v[x] for x in ("test_mape_model_obs_temp", "test_mape_climatology", "n_test")}
                         for k, v in forecast.load_model()["regions"].items()},
        "renewables": {
            "forecast": ledger.calibrated_forecast(rdf), "verification": ledger.rstats_calibrated(),
            "impact_model": {k: {x: v[x] for x in ("test_nmae_model_obs_weather", "test_nmae_normal_weather", "test_bias_pct", "n_test")}
                             for k, v in renew_model.items()}},
        "crops": {
            "forecast": json.loads(cdf.to_json(orient="records")), "verification": ledger.cstats(),
            "model": {k: {x: v[x] for x in ("loyo_mae_model", "loyo_mae_clim", "loyo_mae_zero", "loyo_corr", "n_weeks", "seasons",
                                            "holdout_2026", "coef_std")} for k, v in crop_model.items()}},
    }
    json.dump(payload, open(os.path.join(ROOT, "data", "latest.json"), "w"))
    print("wrote data/latest.json")


if __name__ == "__main__":
    main()
