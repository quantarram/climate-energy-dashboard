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
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    date = args.date or latest_available_date(now)
    df = forecast.run(date, 0, workers=args.workers)
    n = ledger.append(df, source="backfill" if args.backfill else "live")
    print(f"IFS {date} 00z: {len(df)} forecast rows, {n} new in ledger")
    if args.backfill:
        return
    if not args.no_score:
        print("scored", ledger.score(forecast.load_model()), "rows")
    payload = {"generated_utc": now.strftime("%Y-%m-%d %H:%M"), "issue_date": df["issue_date"].iloc[0],
               "model": df["model"].iloc[0], "forecast": df.to_dict(orient="records"),
               "verification": ledger.stats(), "impact_model": {
                   k: {x: v[x] for x in ("test_mape_model_obs_temp", "test_mape_climatology", "n_test")}
                   for k, v in forecast.load_model()["regions"].items()}}
    json.dump(payload, open(os.path.join(ROOT, "data", "latest.json"), "w"))
    print("wrote data/latest.json")


if __name__ == "__main__":
    main()
