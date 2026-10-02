#!/usr/bin/env python3
"""
Tinga Lens - drought layer.

Turns CHIRPS monthly rainfall into a district-level drought indicator for Ghana.

Indicator: rainfall total over the latest 3 months, compared with the same
3 months in every year of the 1991-2020 baseline. For each district we report
  - rain_mm      : district-average 3-month rainfall
  - normal_mm    : 1991-2020 average for the same 3 months
  - pct_normal   : rain_mm / normal_mm * 100
  - percentile   : where this year ranks among the baseline years (0 = driest)
  - category     : very_dry / dry / normal / wet / very_wet / dry_season

Run:
  python scripts/drought.py          # real data (downloads CHIRPS, needs internet)
  python scripts/drought.py --demo   # made-up data, only for previewing the site

Data: CHIRPS, Climate Hazards Center, UC Santa Barbara (public domain).
Boundaries: geoBoundaries GHA ADM2 (CC BY 4.0).
"""
import argparse
import datetime as dt
import gzip
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds
from rasterio.windows import transform as window_transform

ROOT = Path(__file__).resolve().parent.parent
DISTRICTS = ROOT / "data" / "districts.geojson"
OUT = ROOT / "data" / "drought.json"
CACHE = ROOT / "cache"

# ---- settings you may want to change -------------------------------------
BBOX = (-3.5, 4.5, 1.5, 11.5)        # west, south, east, north (Ghana + margin)
START_YEAR = 1981                    # first year of CHIRPS
BASELINE = (1991, 2020)              # years that define "normal"
WINDOW = 3                           # months of rainfall added together
DRY_SEASON_MM = 30                   # if normal 3-month rain is below this, do not rate
HISTORY_MONTHS = 12                  # months of history kept per district
BASE = os.environ.get("TINGA_CHIRPS_BASE", "https://data.chc.ucsb.edu/products")

# CHIRPS products, tried in this order. The newest one that has data is used
# for the WHOLE record, so the current month and the baseline always match.
PRODUCTS = [
    {"id": "CHIRPS v3.0", "url": BASE + "/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.{y}.{m:02d}.tif"},
    {"id": "CHIRPS v2.0", "url": BASE + "/CHIRPS-2.0/africa_monthly/tifs/chirps-v2.0.{y}.{m:02d}.tif.gz"},
]
# --------------------------------------------------------------------------


def month_list(first, last):
    """All (year, month) pairs from first to last, inclusive."""
    out, (y, m) = [], first
    while (y, m) <= last:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    retry = Retry(total=5, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.headers["User-Agent"] = "tinga-lens/0.1"
    return s


def exists(s, url):
    try:
        r = s.get(url, stream=True, timeout=60)
        ok = r.status_code == 200
        r.close()
        return ok
    except Exception:
        return False


def latest_month(s, product, today):
    """Most recent month this product has published (looks back 6 months)."""
    y, m = today.year, today.month
    for _ in range(6):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        if exists(s, product["url"].format(y=y, m=m)):
            return (y, m)
    return None


def fetch_month(s, product, ym):
    """Download one month and return rainfall (mm) for the Ghana window."""
    y, m = ym
    url = product["url"].format(y=y, m=m)
    r = s.get(url, timeout=180)
    r.raise_for_status()
    raw = gzip.decompress(r.content) if url.endswith(".gz") else r.content
    with MemoryFile(raw) as mem, mem.open() as src:
        win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win).astype("float32")
        nodata = src.nodata if src.nodata is not None else -9999
        arr[(arr == nodata) | (arr < 0)] = np.nan
        tf = window_transform(win, src.transform)
    return arr, tf


def load_real(today):
    """Returns months, stack (time, rows, cols), affine transform, product name."""
    s = session()
    best = None
    for p in PRODUCTS:
        last = latest_month(s, p, today)
        print(f"{p['id']}: latest month = {last}")
        if last and (best is None or last > best[1]):
            best = (p, last)
    if best is None:
        sys.exit("No CHIRPS data could be reached. Check the internet connection or the URLs in PRODUCTS.")
    product, last = best
    months = month_list((START_YEAR, 1), last)

    CACHE.mkdir(exist_ok=True)
    cache_file = CACHE / (product["id"].replace(" ", "_") + ".npz")
    have, tf = {}, None
    if cache_file.exists():
        z = np.load(cache_file, allow_pickle=False)
        keys = [tuple(k) for k in z["months"].tolist()]
        cached = z["stack"]                      # read once (it is compressed on disk)
        have = {k: cached[i] for i, k in enumerate(keys)}
        tf = rasterio.Affine(*z["transform"].tolist())
    # always refresh the newest 2 months: CHIRPS can revise recent values
    for k in months[-2:]:
        have.pop(k, None)

    todo = [k for k in months if k not in have]
    print(f"Using {product['id']}; {len(todo)} month(s) to download, {len(have)} cached")
    with ThreadPoolExecutor(8) as ex:
        for k, (arr, t) in zip(todo, ex.map(lambda k: fetch_month(s, product, k), todo)):
            if tf is None:
                tf = t
            if have and arr.shape != next(iter(have.values())).shape:
                sys.exit(f"Grid changed at {k}; delete the cache folder and run again.")
            have[k] = arr
    stack = np.stack([have[k] for k in months]).astype("float32")
    np.savez_compressed(cache_file, stack=stack, months=np.array(months), transform=np.array(tf[:6]))
    return months, stack, tf, product["id"]


