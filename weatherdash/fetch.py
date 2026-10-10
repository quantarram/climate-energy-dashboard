"""
Fetching forecast fields straight into memory -- nothing raw is ever written to disk.

ECMWF open data (IFS 0.25 deg, CC-BY-4.0) publishes, next to every step file, a small
`.index` file listing each GRIB message with its byte offset and length. We read the index,
pick the few fields we need, and fetch only those byte ranges. A full step file is ~140 MB;
the handful of surface fields used here is ~10 MB.

Three mirrors host the same files; requests retry with backoff (S3 answers "SlowDown" under load)
and fall back across mirrors.
"""
import json
import time

import requests

ECMWF_MIRRORS = [  # Google first: the AWS bucket often answers "SlowDown" (503) under load
    "https://storage.googleapis.com/ecmwf-open-data",
    "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com",
    "https://data.ecmwf.int/forecasts",
]
TIMEOUT = 60
_session = requests.Session()


def _get(urls, headers=None, tries=6):
    """GET the first URL that works, retrying with backoff; returns bytes."""
    last = None
    for attempt in range(tries):
        for url in urls:
            try:
                r = _session.get(url, headers=headers, timeout=TIMEOUT)
                if r.status_code in (200, 206):
                    return r.content
                last = f"{r.status_code} {url}"
            except requests.RequestException as e:
                last = f"{type(e).__name__} {url}"
        time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"fetch failed after {tries} rounds: {last}")


def ifs_paths(date, cycle, step, stream="oper", kind="fc"):
    base = f"{date}/{cycle:02d}z/ifs/0p25/{stream}/{date}{cycle:02d}0000-{step}h-{stream}-{kind}"
    return base + ".grib2", base + ".index"


def ifs_index(date, cycle, step):
    _, idx = ifs_paths(date, cycle, step)
    raw = _get([f"{m}/{idx}" for m in ECMWF_MIRRORS])
    return [json.loads(l) for l in raw.decode().splitlines() if l.strip()]


def ifs_fetch(date, cycle, step, want):
    """
    want: set of (levtype, param) tuples, e.g. {("sfc", "2t"), ("sol", "vsw")}.
    Returns the concatenated GRIB messages (bytes) for those fields at this step.
    """
    rows = [r for r in ifs_index(date, cycle, step) if (r["levtype"], r["param"]) in want]
    if not rows:
        raise RuntimeError(f"no requested fields in index for {date} {cycle:02d}z step {step}")
    rows.sort(key=lambda r: r["_offset"])
    grib, _ = ifs_paths(date, cycle, step)
    out = []
    for r in rows:
        hdr = {"Range": f"bytes={r['_offset']}-{r['_offset'] + r['_length'] - 1}"}
        out.append(_get([f"{m}/{grib}" for m in ECMWF_MIRRORS], headers=hdr))
    return b"".join(out)


def ifs_latest_cycle(now_utc, lag_hours=9):
    """Most recent 00z/12z cycle that should be fully published (IFS open data lands ~7.5h after cycle time)."""
    t = now_utc - __import__("datetime").timedelta(hours=lag_hours)
    cycle = 12 if t.hour >= 12 else 0
    return t.strftime("%Y%m%d"), cycle
