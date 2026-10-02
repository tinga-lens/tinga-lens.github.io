#!/usr/bin/env python3
"""
Tinga Lens - forest loss layer.

Source: Hansen / UMD / Google Global Forest Change (30 m, yearly, CC BY 4.0).
For each district:
  - tree cover in 2000 (pixels with at least CANOPY % canopy), in hectares
  - tree cover lost in each year since 2001, in hectares
  - recent rate: average yearly loss over the last 3 years, as % of 2000 tree cover

The data are updated once a year, so this script only needs to run once a year.

Run:
  python scripts/forest.py          # real data (downloads about 1-2 GB, needs internet)
  python scripts/forest.py --demo   # made-up data, only for previewing the site
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from rasterio.windows import transform as window_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
CANOPY = 30            # % canopy cover in 2000 that counts as "tree cover" (30 = Global Forest Watch default)
RECENT = 3             # years averaged for the "recent rate"
MIN_COVER_PCT = 5      # districts with less 2000 tree cover than this (% of area) are not rated
BLOCK = 1024           # rows processed at a time
BASE = os.environ.get("TINGA_GFC_BASE", "https://storage.googleapis.com/earthenginepartners-hansen")
VERSIONS = ["GFC-2025-v1.13", "GFC-2024-v1.12", "GFC-2023-v1.11"]   # newest first; first one found is used
TILES = ["10N_010W", "10N_000E", "20N_010W", "20N_000E"]            # 10-degree tiles covering Ghana
# --------------------------------------------------------------------------

CATS = [
    {"key": "r1", "label": "Under 0.5% a year", "note": "", "color": "#fff3c4", "max": 0.5},
    {"key": "r2", "label": "0.5 to 1%", "note": "", "color": "#fdc777", "max": 1},
    {"key": "r3", "label": "1 to 2%", "note": "", "color": "#f58b3f", "max": 2},
    {"key": "r4", "label": "2 to 3%", "note": "", "color": "#d6402b", "max": 3},
    {"key": "r5", "label": "Over 3% a year", "note": "", "color": "#8e0f26", "max": 1e9},
    {"key": "low", "label": "Little tree cover", "note": "not rated", "color": "#bdbdbd"},
]
R = 6371007.2   # earth radius (m) used for pixel areas


def url(version, layer, tile):
    return f"{BASE}/{version}/Hansen_{version}_{layer}_{tile}.tif"


def pick_version(s):
    for v in VERSIONS:
        r = s.get(url(v, "lossyear", TILES[0]), stream=True, timeout=60)
        ok = r.status_code == 200
        r.close()
        print(f"{v}: {'found' if ok else 'not found'}")
        if ok:
            return v
    sys.exit("No Global Forest Change version could be reached. Check VERSIONS and BASE in scripts/forest.py.")


def download(s, link, dest):
    with s.get(link, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    print(f"  downloaded {link.rsplit('/', 1)[1]} ({os.path.getsize(dest) / 1e6:.0f} MB)")


def row_area_ha(tf, row0, nrows, width_deg):
    """Area of one pixel (hectares) for each row; pixels shrink away from the equator."""
    top = tf.f + tf.e * (row0 + np.arange(nrows))
    bot = top + tf.e
    return (R ** 2) * np.radians(width_deg) * np.abs(np.sin(np.radians(top)) - np.sin(np.radians(bot))) / 1e4


def tally(tc_path, ly_path, gdf, nyears, tc_ha, loss_ha):
    """Add one tile's tree cover and loss to the district totals."""
    with rasterio.open(tc_path) as tc, rasterio.open(ly_path) as ly:
        assert tc.transform == ly.transform and tc.shape == ly.shape, "tree cover and loss tiles do not line up"
        b = tc.bounds
        w, s_, e, n = max(BBOX[0], b.left), max(BBOX[1], b.bottom), min(BBOX[2], b.right), min(BBOX[3], b.top)
        if w >= e or s_ >= n:
            return
        win = from_bounds(w, s_, e, n, transform=tc.transform).round_offsets().round_lengths()
        r0, c0, H, W = int(win.row_off), int(win.col_off), int(win.height), int(win.width)
        nd = len(gdf)
        for off in range(0, H, BLOCK):
            h = min(BLOCK, H - off)
            bw = Window(c0, r0 + off, W, h)
            tf = window_transform(bw, tc.transform)
            top = tf.f
            bot = tf.f + tf.e * h
            cand = gdf.cx[w:e, bot:top]
            if cand.empty:
                continue
            ids = rasterize(((g, i + 1) for i, g in zip(cand.index, cand.geometry)),
                            out_shape=(h, W), transform=tf, fill=0, dtype="int32")
            if not ids.any():
                continue
            cover = tc.read(1, window=bw) >= CANOPY
            year = ly.read(1, window=bw)
            row_area = row_area_ha(tf, 0, h, tf.a)          # one value per row
            m = (ids > 0) & cover
            tc_ha += np.bincount(ids[m], weights=row_area[np.nonzero(m)[0]], minlength=nd + 1)[1:]
            m &= (year > 0) & (year <= nyears)
            key = (ids[m] - 1) * (nyears + 1) + year[m].astype("int64")
            loss_ha += np.bincount(key, weights=row_area[np.nonzero(m)[0]],
                                   minlength=nd * (nyears + 1)).reshape(nd, nyears + 1)


