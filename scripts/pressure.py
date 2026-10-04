#!/usr/bin/env python3
"""
Tinga Lens - human pressure layer.

Source: Global Human Modification v3 (Theobald and others, 2025; The Nature Conservancy), CC BY 4.0.
It gives, for every 300 m cell, how far the land has been altered by people, from 0 (not modified)
to 1 (fully modified), combining farming, building, roads, mining, energy, logging and pollution.
The "change-consistent" series has one map every five years from 1990 to 2020.

For each district this script works out the area-weighted average for each year, the change since
1990, and where the district stands among Ghana's districts. It writes two layers:
  data/pressure.json        human modification in the latest year
  data/pressurechange.json  change since the first year

The source is a fixed published dataset, so this script needs to run once.

Run:
  python scripts/pressure.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from rasterio.windows import transform as window_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
RECORD = os.environ.get("TINGA_GHM_RECORD", "https://zenodo.org/api/records/14449495")
YEARS = [1990, 1995, 2000, 2005, 2010, 2015, 2020]
PARTS = [("AG", "Agriculture"), ("BU", "Built-up areas"), ("TI", "Roads and other corridors"), ("EX", "Energy and mining"),
         ("FR", "Logging and other harvesting"), ("HA", "Human access"), ("NS", "Changes to natural systems"), ("PO", "Pollution")]
# --------------------------------------------------------------------------

LEVEL = [("q1", "Lowest fifth of districts", "#ffffcc"), ("q2", "Second fifth", "#fed98e"), ("q3", "Middle fifth", "#fe9929"),
         ("q4", "Fourth fifth", "#d95f0e"), ("q5", "Highest fifth of districts", "#993404")]
CHANGE = [("c1", "Lowest fifth of districts", "#f2f0f7"), ("c2", "Second fifth", "#cbc9e2"), ("c3", "Middle fifth", "#9e9ac8"),
          ("c4", "Fourth fifth", "#756bb1"), ("c5", "Highest fifth of districts", "#54278f")]
CREDIT = [{"text": "Human modification: Theobald, D. M. and others (2025), Global Human Modification v3, The Nature Conservancy (CC BY 4.0)",
           "url": "https://doi.org/10.1038/s41597-025-04892-2"}]


def files_on_record(s):
    for attempt in range(1, 4):
        try:
            r = s.get(RECORD, timeout=60)
            if r.status_code == 200:
                return {f["key"]: f["links"]["self"] for f in r.json()["files"]}
            msg = f"HTTP {r.status_code}"
        except Exception as e:
            msg = type(e).__name__
        print(f"  could not read the file list ({msg}), attempt {attempt}", flush=True)
        time.sleep(10 * attempt)
    sys.exit("Could not read the list of files for Global Human Modification v3.")


def pick(files, year, code):
    """The file for one year and one kind of pressure ('AA' = all combined)."""
    hits = [k for k in files if f"_{year}c_{code}_300" in k and k.lower().endswith((".tif", ".tiff"))]
    return (hits[0], files[hits[0]]) if hits else (None, None)


def district_means(path, gdf):
    """Area-weighted mean value in each district, read only for the part of the file that covers Ghana."""
    with rasterio.open(path) as src:
        w, s_, e, n = gdf.total_bounds
        pad = 3 * abs(src.transform.a)
        win = from_bounds(w - pad, s_ - pad, e + pad, n + pad, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win).astype("float64")
        nodata = src.nodata
        tf = window_transform(win, src.transform)
    ok = np.isfinite(a) & (a >= 0) & (a <= 1)
    if nodata is not None:
        ok &= a != nodata
    ids = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=a.shape, transform=tf, fill=0, dtype="int32")
    lat = tf.f + tf.e * (np.arange(a.shape[0]) + 0.5)
    wgt = np.repeat(np.cos(np.radians(lat))[:, None], a.shape[1], axis=1)      # cells are narrower away from the equator
    m = ok & (ids > 0)
    nd = len(gdf)
    num = np.bincount(ids[m], weights=(a * wgt)[m], minlength=nd + 1)[1:]
    den = np.bincount(ids[m], weights=wgt[m], minlength=nd + 1)[1:]
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def read(s, name, link, gdf, allow_download):
    """Read Ghana's part straight from the remote file; if the server will not allow that, download the file."""
    for attempt in range(1, 3):
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="10", GDAL_HTTP_TIMEOUT="120"):
                return district_means(link, gdf)
        except Exception as e:
            print(f"  {name}: remote read failed ({type(e).__name__}), attempt {attempt}", flush=True)
            time.sleep(15)
    if not allow_download or not str(link).startswith("http"):
        return None
    print(f"  {name}: downloading the whole file instead (large)", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, "ghm.tif")
        with s.get(link, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 23):
                    f.write(chunk)
        return district_means(dest, gdf)


def fifths(values, cats):
    """Put each district in a fifth of the Ghana ranking; also return the share of districts below it."""
    order = np.argsort(np.argsort(values, kind="stable"), kind="stable")
    below = order / max(len(values) - 1, 1) * 100
    return [cats[min(int(o * 5 / len(values)), 4)][0] for o in order], below


