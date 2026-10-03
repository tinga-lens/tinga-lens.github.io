#!/usr/bin/env python3
"""
Tinga Lens - built-up area and urban growth layer.

Source: Global Human Settlement Layer, GHS-BUILT-S R2023A (European Commission, Joint Research Centre).
It gives the built-up surface (buildings) in each 1 km cell, in square metres, every five years.
For each district:
  - built-up area at each date from 2000 to 2020, in square kilometres
  - growth from the first to the last date, in percent
  - built-up share of the district's land

The source changes only when a new release is published, so this script needs to run once.

Run:
  python scripts/urban.py          # real data (downloads about 150 MB per date)
"""
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.windows import from_bounds
from rasterio.windows import transform as window_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
EPOCHS = [2000, 2005, 2010, 2015, 2020]   # dates built from satellite images (2025 and 2030 in the source are projections, so they are left out)
RELEASE = "R2023A"
BASE = os.environ.get("TINGA_GHSL_BASE", "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A")
FINE = 10              # each 1 km cell is split into FINE x FINE pieces when it is shared between districts
MIN_BUILT_KM2 = 0.5    # districts with less built-up area than this at the first date are not given a growth rating
# --------------------------------------------------------------------------

CATS = [
    {"key": "g1", "label": "Under 20%", "note": "", "color": "#f2f0f7", "max": 20},
    {"key": "g2", "label": "20 to 40%", "note": "", "color": "#cbc9e2", "max": 40},
    {"key": "g3", "label": "40 to 60%", "note": "", "color": "#9e9ac8", "max": 60},
    {"key": "g4", "label": "60 to 100%", "note": "", "color": "#756bb1", "max": 100},
    {"key": "g5", "label": "Over 100%", "note": "more than doubled", "color": "#54278f", "max": 1e12},
    {"key": "low", "label": "Very little built-up area", "note": "not rated", "color": "#bdbdbd"},
]


def name(year):
    return f"GHS_BUILT_S_E{year}_GLOBE_{RELEASE}_54009_1000"


