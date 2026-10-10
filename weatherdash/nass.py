"""
USDA NASS weekly crop condition from the Quick Stats bulk file (no API key needed).

The crops file (~1.1 GB gzipped, rebuilt daily at qs.crops_YYYYMMDD.txt.gz) is streamed straight through a
decompressor and filtered to weekly CONDITION rows for corn, soybeans and wheat; nothing large is stored.
"""
import zlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

BASE = "https://www.nass.usda.gov/datasets"
COMMODITIES = {b"CORN", b"SOYBEANS", b"WHEAT"}
CATS = {"PCT VERY POOR": "vpoor", "PCT POOR": "poor", "PCT FAIR": "fair", "PCT GOOD": "good", "PCT EXCELLENT": "excellent"}
OUT_COLS = ["commodity", "class", "state", "year", "week_ending", "vpoor", "poor", "fair", "good", "excellent"]


def latest_file_url(now=None, back_days=5):
    now = now or datetime.now(timezone.utc)
    for b in range(back_days):
        url = f"{BASE}/qs.crops_{(now - timedelta(days=b)).strftime('%Y%m%d')}.txt.gz"
        try:
            if requests.head(url, timeout=30).status_code == 200:
                return url
        except requests.RequestException:
            pass
    raise RuntimeError("no recent qs.crops file found")


def stream_condition(url=None, min_year=2010):
    """Stream the bulk file and return a wide DataFrame of weekly condition percentages (state and national)."""
    url = url or latest_file_url()
    dec = zlib.decompressobj(31)
    rows, tail, header = [], b"", None
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1 << 22):
            data = tail + dec.decompress(chunk)
            parts = data.split(b"\n")
            tail = parts.pop()
            for line in parts:
                if header is None:
                    header = line.decode("latin1").rstrip("\r").split("\t")
                    ix = {k: header.index(k) for k in ("COMMODITY_DESC", "CLASS_DESC", "SHORT_DESC", "AGG_LEVEL_DESC", "STATE_ALPHA",
                                                       "YEAR", "FREQ_DESC", "WEEK_ENDING", "VALUE", "UNIT_DESC")}
                    continue
                if b"CONDITION, MEASURED" not in line:
                    continue
                f = line.decode("latin1").rstrip("\r\x00").split("\t")
                if len(f) < len(header) - 1 or f[ix["COMMODITY_DESC"]].encode() not in COMMODITIES:
                    continue
                if f[ix["FREQ_DESC"]] != "WEEKLY" or f[ix["AGG_LEVEL_DESC"]] not in ("STATE", "NATIONAL"):
                    continue
                if int(f[ix["YEAR"]]) < min_year or f[ix["UNIT_DESC"]] not in CATS:
                    continue
                v = f[ix["VALUE"]].strip().replace(",", "")
                if not v.replace(".", "").isdigit():
                    continue
                st = f[ix["STATE_ALPHA"]] or "US"
                rows.append((f[ix["COMMODITY_DESC"]], f[ix["CLASS_DESC"]], st, int(f[ix["YEAR"]]), f[ix["WEEK_ENDING"]],
                             CATS[f[ix["UNIT_DESC"]]], float(v)))
    df = pd.DataFrame(rows, columns=["commodity", "class", "state", "year", "week_ending", "cat", "value"])
    wide = df.pivot_table(index=["commodity", "class", "state", "year", "week_ending"], columns="cat", values="value", aggfunc="first").reset_index()
    wide.columns.name = None
    return wide.reindex(columns=OUT_COLS).sort_values(["commodity", "class", "state", "week_ending"])
