#!/usr/bin/env python3
"""
Tinga Lens - soil properties across Ghana on a 1 km grid (not averaged by district).

Source: iSDAsoil, 30 m maps of Africa (Hengl et al. 2021, CC BY 4.0), read through Google Earth Engine.
For each property the 30 m topsoil (0-20 cm) values are averaged into 1 km cells (0.009 degrees) and
exported as one small image for Ghana. Nothing is modelled here.

Each property is published as two small files in data/soilgrid/:
  <key>.png   an 8-bit grey image, one pixel per 1 km cell: 0 = outside Ghana, 1 to 255 = the value
              between the low and high values given in the .json file
  <key>.json  where the image sits on the map, its low and high values, unit and wording

The page paints the image in colour and reads the value under the pointer from it.

Run (SOILGRID=trial does pH only and publishes it; full does every property):
  SOILGRID=trial python scripts/soilgrid.py
  SOILGRID=full python scripts/soilgrid.py
"""
import datetime
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agriculture as A  # noqa: E402  (soil properties, units and plausible ranges are defined there)
from common import BBOX, DATA, load_districts  # noqa: E402
from ee_check import ee_login  # noqa: E402
from floodhazard import retry  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 1
CELL = 0.009                           # degrees, about 1 km
TRIAL_KEYS = ["soilph"]
# --------------------------------------------------------------------------

OUT = DATA / "soilgrid"
W, S, E, N = BBOX
WIDTH, HEIGHT = int(round((E - W) / CELL)), int(round((N - S) / CELL))
TRANSFORM = [CELL, 0, W, 0, -CELL, N]
BOUNDS = [[round(N - HEIGHT * CELL, 5), W], [N, round(W + WIDTH * CELL, 5)]]     # [[south, west], [north, east]]


def band(ee, key):
    """The 0-20 cm band of one property, back-transformed to its unit, and the native projection of the source."""
    asset, kind, div, scale, *_ = A.PROPS[key]
    img = ee.Image(A.SOIL + asset).select("mean_0_20")
    native = img.projection()
    v = img.divide(div)
    if kind == "log":
        v = v.exp().subtract(1)
    return v.multiply(scale).setDefaultProjection(native).rename("v")


def fetch(ee, key):
    img = band(ee, key).reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096).reproject(crs="EPSG:4326", crsTransform=TRANSFORM)
    region = ee.Geometry.Rectangle([W, BOUNDS[0][0], BOUNDS[1][1], N], proj="EPSG:4326", geodesic=False)
    url = retry(lambda: img.getDownloadURL({"region": region, "crs": "EPSG:4326", "crsTransform": TRANSFORM, "format": "GEO_TIFF"}))
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    data = r.content
    if data[:2] == b"PK":                                   # a zip holding the image
        z = zipfile.ZipFile(io.BytesIO(data))
        data = z.read([n for n in z.namelist() if n.lower().endswith((".tif", ".tiff"))][0])
    from rasterio.io import MemoryFile
    with MemoryFile(data) as mf, mf.open() as src:
        arr = src.read(1, masked=True).astype("float64").filled(np.nan)
        tf = src.transform
    return arr, tf


def inside_ghana(shape, tf):
    from rasterio.features import geometry_mask
    gdf = load_districts()
    geom = gdf.geometry.union_all() if hasattr(gdf.geometry, "union_all") else gdf.geometry.unary_union
    return ~geometry_mask([geom], out_shape=shape, transform=tf, all_touched=True)


def main():
    mode = os.environ.get("SOILGRID", "").lower()
    keys = TRIAL_KEYS if mode == "trial" else list(A.PROPS)
    ee, project, email = ee_login()
    ee.data.setDeadline(600000)
    A.ee = ee
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Soil grid, {mode or 'full'}: {len(keys)} propert{'y' if len(keys) == 1 else 'ies'}, cells of {CELL} degrees, {WIDTH} x {HEIGHT} pixels", flush=True)
    failed = []
    for key in keys:
        asset, kind, div, scale, unit, dec, label, short, (lo, hi) = A.PROPS[key]
        t0 = time.time()
        try:
            arr, tf = fetch(ee, key)
        except Exception as e:
            failed.append(short)
            print(f"  FAILED {label}: {type(e).__name__}: {str(e)[:300]}", flush=True)
            continue
        mask = inside_ghana(arr.shape, tf) & np.isfinite(arr)
        vals = arr[mask]
        if vals.size < 1000:
            failed.append(short)
            print(f"  FAILED {label}: only {vals.size} cells with a value", flush=True)
            continue
        med = float(np.median(vals))
        p2, p98 = float(np.percentile(vals, 2)), float(np.percentile(vals, 98))
        print(f"  {label}: {vals.size:,} cells, median {med:.3g}, 2% to 98% range {p2:.3g} to {p98:.3g} {unit}, {time.time() - t0:.0f} s", flush=True)
        if not (lo <= med <= hi):
            failed.append(short)
            print(f"  WARNING {label}: median is outside the plausible range {lo} to {hi}. The units may be wrong, so it is NOT published.", flush=True)
            continue
        idx = np.zeros(arr.shape, dtype=np.uint8)
        idx[mask] = 1 + np.rint(np.clip((arr[mask] - p2) / (p98 - p2), 0, 1) * 254).astype(np.uint8)
        from PIL import Image
        Image.fromarray(idx, mode="L").save(OUT / f"{key}.png", optimize=True)
        meta = {"key": key, "label": label, "short": short, "unit": unit, "dec": dec, "low": round(p2, 4), "high": round(p98, 4),
                "median": round(med, 4), "width": arr.shape[1], "height": arr.shape[0], "bounds": BOUNDS, "cell_km": 1,
                "source": "iSDAsoil Africa v1 (Hengl and others, 2021), 0 to 20 cm, averaged from 30 m to 1 km cells",
                "updated": datetime.date.today().isoformat(), "build": BUILD}
        (OUT / f"{key}.json").write_text(json.dumps(meta, indent=1))
        print(f"  Wrote data/soilgrid/{key}.png ({(OUT / f'{key}.png').stat().st_size / 1024:.0f} KB) and {key}.json", flush=True)
    if failed:
        sys.exit(f"These did not publish: {', '.join(failed)}. The others were saved.")


if __name__ == "__main__":
    main()