def fetch(s, year, tmp):
    link = f"{BASE}/{name(year)}/V1-0/{name(year)}_V1_0.zip"
    z = os.path.join(tmp, f"{year}.zip")
    for attempt in range(1, 4):
        try:
            with s.get(link, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(z, "wb") as f:
                    for chunk in r.iter_content(1 << 22):
                        f.write(chunk)
            break
        except Exception as e:
            print(f"  download failed ({type(e).__name__}), attempt {attempt}", flush=True)
            if attempt == 3:
                sys.exit(f"Could not download {link}")
    with zipfile.ZipFile(z) as zf:
        tif = next(n for n in zf.namelist() if n.lower().endswith(".tif"))
        zf.extract(tif, tmp)
    os.remove(z)
    print(f"  {year}: downloaded", flush=True)
    return os.path.join(tmp, tif)


def tally(path, geoms):
    """Built-up square kilometres in each district for one date."""
    with rasterio.open(path) as src:
        assert src.crs is not None and "54009" in src.crs.to_string() or "Mollweide" in src.crs.to_wkt(), "unexpected map projection"
        w, s_, e, n = geoms.total_bounds
        pad = 2 * abs(src.transform.a)
        win = from_bounds(w - pad, s_ - pad, e + pad, n + pad, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win).astype("float64")
        cell_m2 = abs(src.transform.a * src.transform.e)
        a[(a < 0) | (a > cell_m2 * 1.001)] = 0            # no-data and sea
        tf = window_transform(win, src.transform)
    fine_tf = tf * Affine.scale(1 / FINE)
    ids = rasterize(((g, i + 1) for i, g in enumerate(geoms.geometry)),
                    out_shape=(a.shape[0] * FINE, a.shape[1] * FINE), transform=fine_tf, fill=0, dtype="int32")
    fine = np.repeat(np.repeat(a, FINE, axis=0), FINE, axis=1) / (FINE * FINE)
    return np.bincount(ids.ravel(), weights=fine.ravel(), minlength=len(geoms) + 1)[1:] / 1e6


def main():
    import requests
    gdf = load_districts()
    moll = gdf.to_crs("ESRI:54009")                      # the projection of the source; it keeps areas true
    area = moll.geometry.area.to_numpy() / 1e6
    built = np.zeros((len(gdf), len(EPOCHS)))
    s = requests.Session()
    with tempfile.TemporaryDirectory() as tmp:
        for j, year in enumerate(EPOCHS):
            p = fetch(s, year, tmp)
            built[:, j] = tally(p, moll)
            os.remove(p)
    y0, y1 = EPOCHS[0], EPOCHS[-1]
    total0, total1 = built[:, 0].sum(), built[:, -1].sum()
    if not (50 < total1 < 20000 and total1 >= total0):
        sys.exit(f"Built-up totals look wrong ({total0:,.0f} km2 in {y0}, {total1:,.0f} km2 in {y1}); not publishing.")

    districts = {}
    for i, row in gdf.iterrows():
        b0, b1 = built[i, 0], built[i, -1]
        rated = b0 >= MIN_BUILT_KM2
        growth = (b1 / b0 - 1) * 100 if b0 > 0 else 0.0
        cat = next(c["key"] for c in CATS if growth < c.get("max", -1)) if rated else "low"
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"+{growth:.0f}%" if rated else "–",
            "big_note": (f"growth in built-up area, {y0} to {y1}" if rated
                         else f"Built-up area was under {MIN_BUILT_KM2} km² in {y0}, so growth is not rated."),
            "tip": f"+{growth:.0f}% since {y0}" if rated else "Very little built-up area",
            "rows": [
                [f"Built-up area in {y0}", f"{b0:,.1f} km²"],
                [f"Built-up area in {y1}", f"{b1:,.1f} km²"],
                [f"Added {y0}–{y1}", f"{b1 - b0:,.1f} km²"],
                [f"Share of district built on, {y1}", f"{b1 / area[i] * 100:.1f}%"],
            ],
            "v": [round(float(x), 2) for x in built[i]],
            "c": [cat] * len(EPOCHS),
        }
    print(f"Ghana totals: built-up {total0:,.0f} km2 in {y0}, {total1:,.0f} km2 in {y1}")

    write_layer("urban", {
        "label": "Urban growth", "title": "Built-up area growth", "source": f"GHSL GHS-BUILT-S {RELEASE}", "demo": False,
        "subtitle": f"Growth in built-up area, {y0} to {y1}",
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Each district shows how much its built-up area grew between {y0} and {y1}, in percent. Built-up area means "
                f"the ground covered by buildings, estimated from Landsat and Sentinel-2 satellite images by the Global Human "
                f"Settlement Layer. Click a district to see its built-up area at each date."),
        "limits": [
            "Built-up area counts buildings only. Roads, bare plots and open spaces between buildings are not included, so it is smaller than the area people would call a town.",
            "Percent growth is large where there was little to begin with. Read it together with the square kilometres added.",
            f"The source data are in 1 km cells. Cells shared between districts are split by area, so figures for very small districts are approximate. Districts with under {MIN_BUILT_KM2} km² built on in {y0} are not rated.",
            f"The latest date built from satellite images is {y1}. Building since then is not shown.",
            "Small or scattered buildings, especially under trees or with thatched roofs, can be missed.",
            "District boundaries are those of 2019 for every date, so the figures follow the same land through time.",
        ],
        "credits": [{"text": "Built-up surface: GHSL GHS-BUILT-S R2023A, European Commission Joint Research Centre (CC BY 4.0)",
                     "url": "https://human-settlement.emergency.copernicus.eu/"}],
        "chart": {"kind": "bars", "unit": "km²", "x": [str(y) for y in EPOCHS],
                  "caption": "Built-up area at each date (square kilometres)", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