def real(gdf):
    import requests
    s = requests.Session()
    version = pick_version(s)
    nyears = int(version.split("-")[1]) - 2000
    tc_ha = np.zeros(len(gdf))
    loss_ha = np.zeros((len(gdf), nyears + 1))
    with tempfile.TemporaryDirectory() as tmp:
        for tile in TILES:
            print(f"Tile {tile}")
            paths = {}
            for layer in ("treecover2000", "lossyear"):
                paths[layer] = os.path.join(tmp, f"{layer}_{tile}.tif")
                download(s, url(version, layer, tile), paths[layer])
            tally(paths["treecover2000"], paths["lossyear"], gdf, nyears, tc_ha, loss_ha)
            for p in paths.values():
                os.remove(p)
    return tc_ha, loss_ha[:, 1:], f"Global Forest Change {version.replace('GFC-', '').replace('-', ' ')}"


def demo(gdf):
    rng = np.random.default_rng(3)
    nyears = 25
    area = district_area_ha(gdf)
    lat = gdf.geometry.centroid.y.to_numpy()
    share = np.clip((8.3 - lat) / 2.5, 0.01, 0.85) * rng.uniform(0.6, 1.1, len(gdf))
    tc = area * share
    trend = np.linspace(0.3, 1.6, nyears)[None, :] * rng.uniform(0.3, 1.8, (len(gdf), 1)) / 100
    loss = tc[:, None] * trend * rng.uniform(0.6, 1.4, (len(gdf), nyears))
    return tc, loss, "DEMO (made-up numbers)"


def district_area_ha(gdf):
    return gdf.geometry.to_crs("ESRI:54034").area.to_numpy() / 1e4     # equal-area projection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    args = ap.parse_args()
    gdf = load_districts()
    tc_ha, loss, source = demo(gdf) if args.demo else real(gdf)
    nyears = loss.shape[1]
    years = [2000 + y for y in range(1, nyears + 1)]
    area = district_area_ha(gdf)
    first_recent, last = years[-RECENT], years[-1]

    districts = {}
    for i, row in gdf.iterrows():
        total = loss[i].sum()
        recent = loss[i, -RECENT:].sum()
        cover_pct = tc_ha[i] / area[i] * 100
        rate = recent / RECENT / tc_ha[i] * 100 if tc_ha[i] > 0 else 0.0
        rated = cover_pct >= MIN_COVER_PCT
        cat = next(c["key"] for c in CATS if rate < c.get("max", -1)) if rated else "low"
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{rate:.1f}%" if rated else "–",
            "big_note": (f"of its 2000 tree cover lost per year, {first_recent} to {last}" if rated
                         else f"Tree cover was under {MIN_COVER_PCT}% of this district in 2000, so it is not rated."),
            "tip": (f"{rate:.1f}% a year" if rated else "Little tree cover"),
            "rows": [
                ["Tree cover in 2000", f"{tc_ha[i]:,.0f} ha ({cover_pct:.0f}% of district)"],
                [f"Lost {first_recent}–{last}", f"{recent:,.0f} ha"],
                [f"Lost 2001–{last}", f"{total:,.0f} ha ({(total / tc_ha[i] * 100 if tc_ha[i] else 0):.0f}%)"],
            ],
            "v": [round(float(x), 1) for x in loss[i]],
            "c": [cat] * nyears,
        }
    print(f"Ghana totals: tree cover 2000 = {tc_ha.sum():,.0f} ha, loss 2001-{last} = {loss.sum():,.0f} ha")

    write_layer("forest", {
        "label": "Forest loss", "title": "Tree cover loss", "source": source, "demo": bool(args.demo),
        "subtitle": f"Average yearly loss, {first_recent} to {last}, as a share of tree cover in 2000",
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Each district shows how fast it has been losing tree cover: the average area lost per year from "
                f"{first_recent} to {last}, as a percentage of the tree cover it had in 2000. Tree cover means 30-metre "
                f"satellite pixels with at least {CANOPY}% canopy from vegetation taller than 5 metres."),
        "limits": [
            "Tree cover loss is not the same as deforestation. It includes logging, farming, mining, fire and the harvesting of plantations, and it counts cocoa, rubber and oil palm as tree cover.",
            "Only losses are shown. Regrowth and replanting are not subtracted.",
            "Detection methods improved over time, so recent years are picked up more completely than the early 2000s. Compare neighbouring districts more than distant years.",
            f"Districts where tree cover was under {MIN_COVER_PCT}% of the area in 2000, mostly northern savanna, are not rated.",
            "The data are released once a year, so this layer changes once a year.",
        ],
        "credits": [{"text": "Tree cover: Hansen/UMD/Google/USGS/NASA Global Forest Change (CC BY 4.0)",
                     "url": "https://glad.earthengine.app/view/global-forest-change"}],
        "chart": {"kind": "bars", "unit": "ha", "x": [str(y) for y in years],
                  "caption": "Tree cover lost each year (hectares)", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
