#!/usr/bin/env python3
"""
Tinga Lens - observed flooding layer.

Source: Copernicus Emergency Management Service, Global Flood Monitoring (GFM).
GFM maps flooded land from Sentinel-1 radar images at 20 m. Radar sees through cloud.
"Flooded" means water where the reference water map has none, so rivers, lakes and the
normal seasonal water are not counted.

This script maps named flood events (see EVENTS). For each district inside the event area:
  - flooded area on each satellite pass, in square kilometres
  - total area seen flooded on at least one pass

An event is a past period, so this script needs to run once per event.

Run:
  python scripts/flood.py
"""
import datetime as dt
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from rasterio.windows import transform as window_transform
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
STAC = os.environ.get("TINGA_GFM_STAC", "https://stac.eodc.eu/api/v1")
EVENTS = [   # the first one is shown on the map; bbox = west, south, east, north
    {"key": "volta2023", "name": "Lower Volta flooding after the Akosombo and Kpong dam spillage",
     "start": "2023-09-15", "end": "2023-11-15", "bbox": (0.0, 5.7, 1.0, 6.5)},
]
MIN_KM2 = 0.1          # less flooded area than this is shown as "none detected"
# --------------------------------------------------------------------------

CATS = [
    {"key": "f0", "label": "None detected", "note": "", "color": "#f1eee6", "max": MIN_KM2},
    {"key": "f1", "label": "Under 1 km²", "note": "", "color": "#c6dbef", "max": 1},
    {"key": "f2", "label": "1 to 5 km²", "note": "", "color": "#6baed6", "max": 5},
    {"key": "f3", "label": "5 to 20 km²", "note": "", "color": "#2171b5", "max": 20},
    {"key": "f4", "label": "Over 20 km²", "note": "", "color": "#08306b", "max": 1e12},
    {"key": "out", "label": "Outside the mapped area", "note": "not assessed", "color": "#bdbdbd"},
]


def get_json(s, url, **kw):
    for attempt in range(1, 4):
        try:
            r = s.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r.json()
            msg = f"HTTP {r.status_code}"
        except Exception as e:
            msg = type(e).__name__
        print(f"  request failed ({msg}), attempt {attempt}", flush=True)
        time.sleep(5 * attempt)
    sys.exit(f"Could not read {url}")


def search(s, ev):
    """Every GFM scene over the event area and period."""
    params = {"collections": "GFM", "bbox": ",".join(map(str, ev["bbox"])), "limit": 100,
              "datetime": f"{ev['start']}T00:00:00Z/{ev['end']}T23:59:59Z"}
    page = get_json(s, f"{STAC}/search", params=params)
    items = []
    while True:
        items += page.get("features", [])
        nxt = next((l["href"] for l in page.get("links", []) if l.get("rel") == "next"), None)
        if not nxt or not page.get("features"):
            return items
        page = get_json(s, nxt)


def read(href, win=None):
    for attempt in range(1, 4):
        try:
            with rasterio.open(href) as src:
                return (src.read(1, window=win) if win is not None else None), src.crs, src.transform
        except Exception as e:
            print(f"  could not read {href.rsplit('/', 1)[-1]} ({type(e).__name__}), attempt {attempt}", flush=True)
            time.sleep(5 * attempt)
    return None, None, None