def load_demo(today):
    """Made-up rainfall with a realistic season, for previewing the website only."""
    rng = np.random.default_rng(7)
    last = (today.year, today.month - 2) if today.month > 2 else (today.year - 1, today.month + 10)
    months = month_list((START_YEAR, 1), last)
    res = 0.05
    w, s_, e, n = BBOX
    cols, rows = round((e - w) / res), round((n - s_) / res)
    tf = rasterio.Affine(res, 0, w, 0, -res, n)
    lat = (n - (np.arange(rows) + 0.5) * res)[:, None] * np.ones((1, cols))
    lon = (w + (np.arange(cols) + 0.5) * res)[None, :] * np.ones((rows, 1))
    north = np.clip((lat - 6.5) / 3.0, 0, 1)            # 0 = south, 1 = north
    stack = np.empty((len(months), rows, cols), "float32")
    for i, (y, m) in enumerate(months):
        uni = 230 * np.exp(-((m - 8) ** 2) / 5.0)        # one rainy season (north)
        bi = 210 * np.exp(-((m - 6) ** 2) / 3.0) + 150 * np.exp(-((m - 10) ** 2) / 2.0) + 15
        clim = north * uni + (1 - north) * bi
        # smooth year-to-year anomaly that varies across the country
        a, b, c = rng.normal(0, 0.15), rng.normal(0, 0.12), rng.normal(0, 0.12)
        factor = np.exp(a + b * (lat - 8) + c * (lon + 1))
        stack[i] = clim * factor
    return months, stack, tf, "DEMO (made-up numbers)"


def district_means(stack, tf, gdf):
    """Average each month's rainfall over every district -> (time, districts)."""
    shape = stack.shape[1:]
    ids = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=shape,
                    transform=tf, fill=0, dtype="int32")
    out = np.full((stack.shape[0], len(gdf)), np.nan, "float32")
    for i, geom in enumerate(gdf.geometry):
        mask = ids == i + 1
        if not mask.any():      # district smaller than a pixel: take every pixel it touches
            mask = rasterize([(geom, 1)], out_shape=shape, transform=tf, fill=0,
                             dtype="uint8", all_touched=True).astype(bool)
        if mask.any():
            out[:, i] = np.nanmean(stack[:, mask], axis=1)
    return out


def categorise(pctile, normal):
    if normal < DRY_SEASON_MM:
        return "dry_season"
    if pctile <= 10:
        return "very_dry"
    if pctile <= 30:
        return "dry"
    if pctile < 70:
        return "normal"
    if pctile < 90:
        return "wet"
    return "very_wet"


def assess(months, roll, t):
    """Compare time step t with the same calendar month in the baseline years."""
    y, m = months[t]
    base = [i for i, (yy, mm) in enumerate(months)
            if mm == m and BASELINE[0] <= yy <= BASELINE[1] and i >= WINDOW - 1]
    ref = roll[base]                                   # (years, districts)
    cur = roll[t]
    normal = ref.mean(axis=0)
    pctile = ((ref < cur).sum(axis=0) + 0.5 * (ref == cur).sum(axis=0)) / len(base) * 100
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(normal > 0, cur / normal * 100, np.nan)
    return cur, normal, pct, pctile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    args = ap.parse_args()
    today = dt.date.today()

    gdf = gpd.read_file(DISTRICTS)
    months, stack, tf, source = (load_demo if args.demo else load_real)(today)
    print(f"{len(months)} months, grid {stack.shape[1:]}, last = {months[-1]}")

    dm = district_means(stack, tf, gdf)
    # rolling WINDOW-month totals; the first WINDOW-1 steps are incomplete
    roll = np.full_like(dm, np.nan)
    for t in range(WINDOW - 1, len(months)):
        roll[t] = dm[t - WINDOW + 1:t + 1].sum(axis=0)

    T = len(months) - 1
    cur, normal, pct, pctile = assess(months, roll, T)
    hist_steps = list(range(T - HISTORY_MONTHS + 1, T + 1))
    hist = [assess(months, roll, t) for t in hist_steps]

    def label(ym):
        return f"{ym[0]}-{ym[1]:02d}"

    districts, counts = {}, {}
    for i, row in gdf.reset_index(drop=True).iterrows():
        if np.isnan(cur[i]):
            continue
        cat = categorise(pctile[i], normal[i])
        counts[cat] = counts.get(cat, 0) + 1
        districts[row.shapeID] = {
            "name": row.shapeName,
            "rain_mm": round(float(cur[i])),
            "normal_mm": round(float(normal[i])),
            "pct_normal": None if np.isnan(pct[i]) else round(float(pct[i])),
            "percentile": round(float(pctile[i])),
            "category": cat,
            "history": [
                {"m": label(months[t]),
                 "pct": None if np.isnan(h[2][i]) else round(float(h[2][i])),
                 "cat": categorise(h[3][i], h[1][i])}
                for t, h in zip(hist_steps, hist)
            ],
        }

    out = {
        "layer": "drought",
        "demo": bool(args.demo),
        "source": source,
        "updated": today.isoformat(),
        "period": {"from": label(months[T - WINDOW + 1]), "to": label(months[T]), "months": WINDOW},
        "baseline": list(BASELINE),
        "dry_season_mm": DRY_SEASON_MM,
        "counts": counts,
        "districts": districts,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(districts)} districts, {counts}")


if __name__ == "__main__":
    main()
