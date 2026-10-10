#!/bin/bash
cd "$(dirname "$0")/.."
d="$1"; end="$2"
while [ "$d" -le "$end" ]; do
  .venv/bin/python pipelines/run_daily.py --date "$d" --backfill --crops-only --workers 16 || echo "FAILED $d"
  d=$(date -j -v+1d -f %Y%m%d "$d" +%Y%m%d)
done
