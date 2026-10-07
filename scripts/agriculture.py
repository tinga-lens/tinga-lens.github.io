#!/usr/bin/env python3
"""
Tinga Lens - cropland and soil nutrients (nitrogen, phosphorus, potassium) by district.

Sources, both read through Google Earth Engine:
  * Cropland: ESA WorldCover 10 m v200 (2021), class 40 "Cropland".
  * Soil nutrients: iSDAsoil, 30 m maps of Africa (Hengl et al. 2021, CC BY 4.0): total nitrogen (g/kg),
    extractable phosphorus (ppm) and extractable potassium (ppm), at 0-20 cm and 20-50 cm.

Nothing is modelled here. The script adds up and averages the two published datasets by district:
  * how much of each district is cropland (square kilometres and share of land);
  * the average of each nutrient on that district's cropland, and for comparison on all its land.
The nutrient maps are themselves computer predictions, and the site says so.

Districts are rated by where they fall among Ghana's other districts (fifths). No farm-advice
thresholds are used, because those depend on the crop and on the soil test method.

Run (a trial of eight districts that publishes nothing, then the full run):
  AGRICULTURE=trial python scripts/agriculture.py
  python scripts/agriculture.py
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from shapely.geometry import mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, load_districts, write_layer  # noqa: E402
from ee_check import ee_login  # noqa: E402
from floodhazard import retry  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 1                               # raise this to make the weekly update rebuild the layers
WORLDCOVER = "ESA/WorldCover/v200"
CROPLAND_CLASS = 40
SOIL = "ISDASOIL/Africa/v1/"
NUTRIENTS = {   # key: (asset, back-transform divisor, unit, decimals, label, short label)
    "soiln": ("nitrogen_total", 100, "g/kg", 2, "Total nitrogen", "Nitrogen"),
    "soilp": ("phosphorus_extractable", 10, "ppm", 1, "Extractable phosphorus", "Phosphorus"),
    "soilk": ("potassium_extractable", 10, "ppm", 0, "Extractable potassium", "Potassium"),
}
MIN_CROP_KM2 = 1.0                      # districts with less cropland than this are not given a nutrient rating
CROP_SCALE_M = 10
WORKERS = 4
TRIAL_COUNT = 8
# --------------------------------------------------------------------------

STORE = CACHE / "agriculture"
ee = None

GREENS = ["#eef4e6", "#cfe3bd", "#9ccb88", "#56a05f", "#1f6b43"]
FIFTHS = ["Lowest fifth", "Lower fifth", "Middle fifth", "Higher fifth", "Highest fifth"]
CROP_CATS = [
    {"key": "c0", "label": "Under 1%", "note": "", "color": "#f4efe1", "max": 1},
    {"key": "c1", "label": "1 to 10%", "note": "", "color": "#e5d6a0", "max": 10},
    {"key": "c2", "label": "10 to 25%", "note": "", "color": "#c9b15a", "max": 25},
    {"key": "c3", "label": "25 to 50%", "note": "", "color": "#97832d", "max": 50},
    {"key": "c4", "label": "Over 50%", "note": "", "color": "#5e5114", "max": 1e12},
]


def soil_image():
    """Six bands, already back-transformed to g/kg or ppm: <key>_top (0-20 cm) and <key>_sub (20-50 cm)."""
    bands = []
    for key, (asset, div, *_rest) in NUTRIENTS.items():
        img = ee.Image(SOIL + asset)
        for src, tag in (("mean_0_20", "top"), ("mean_20_50", "sub")):
            bands.append(img.select(src).divide(div).exp().subtract(1).rename(f"{key}_{tag}"))
    return ee.Image.cat(bands)


def ask(shape):
    """One district -> cropland area (km2) and the mean of each nutrient."""
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    crop = ee.ImageCollection(WORLDCOVER).first().select("Map").eq(CROPLAND_CLASS)
    area = ee.Image.pixelArea().divide(1e6).updateMask(crop).rename("crop_km2")
    out = retry(lambda: area.reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=CROP_SCALE_M,
                                          maxPixels=1e12, tileScale=8).getInfo())
    res = {"crop_km2": float((out or {}).get("crop_km2") or 0)}
    soil = soil_image()
    names = [f"{k}_{t}" for k in NUTRIENTS for t in ("top", "sub")]
    onfarm = soil.updateMask(crop).rename([f"{n}_crop" for n in names])
    allland = soil.select([f"{k}_top" for k in NUTRIENTS]).rename([f"{k}_all" for k in NUTRIENTS])
    both = ee.Image.cat([onfarm, allland])
    proj = soil.select(0).projection()
    out = retry(lambda: both.reduceRegion(reducer=ee.Reducer.mean(), geometry=geom, crs=proj,
                                          maxPixels=1e12, tileScale=8).getInfo())
    res.update({k: (None if v is None else float(v)) for k, v in (out or {}).items()})
    return res


def one(row):
    f = STORE / f"{row.shapeID}_b{BUILD}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = ask(row.geometry.simplify(0.0003).buffer(0))
    f.write_text(json.dumps(res))
    return res


def fmt(v, dec):
    return f"{v:,.{dec}f}" if dec else f"{v:,.0f}"


def main():
    global ee
    trial = os.environ.get("AGRICULTURE", "").lower() == "trial"
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    gdf = load_districts()
    area_km2 = gdf.to_crs(6933).geometry.area / 1e6
    rows = list(gdf.assign(land_km2=area_km2).itertuples())
    if trial:
        step = max(1, len(rows) // TRIAL_COUNT)
        rows = rows[::step][:TRIAL_COUNT]
    print(f"Cropland and soil nutrients: {len(rows)} districts" + (" (trial, nothing is published)" if trial else ""), flush=True)
    t0, results, failed = time.time(), {}, []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(one, r): r for r in rows}
        for k, (fut, r) in enumerate(futures.items(), 1):
            try:
                results[r.shapeID] = (r, fut.result())
            except Exception as e:
                failed.append(r.shapeName)
                print(f"  FAILED {r.shapeName}: {type(e).__name__}: {str(e)[:300]}", flush=True)
            if k % 40 == 0:
                print(f"  {k} of {len(rows)} districts, {(time.time() - t0) / 60:.1f} min", flush=True)
    if failed:
        sys.exit(f"{len(failed)} districts failed ({', '.join(failed[:8])}). Finished districts are saved; run again to retry the rest. Nothing was published.")

    if trial:
        print(f"Trial finished in {(time.time() - t0) / 60:.1f} min for {len(rows)} districts "
              f"(a full run is about {(time.time() - t0) / 60 * 260 / len(rows):.0f} min).")
        print(f"{'District':28s} {'land km2':>9s} {'crop km2':>9s} {'crop %':>7s} | N top  N sub | P top  P sub | K top  K sub | N all P all K all")
        for sid, (r, v) in results.items():
            g = lambda k: "   –" if v.get(k) is None else f"{v[k]:6.2f}"
            print(f"{r.shapeName[:28]:28s} {r.land_km2:9.0f} {v['crop_km2']:9.1f} {v['crop_km2'] / r.land_km2 * 100:7.1f} | "
                  f"{g('soiln_top_crop')} {g('soiln_sub_crop')} | {g('soilp_top_crop')} {g('soilp_sub_crop')} | {g('soilk_top_crop')} {g('soilk_sub_crop')} | "
                  f"{g('soiln_all')} {g('soilp_all')} {g('soilk_all')}")
        return

    ids = list(results)
    land = {s: results[s][0].land_km2 for s in ids}
    crop = {s: results[s][1]["crop_km2"] for s in ids}
    total_crop = sum(crop.values())
    order = sorted(ids, key=lambda s: -crop[s])
    rank_crop = {s: i + 1 for i, s in enumerate(order)}

    # ---- cropland layer ----
    districts = {}
    for s in ids:
        r = results[s][0]
        pct = crop[s] / land[s] * 100 if land[s] else 0
        cat = next(c["key"] for c in CROP_CATS if pct < c["max"])
        districts[s] = {
            "name": r.shapeName, "cat": cat, "big": f"{pct:.1f}%" if pct < 10 else f"{pct:.0f}%",
            "big_note": "of the district's land is cropland",
            "tip": f"{pct:.1f}% of the land, {crop[s]:,.0f} km² of cropland",
            "rows": [["Cropland (2021)", f"{crop[s]:,.1f} km²"], ["Land in the district", f"{land[s]:,.0f} km²"],
                     ["Share of all cropland in Ghana", f"{crop[s] / total_crop * 100:.2f}%" if total_crop else "–"],
                     ["Rank by cropland area", f"{rank_crop[s]} of {len(ids)}"]],
            "v": [round(crop[s], 1), round(max(land[s] - crop[s], 0), 1)], "c": [cat, cat],
        }
    print(f"Cropland in Ghana: {total_crop:,.0f} km2 ({total_crop / sum(land.values()) * 100:.1f}% of the land)")
    print("Most cropland: " + "; ".join(f"{districts[s]['name']} {crop[s]:,.0f} km2" for s in order[:8]))
    write_layer("cropland", {
        "label": "Cropland", "title": "Cropland", "source": "ESA WorldCover 10 m v200 (2021)", "demo": False,
        "subtitle": "Share of each district's land that is cropland, 2021",
        "build": BUILD,
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CROP_CATS],
        "how": ("Each district shows the share of its land that satellites saw as cropland in 2021. The map is the European Space Agency's WorldCover, "
                "made from Sentinel-1 radar and Sentinel-2 images at 10 m. Tinga Lens adds up the cropland cells in each district. Click a district for the area in square kilometres."),
        "limits": [
            "This is a satellite classification, not a farm census. It tells you where land looks like cropland, not who farms it, which crop is grown or whether it is in use this year.",
            "Small farms mixed with trees and fallow land are hard to separate. Tree crops such as cocoa, and farms under scattered trees, are often classed as tree cover, and resting fields can be classed as grass. Cropland is therefore likely to be under-counted, most of all in the forest and transition zones.",
            "The map shows 2021 only. It does not show change.",
            "It is not a map of individual fields. Field boundaries are not available for Ghana.",
        ],
        "credits": [{"text": "Cropland: ESA WorldCover 10 m 2021 v200, Zanaga and others (2022), CC BY 4.0", "url": "https://esa-worldcover.org/"}],
        "chart": {"kind": "bars", "unit": "km²", "x": ["Cropland", "Other land"],
                  "caption": "Cropland and other land in the district (square kilometres)", "top": "", "bottom": ""},
        "districts": districts,
    })

    # ---- nutrient layers ----
    for key, (asset, div, unit, dec, label, short) in NUTRIENTS.items():
        top, sub, allv = (f"{key}_top_crop", f"{key}_sub_crop", f"{key}_all")
        rated = [s for s in ids if crop[s] >= MIN_CROP_KM2 and results[s][1].get(top) is not None]
        vals = np.array([results[s][1][top] for s in rated])
        cuts = np.percentile(vals, [20, 40, 60, 80]) if len(vals) else []
        weight = np.array([crop[s] for s in rated])
        national = float(np.average(vals, weights=weight)) if len(vals) else None
        order_v = sorted(rated, key=lambda s: -results[s][1][top])
        rank = {s: i + 1 for i, s in enumerate(order_v)}
        print(f"{label}: {len(rated)} districts rated. Lowest {vals.min():.2f}, median {np.median(vals):.2f}, highest {vals.max():.2f} {unit}; "
              f"Ghana cropland average {national:.2f} {unit}")
        cats = [{"key": f"n{i}", "label": FIFTHS[i], "note": "", "color": GREENS[i]} for i in range(5)] + \
               [{"key": "none", "label": "Too little cropland to rate", "note": "", "color": "#bdbdbd"}]
        districts = {}
        for s in ids:
            r, v = results[s]
            if s not in rated:
                districts[s] = {"name": r.shapeName, "cat": "none", "big": "–", "big_note": f"Less than {MIN_CROP_KM2:g} km² of cropland, so no rating.",
                                "tip": "Too little cropland to rate", "rows": [["Cropland (2021)", f"{crop[s]:,.1f} km²"]],
                                "v": [None, None], "c": ["none", "none"]}
                continue
            i = int(np.searchsorted(cuts, v[top], side="right"))
            cat = f"n{i}"
            det = [[f"Topsoil, 0 to 20 cm, on cropland", f"{fmt(v[top], dec)} {unit}"]]
            if v.get(sub) is not None:
                det.append(["Subsoil, 20 to 50 cm, on cropland", f"{fmt(v[sub], dec)} {unit}"])
            if v.get(allv) is not None:
                det.append(["Topsoil, all land in the district", f"{fmt(v[allv], dec)} {unit}"])
            det += [["Average for Ghana's cropland, topsoil", f"{fmt(national, dec)} {unit}"],
                    ["Rank among rated districts (1 = highest)", f"{rank[s]} of {len(rated)}"],
                    ["Cropland the average covers", f"{crop[s]:,.1f} km²"]]
            districts[s] = {"name": r.shapeName, "cat": cat, "big": f"{fmt(v[top], dec)} {unit}",
                            "big_note": f"{label.lower()} in the topsoil of cropland, {FIFTHS[i].lower()} of Ghana's districts",
                            "tip": f"{fmt(v[top], dec)} {unit}, {FIFTHS[i].lower()}",
                            "rows": det, "v": [round(v[top], 3), None if v.get(sub) is None else round(v[sub], 3)], "c": [cat, cat]}
        write_layer(key, {
            "label": short, "title": f"Soil {short.lower()} on cropland", "source": "iSDAsoil Africa v1 (Hengl and others, 2021) and ESA WorldCover 2021", "demo": False,
            "subtitle": f"Average {label.lower()} ({unit}) in the topsoil of each district's cropland",
            "build": BUILD,
            "categories": cats,
            "how": (f"Each district shows the average {label.lower()} in the top 20 cm of soil, taken only over the land that satellites saw as cropland in 2021. "
                    f"The soil values come from iSDAsoil, a computer model that predicted soil properties across Africa at 30 m from thousands of soil samples and satellite data. "
                    f"Districts are shaded by where they fall among Ghana's rated districts, in fifths. The shading compares districts with each other. It does not say whether the soil has enough {short.lower()} for a crop. "
                    f"Click a district for the exact figure, the deeper layer and the Ghana average."),
            "limits": [
                "These are model predictions, not measurements. They show broad patterns and can be wrong for a single farm or field. They are not a substitute for a soil test.",
                "The shading is relative. 'Highest fifth' means higher than most other districts, not high enough for a crop. Tinga Lens does not give fertiliser advice.",
                "The maps describe conditions as predicted from samples and satellite data of about 2001 to 2017. Fertiliser use, erosion and changes in farming since then are not shown.",
                ("Total nitrogen is all the nitrogen in the soil, mostly locked in organic matter. It is not the amount plants can take up." if key == "soiln"
                 else f"'Extractable' means the part a laboratory method can remove from the soil. Results depend on the method, and the model's values are not directly comparable with a particular laboratory's soil test."),
                "Averages are taken over cropland as seen at a 30 m grid. Where cropland is under-counted (see the Cropland map), the average may not reflect all farms in the district.",
                f"Districts with less than {MIN_CROP_KM2:g} km² of cropland are not rated.",
                "In dense forest the soil model is less reliable and can show stripes.",
            ],
            "credits": [{"text": "Soil nutrients: iSDAsoil, Hengl and others (2021), Scientific Reports 11, 6130, CC BY 4.0", "url": "https://www.isda-africa.com/isdasoil"},
                        {"text": "Cropland: ESA WorldCover 10 m 2021 v200, Zanaga and others (2022), CC BY 4.0", "url": "https://esa-worldcover.org/"}],
            "chart": {"kind": "bars", "unit": unit, "x": ["0 to 20 cm", "20 to 50 cm"],
                      "caption": f"Average {label.lower()} on cropland at two depths ({unit})", "top": "", "bottom": ""},
            "districts": districts,
        })


if __name__ == "__main__":
    main()
