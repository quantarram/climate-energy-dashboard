"""One-off: derive the gas-burn and storage forecast ledgers for every issue date already in the demand and wind/solar ledgers, and score what has matured.
  python pipelines/backfill_exposure.py"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from weatherdash import exposure, ledger, prices  # noqa: E402

model = exposure.load_model()
dem, ren = ledger.load(), ledger.rload()
dem["issue_date"], ren["issue_date"] = dem["issue_date"].astype(str), ren["issue_date"].astype(str)
log, failed = prices.update(["NG=F", "UNG", "XLU", "VST", "NRG", "CEG", "ICLN", "SPY"], "1y")
print("prices", len(log), "failed", failed)
pw = prices.wide(log)
print("burn rows appended:", exposure.burn_append(exposure.burn_rows(dem, ren, model, pw), "backfill"))
chg = exposure.storage_series()
print("storage rows appended:", exposure.storage_append(exposure.storage_rows(dem, model, chg), "backfill"))
print("burn scored:", exposure.burn_score(), " storage scored:", exposure.storage_score(chg))
print(exposure.burn_stats()["total_overall"], exposure.storage_stats()["by_region"])