def run_event(s, ev, gdf):
    items = search(s, ev)
    print(f"{ev['name']}: {len(items)} scenes", flush=True)
    if not items:
        sys.exit("No scenes found for this event.")
    area_box = box(*ev["bbox"])
    inside = gdf[gdf.geometry.intersects(area_box)]
    tiles = {}
    for it in items:
        tiles.setdefault(it["properties"].get("Equi7Tile") or it["id"].rsplit("_", 2)[-1], []).append(it)
    dates = sorted({it["properties"]["datetime"][:10] for it in items})
    di = {d: j for j, d in enumerate(dates)}
    nd = len(gdf)
    by_date = np.zeros((nd, len(dates)))            # flooded km2, district x date
    seen = np.zeros((nd, len(dates)), bool)         # did the satellite cover the district that day
    ever = np.zeros(nd)                             # km2 flooded on at least one pass
    done = failed = 0
    with rasterio.Env(GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="5", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        for tile, group in sorted(tiles.items()):
            _, crs, tf = read(group[0]["assets"]["ensemble_flood_extent"]["href"])
            if crs is None:
                failed += len(group)
                continue
            local = inside.to_crs(crs)
            clip = gpd_bounds(area_box, crs)
            win = from_bounds(*clip, transform=tf).round_offsets().round_lengths()
            win = win.intersection(rasterio.windows.Window(0, 0, *reversed(group[0]["properties"].get("proj:shape", [15000, 15000]))))
            h, w = int(win.height), int(win.width)
            if h <= 0 or w <= 0:
                continue
            wtf = window_transform(win, tf)
            ids = rasterize(((g, i + 1) for i, g in zip(local.index, local.geometry)), out_shape=(h, w), transform=wtf, fill=0, dtype="int32")
            px_km2 = abs(wtf.a * wtf.e) / 1e6
            union = np.zeros((h, w), bool)
            day = {}
            for it in sorted(group, key=lambda x: x["properties"]["datetime"]):
                a, _, _ = read(it["assets"]["ensemble_flood_extent"]["href"], win)
                done += 1
                if a is None:
                    failed += 1
                    continue
                d = it["properties"]["datetime"][:10]
                f, valid = day.setdefault(d, [np.zeros((h, w), bool), np.zeros((h, w), bool)])
                f |= a == 1
                valid |= a != 255
                if done % 10 == 0:
                    print(f"  {done}/{len(items)} scenes read", flush=True)
            for d, (f, valid) in day.items():
                by_date[:, di[d]] += np.bincount(ids[f], minlength=nd + 1)[1:] * px_km2
                seen[:, di[d]] |= np.bincount(ids[valid], minlength=nd + 1)[1:] > 0
                union |= f
            ever += np.bincount(ids[union], minlength=nd + 1)[1:] * px_km2
    if failed > len(items) / 4:
        sys.exit(f"{failed} of {len(items)} scenes could not be read; not publishing.")
    if failed:
        print(f"{failed} scene(s) could not be read and were left out.")
    return dates, by_date, seen, ever, set(inside.index), len(items) - failed


def gpd_bounds(geom, crs):
    import geopandas as gpd
    return gpd.GeoSeries([geom.segmentize(0.05)], crs="EPSG:4326").to_crs(crs).total_bounds


def nice(d):
    x = dt.date.fromisoformat(d)
    return f"{x.day} {x.strftime('%b %Y')}"


def main():
    import requests
    gdf = load_districts()
    area = gdf.geometry.to_crs("ESRI:54034").area.to_numpy() / 1e6
    ev = EVENTS[0]
    dates, by_date, seen, ever, inside, nscenes = run_event(requests.Session(), ev, gdf)
    w, s_, e, n = ev["bbox"]

    districts = {}
    for i, row in gdf.iterrows():
        if i not in inside or not seen[i].any():
            districts[row.shapeID] = {"name": row.shapeName, "cat": "out", "big": "–",
                                      "big_note": "This district is outside the area mapped for this event.",
                                      "tip": "Not assessed", "rows": [], "v": [None] * len(dates), "c": ["out"] * len(dates)}
            continue
        km2 = ever[i]
        cat = next(c["key"] for c in CATS if km2 < c.get("max", -1))
        peak = int(np.argmax(by_date[i]))
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{km2:,.1f} km²" if km2 >= MIN_KM2 else "None",
            "big_note": f"of land seen flooded on at least one satellite pass, {nice(ev['start'])} to {nice(ev['end'])}",
            "tip": f"{km2:,.1f} km² flooded" if km2 >= MIN_KM2 else "None detected",
            "rows": [
                ["Share of the district", f"{km2 / area[i] * 100:.1f}%"],
                ["Largest extent on one pass", f"{by_date[i, peak]:,.1f} km² ({nice(dates[peak])})" if km2 >= MIN_KM2 else "–"],
                ["Satellite passes over the district", str(int(seen[i].sum()))],
            ],
            "v": [round(float(x), 2) if ok else None for x, ok in zip(by_date[i], seen[i])],
            "c": [cat] * len(dates),
        }
    total = sum(ever[i] for i in inside)
    print(f"Flooded on at least one pass: {total:,.1f} km2 over {len(dates)} dates, {nscenes} scenes")

    write_layer("flood", {
        "label": "Observed flooding", "title": "Observed flooding", "source": "Copernicus GFM (Sentinel-1)", "demo": False,
        "subtitle": f"{ev['name']}, {nice(ev['start'])} to {nice(ev['end'])}",
        "event": {"key": ev["key"], "name": ev["name"], "start": ev["start"], "end": ev["end"], "bbox": list(ev["bbox"]), "scenes": nscenes},
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"This map covers one flood event: {ev['name'].lower()}. Each district shows the area of land that Sentinel-1 radar "
                f"satellites saw under water on at least one pass between {nice(ev['start'])} and {nice(ev['end'])}. Rivers, lakes "
                f"and water that is normally there are not counted. Only districts between {s_}° and {n}° north and {w}° and {e}° east "
                f"were assessed. Click a district to see the flooded area on each pass."),
        "limits": [
            "A satellite passes every few days, so a flood that rose and fell between passes is missed, and the largest extent shown may be smaller than the true peak.",
            "Radar cannot map water under dense tree cover or between buildings, so flooding in forests, plantations and built-up areas is under-counted. Flooded homes in towns are mostly not visible.",
            "Flooded crops and wet bare soil can be confused. The source provides a likelihood for every pixel; this map uses its yes-or-no result.",
            "The figure is land area, not people or property affected.",
            "Districts outside the mapped area are grey. Grey does not mean there was no flooding there.",
            "This layer shows a past event. It is not a live flood map or a warning.",
        ],
        "credits": [{"text": "Flood extent: Copernicus Emergency Management Service, Global Flood Monitoring (GFM), from Copernicus Sentinel-1 data",
                     "url": "https://global-flood.emergency.copernicus.eu/"}],
        "chart": {"kind": "bars", "unit": "km²", "x": [f"{int(d[8:])} {dt.date.fromisoformat(d).strftime('%b')}" for d in dates],
                  "caption": "Flooded area on each satellite pass (square kilometres). Gaps: no pass that day.", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
