"""Decode GRIB messages held in memory and sample them at points (regular lat/lon grids)."""
import numpy as np
import eccodes


def messages(buf):
    """Yield open eccodes handles for each GRIB message in a bytes buffer."""
    pos = 0
    while pos < len(buf):
        start = buf.find(b"GRIB", pos)
        if start < 0:
            return
        # total length of the message is in the indicator section (bytes 8-15 for GRIB2)
        total = int.from_bytes(buf[start + 8:start + 16], "big")
        h = eccodes.codes_new_from_message(buf[start:start + total])
        try:
            yield h
        finally:
            eccodes.codes_release(h)
        pos = start + total


def grid_of(h):
    ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
    lat0 = eccodes.codes_get(h, "latitudeOfFirstGridPointInDegrees")
    lon0 = eccodes.codes_get(h, "longitudeOfFirstGridPointInDegrees")
    di = eccodes.codes_get(h, "iDirectionIncrementInDegrees")
    dj = eccodes.codes_get(h, "jDirectionIncrementInDegrees")
    south_to_north = bool(eccodes.codes_get(h, "jScansPositively"))
    return ni, nj, lat0, lon0, di, dj, south_to_north


def sample(h, lats, lons):
    """Bilinear sample of one message at points; returns (values array, meta dict)."""
    ni, nj, lat0, lon0, di, dj, s2n = grid_of(h)
    v = eccodes.codes_get_values(h).reshape(nj, ni)
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    jf = (lats - lat0) / (dj if s2n else -dj)
    lon_rel = (lons - lon0) % 360.0
    i_f = lon_rel / di
    j0 = np.clip(np.floor(jf).astype(int), 0, nj - 2)
    i0 = np.floor(i_f).astype(int) % ni
    i1 = (i0 + 1) % ni
    wj, wi = jf - j0, i_f - np.floor(i_f)
    top = v[j0, i0] * (1 - wi) + v[j0, i1] * wi
    bot = v[j0 + 1, i0] * (1 - wi) + v[j0 + 1, i1] * wi
    out = top * (1 - wj) + bot * wj
    meta = {k: eccodes.codes_get(h, k) for k in ("shortName", "level", "stepRange", "dataDate", "dataTime")}
    return out, meta
