"""
The one daily pipeline (run after the ECMWF 00z open-data cycle is published, ~07:35 UTC).

  Stage 1, signals (needs no weather forecast, never blocked by a forecast outage): refresh the NOAA climate indices, extend the price calendar, log new entry events for the frozen climate
  signals, and write data/signals.json for the front page.
  Stage 2, archive (daily weather panels, still scored for the registered experiment):
  1. fetch the IFS 2 m temperature forecast for the pilot load centres (in memory, nothing raw is stored)
  2. regional temperature -> degree days -> demand forecast vs climatology
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
from weatherdash import decisions, exposure, fetch, forecast, ledger, prices, truth  # noqa: E402


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


def signals_stage():
    """Frozen climate signals. Every step is isolated: a failure keeps the last stored data and the page still builds."""
    from weatherdash import cpe_climate, signals_page
    try:
        cpe_climate.run_all()
    except Exception as e:  # noqa: BLE001
        print(f"climate ledger step failed: {type(e).__name__}: {str(e)[:150]}")
    try:
        payload = signals_page.assemble()
        json.dump(payload, open(os.path.join(ROOT, "data", "signals.json"), "w"), default=float)
        print(f"signals payload written: {sum(len(b['watch']) for b in payload['cpe'])} watched conditions in {len(payload['cpe'])} frozen tables, {sum(1 for b in payload['cpe'] for w in b['watch'] if w['firing'])} firing")
    except Exception as e:  # noqa: BLE001
        print(f"signals payload failed (keeping the previous one): {type(e).__name__}: {str(e)[:150]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals-only", action="store_true", help="run stage 1 only")
    ap.add_argument("--no-signals", action="store_true", help="skip stage 1")
    ap.add_argument("--date")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--renewables-only", action="store_true", help="backfill the wind/solar ledger only")
    ap.add_argument("--crops-only", action="store_true", help="backfill the crop-stress ledger only")
    args = ap.parse_args()
    if not args.no_signals:
        signals_stage()
    if args.signals_only:
        return
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
    # physical-exposure ledgers (gas burn, storage) derive from the ledgers above; prices feed the gas-burn model and the live decision experiment
    try:
        pw_log, failed = prices.update(decisions.INSTRUMENTS + [decisions.CONTROL], "3mo")
        if failed:
            print("price fetch incomplete:", failed)
    except Exception as e:  # noqa: BLE001
        print(f"price log update failed: {type(e).__name__}: {str(e)[:100]}")
    pw = prices.wide() if os.path.exists(prices.LOG) else None
    chg = None
    try:
        n_new, chg = exposure.append_issue(pd.Timestamp(date).strftime("%Y-%m-%d"), pw, src)
        print(f"exposure ledgers: {n_new['burn']} new gas-burn rows, {n_new['storage']} new storage rows")
    except Exception as e:  # noqa: BLE001
        print(f"exposure ledgers skipped: {type(e).__name__}: {str(e)[:120]}")
    if args.backfill:
        return
    if not args.no_score:
        # Scoring needs the free Open-Meteo archive, which rate-limits shared CI addresses. It gets a fixed time budget and
        # a failure only defers scoring (rows stay pending and are retried next run); it never stops the forecast being
        # logged, the payload written or the dashboard published.
        truth.set_budget(600)
        for label, fn in (("temperature/demand rows", lambda: ledger.score(forecast.load_model())),
                          ("wind/solar rows", lambda: ledger.rscore(forecast.load_renewables())),
                          ("crop-stress outcomes", ledger.cscore)):
            try:
                print("scored", fn(), label)
            except Exception as e:  # noqa: BLE001
                print(f"scoring deferred for {label}: {type(e).__name__}: {str(e)[:120]}")
    try:
        print("scored", exposure.burn_score(), "gas-burn rows")
        if chg is not None:
            print("scored", exposure.storage_score(chg), "storage rows")
    except Exception as e:  # noqa: BLE001
        print(f"exposure scoring deferred: {type(e).__name__}: {str(e)[:120]}")
    expo = dec = None
    try:
        expo = exposure.payload(pd.Timestamp(date).strftime("%Y-%m-%d"), chg, pw)
    except Exception as e:  # noqa: BLE001
        print(f"exposure payload skipped: {type(e).__name__}: {str(e)[:120]}")
    try:
        sig = decisions.history_from_ledgers(ledger.load(), ledger.rload())
        decisions.save_signals(sig)
        dec = decisions.summarise(decisions.score(sig, pw)) if pw is not None else decisions.summarise(None)
    except Exception as e:  # noqa: BLE001
        print(f"decision experiment skipped: {type(e).__name__}: {str(e)[:120]}")
    renew_model = forecast.load_renewables()["models"]
    crop_model = forecast.load_crop_model()["models"]
    payload = {
        "generated_utc": now.strftime("%Y-%m-%d %H:%M"), "issue_date": df["issue_date"].iloc[0], "model": df["model"].iloc[0],
        "forecast": df.to_dict(orient="records"), "verification": ledger.stats(),
        "impact_model": {k: {x: v[x] for x in ("test_mape_model_obs_temp", "test_mape_climatology", "n_test")}
                         for k, v in forecast.load_model()["regions"].items()},
        "climatology": {"demand": forecast.load_model()["climatology"], "renewables": forecast.load_renewables()["climatology"],
                        "crops": forecast.load_crop_model()["climatology"]},
        "renewables": {
            "forecast": ledger.calibrated_forecast(rdf), "verification": ledger.rstats_calibrated(),
            "impact_model": {k: {x: v[x] for x in ("test_nmae_model_obs_weather", "test_nmae_climatology", "test_bias_pct", "n_test")}
                             for k, v in renew_model.items()}},
        "crops": {
            "forecast": json.loads(cdf.to_json(orient="records")), "verification": ledger.cstats(),
            "model": {k: {x: v[x] for x in ("loyo_mae_model", "loyo_mae_clim", "loyo_mae_zero", "loyo_corr", "n_weeks", "seasons",
                                            "holdout_2026", "coef_std")} for k, v in crop_model.items()}},
    }
    if expo:
        payload["exposure"] = expo
    if dec:
        payload["decisions"] = dec
    json.dump(payload, open(os.path.join(ROOT, "data", "latest.json"), "w"), default=float)
    print("wrote data/latest.json")


if __name__ == "__main__":
    main()
