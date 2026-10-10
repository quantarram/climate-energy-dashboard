#!/bin/bash
# Backfill the ledger with archived IFS 00z forecasts (open-data archive keeps them), one cycle per day.
# usage: pipelines/backfill.sh 20260601 20261008
cd "$(dirname "$0")/.."
d="$1"; end="$2"
while [ "$d" -le "$end" ]; do
  .venv/bin/python pipelines/run_daily.py --date "$d" --backfill --workers 16 $3 || echo "FAILED $d"
  d=$(date -j -v+1d -f %Y%m%d "$d" +%Y%m%d)
done