def main():
    import requests
    s = requests.Session()
    gdf = load_districts()
    files = files_on_record(s)
    series = np.full((len(gdf), len(YEARS)), np.nan)
    for j, y in enumerate(YEARS):
        name, link = pick(files, y, "AA")
        if not name:
            sys.exit(f"No combined file found for {y}; the file names on the record may have changed.")
        v = read(s, name, link, gdf, allow_download=True)
        if v is None:
            sys.exit(f"Could not read {name}.")
        series[:, j] = v
        print(f"  {y}: Ghana district mean {np.nanmean(v):.3f}", flush=True)
    if np.isnan(series).any() or not (0.01 < np.nanmean(series[:, -1]) < 0.99):
        sys.exit("Human modification values look wrong (missing districts or an implausible average); not publishing.")

    parts = {}                                    # which pressures make up the latest value; skipped if a file cannot be read remotely
    for code, label in PARTS:
        name, link = pick(files, YEARS[-1], code)
        v = read(s, name, link, gdf, allow_download=False) if name else None
        if v is not None and not np.isnan(v).all():
            parts[label] = np.nan_to_num(v)

    y0, y1 = YEARS[0], YEARS[-1]
    now, change = series[:, -1], series[:, -1] - series[:, 0]
    cat_now, below_now = fifths(now, LEVEL)
    cat_chg, below_chg = fifths(change, CHANGE)
    print(f"Ghana: {np.mean(series[:, 0]):.3f} in {y0}, {np.mean(now):.3f} in {y1}; change ranges {change.min():+.3f} to {change.max():+.3f}")

    def build(which):
        out = {}
        for i, row in gdf.iterrows():
            top = sorted(((lab, float(v[i])) for lab, v in parts.items()), key=lambda t: -t[1])[:3]
            rows = [[f"Human modification in {y1}", f"{now[i]:.2f}"],
                    ["Higher than", f"{below_now[i]:.0f}% of Ghana's districts"],
                    [f"Change since {y0}", f"{change[i]:+.2f} (from {series[i, 0]:.2f})"],
                    ["Change is larger than in", f"{below_chg[i]:.0f}% of districts"]]
            if top:
                rows.append([f"Largest pressures in {y1}", ", ".join(f"{lab.lower()} {v:.2f}" for lab, v in top)])
            if which == "now":
                d = {"cat": cat_now[i], "big": f"{now[i]:.2f}", "big_note": f"human modification in {y1}, on a scale from 0 (not modified) to 1 (fully modified)",
                     "tip": f"{now[i]:.2f}, higher than {below_now[i]:.0f}% of districts", "c": [cat_now[i]] * len(YEARS)}
            else:
                d = {"cat": cat_chg[i], "big": f"{change[i]:+.2f}", "big_note": f"change in human modification, {y0} to {y1}",
                     "tip": f"{change[i]:+.2f} since {y0}", "c": [cat_chg[i]] * len(YEARS)}
            out[row.shapeID] = {"name": row.shapeName, "rows": rows, "v": [round(float(x), 3) for x in series[i]], **d}
        return out

    chart = {"kind": "bars", "unit": "", "x": [str(y) for y in YEARS], "caption": "Human modification at each date (0 to 1)", "top": "", "bottom": ""}
    shared = ["The source's own check against independent reference data gave a typical error of about 0.18 for a single cell. District averages are steadier than that, but small differences between districts should not be over-read.",
              "The figure is an index built from many datasets on farming, building, roads, mining, energy, logging and pollution. It is not a direct measurement.",
              "A district average hides variation inside the district. A district with a city and a forest reserve can score the same as one that is evenly farmed.",
              "The classes are fifths of Ghana's 260 districts, so they show where a district stands within Ghana, not a fixed level of pressure.",
              f"The latest date is {y1}. Change since then is not shown."]
    write_layer("pressure", {
        "label": "Human pressure", "title": "Human modification of the land", "source": "Global Human Modification v3 (TNC)", "demo": False,
        "subtitle": f"District average in {y1}, from 0 (not modified) to 1 (fully modified)",
        "categories": [{"key": k, "label": lab, "note": "", "color": c} for k, lab, c in LEVEL],
        "how": (f"Each district shows how far its land had been altered by people in {y1}, as the average of the Global Human "
                f"Modification index across the district. The index runs from 0, land that is not modified, to 1, land that is "
                f"fully modified. Districts are coloured by where they stand among Ghana's districts. Click a district to see its "
                f"value at each date since {y0}."),
        "limits": shared, "credits": CREDIT, "chart": chart, "districts": build("now"),
    })
    write_layer("pressurechange", {
        "label": "Pressure change", "title": "Change in human modification", "source": "Global Human Modification v3 (TNC)", "demo": False,
        "subtitle": f"Change in the district average, {y0} to {y1}",
        "categories": [{"key": k, "label": lab, "note": "", "color": c} for k, lab, c in CHANGE],
        "how": (f"Each district shows how much its human modification index changed between {y0} and {y1}. A positive figure means "
                f"more of the land has been altered by people. Districts are coloured by where their change stands among Ghana's "
                f"districts. A district can have high pressure that is stable, or low pressure that is rising quickly."),
        "limits": ["Small changes are within the uncertainty of the source data. Read the direction and the ranking more than the exact figure."] + shared,
        "credits": CREDIT, "chart": chart, "districts": build("change"),
    })


if __name__ == "__main__":
    main()
