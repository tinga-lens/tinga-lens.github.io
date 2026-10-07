#!/usr/bin/env python3
"""
Tinga Lens - cropland and soil properties by district (nitrogen, phosphorus, potassium, pH, organic matter, sand, clay, bulk density).

Sources, both read through Google Earth Engine:
  * Cropland: ESA WorldCover 10 m v200 (2021), class 40 "Cropland".
  * Soil: iSDAsoil, 30 m maps of Africa (Hengl et al. 2021, CC BY 4.0), at 0-20 cm and 20-50 cm: total nitrogen,
    extractable phosphorus and potassium, pH, organic carbon, sand, clay and bulk density.

Nothing is modelled here. The script adds up and averages the two published datasets by district:
  * how much of each district is cropland (square kilometres and share of land);
  * the average of each soil property over all of the district's land (the value that colours the maps, so every
    district is compared on the same basis) and, where there is enough mapped cropland, on its cropland.
The nutrient maps are themselves computer predictions, and the site says so.

Districts are shaded by where they fall among Ghana's 260 districts (fifths). No farm-advice
thresholds are used, because those depend on the crop and on the soil test method.
All values are also written to data/soil-by-district.csv.

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
BUILD = 2                               # raise this to make the weekly update rebuild the layers
WORLDCOVER = "ESA/WorldCover/v200"
CROPLAND_CLASS = 40
SOIL = "ISDASOIL/Africa/v1/"
OM_FROM_OC = 0.1724                     # organic matter (%) = organic carbon (g/kg) x 1.724 / 10
# key: (asset, kind, divisor, scale, unit, decimals, label, short, plausible range for a district average)
#   kind "log": value = exp(x / divisor) - 1 ; kind "lin": value = x / divisor ; scale: multiplied in afterwards
PROPS = {
    "soiln":    ("nitrogen_total",        "log", 100, 1,          "g/kg", 2, "Total nitrogen",        "Nitrogen",       (0.2, 6)),
    "soilp":    ("phosphorus_extractable", "log", 10, 1,          "ppm",  1, "Extractable phosphorus", "Phosphorus",    (1, 40)),
    "soilk":    ("potassium_extractable",  "log", 10, 1,          "ppm",  0, "Extractable potassium",  "Potassium",     (10, 400)),
    "soilph":   ("ph",                     "lin", 10, 1,          "",     1, "Soil pH",                "pH",            (4, 9)),
    "soilom":   ("carbon_organic",         "log", 10, OM_FROM_OC, "%",    1, "Soil organic matter, estimated from organic carbon", "Organic matter", (0.3, 10)),
    "soilclay": ("clay_content",           "lin", 1,  1,          "%",    0, "Clay content",           "Clay",          (1, 80)),
    "soilsand": ("sand_content",           "lin", 1,  1,          "%",    0, "Sand content",           "Sand",          (5, 95)),
    "soilbd":   ("bulk_density",           "lin", 100, 1,         "g/cm³", 2, "Bulk density",          "Bulk density",  (0.7, 2.0)),
}
MIN_CROP_KM2 = 1.0                      # districts with less cropland than this get no cropland-only soil value
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
    """Bands <key>_top (0-20 cm) and <key>_sub (20-50 cm) for every property, back-transformed to their units."""
    bands = []
    for key, (asset, kind, div, scale, *_rest) in PROPS.items():
        img = ee.Image(SOIL + asset)
        for src, tag in (("mean_0_20", "top"), ("mean_20_50", "sub")):
            v = img.select(src).divide(div)
            if kind == "log":
                v = v.exp().subtract(1)
            bands.append(v.multiply(scale).rename(f"{key}_{tag}"))
    return ee.Image.cat(bands)


def ask(shape):
    """One district -> cropland area (km2) and the mean of each soil property (on cropland, and over all land)."""
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    crop = ee.ImageCollection(WORLDCOVER).first().select("Map").eq(CROPLAND_CLASS)
    area = ee.Image.pixelArea().divide(1e6).updateMask(crop).rename("crop_km2")
    out = retry(lambda: area.reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=CROP_SCALE_M,
                                          maxPixels=1e12, tileScale=8).getInfo())
    res = {"crop_km2": float((out or {}).get("crop_km2") or 0)}
    soil = soil_image()
    names = [f"{k}_{t}" for k in PROPS for t in ("top", "sub")]
    onfarm = soil.updateMask(crop).rename([f"{n}_crop" for n in names])
    allland = soil.select([f"{k}_top" for k in PROPS]).rename([f"{k}_all" for k in PROPS])
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
        short = {k: v[7] for k, v in PROPS.items()}
        print(f"{'District':26s} {'land km2':>8s} {'crop km2':>8s} | " + " ".join(f"{short[k][:7]:>7s}" for k in PROPS) + "   (district-wide values)")
        for sid, (r, v) in results.items():
            cells = " ".join("      -" if v.get(f"{k}_all") is None else f"{v[f'{k}_all']:7.2f}" for k in PROPS)
            print(f"{r.shapeName[:26]:26s} {r.land_km2:8.0f} {v['crop_km2']:8.1f} | {cells}")
        print("Plausible ranges, for checking the units:  " + "; ".join(f"{PROPS[k][7]} {PROPS[k][9][0]} to {PROPS[k][9][1]} {PROPS[k][4]}" for k in PROPS))
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

    # ---- soil layers: every district, coloured by its all-land topsoil average ----
    import csv
    from common import DATA
    regions = json.loads((DATA / "regions.json").read_text()) if (DATA / "regions.json").exists() else {}
    tot_land = sum(land.values())
    table = {}
    for key, (asset, kind, div, scale, unit, dec, label, short, (lo, hi)) in PROPS.items():
        top, sub, allv = (f"{key}_top_crop", f"{key}_sub_crop", f"{key}_all")
        have = [s for s in ids if results[s][1].get(allv) is not None]
        if not have:
            print(f"{label}: no values, layer skipped")
            continue
        vals = np.array([results[s][1][allv] for s in have])
        med = float(np.median(vals))
        if not (lo <= med <= hi):
            print(f"WARNING {label}: median {med:.3g} {unit} is outside the plausible range {lo} to {hi}. The units may be wrong, so this layer is NOT published.")
            continue
        cuts = np.percentile(vals, [20, 40, 60, 80])
        national = float(np.average(vals, weights=[land[s] for s in have]))
        order_v = sorted(have, key=lambda s: -results[s][1][allv])
        rank = {s: i + 1 for i, s in enumerate(order_v)}
        print(f"{label}: {len(have)} districts. Lowest {vals.min():.2f}, median {med:.2f}, highest {vals.max():.2f} {unit}; Ghana (area-weighted) {national:.2f}")
        cats = [{"key": f"n{i}", "label": FIFTHS[i], "note": "", "color": GREENS[i]} for i in range(5)] + \
               [{"key": "none", "label": "No estimate", "note": "", "color": "#bdbdbd"}]
        unit_s = f" {unit}" if unit else ""
        lc = label if "pH" in label else label.lower()
        districts = {}
        for s in ids:
            r, v = results[s]
            if s not in have:
                districts[s] = {"name": r.shapeName, "cat": "none", "basis": "none", "big": "–", "big_note": "No soil estimate available for this district.",
                                "tip": "No estimate", "rows": [], "v": [None, None, None], "c": ["none"] * 3}
                continue
            i = int(np.searchsorted(cuts, v[allv], side="right"))
            cat = f"n{i}"
            has_crop = crop[s] >= MIN_CROP_KM2 and v.get(top) is not None
            det = [["All land, 0 to 20 cm", f"{fmt(v[allv], dec)}{unit_s}"]]
            if key == "soilom":
                det.append(["Organic carbon, all land", f"{v[allv] / OM_FROM_OC:,.1f} g/kg"])
            if has_crop:
                det.append([f"Cropland, 0 to 20 cm ({crop[s]:,.0f} km²)", f"{fmt(v[top], dec)}{unit_s}"])
                if v.get(sub) is not None:
                    det.append(["Cropland, 20 to 50 cm", f"{fmt(v[sub], dec)}{unit_s}"])
            else:
                det.append(["Cropland, 0 to 20 cm", f"None ({crop[s]:,.1f} km² mapped)"])
            det += [["Ghana average, all land", f"{fmt(national, dec)}{unit_s}"],
                    ["Rank (1 = highest)", f"{rank[s]} of {len(have)}"]]
            districts[s] = {"name": r.shapeName, "cat": cat, "basis": "all_land", "crop_km2": round(crop[s], 1),
                            "big": f"{fmt(v[allv], dec)}{unit_s}",
                            "big_note": f"{lc} in the topsoil, averaged over all land in the district; {FIFTHS[i].lower()} of Ghana's districts",
                            "tip": f"{fmt(v[allv], dec)}{unit_s}, {FIFTHS[i].lower()}",
                            "rows": det,
                            "v": [round(v[allv], 3), round(v[top], 3) if has_crop else None, round(v[sub], 3) if has_crop and v.get(sub) is not None else None],
                            "c": [cat] * 3}
            table.setdefault(s, {"District": r.shapeName, "Region": regions.get(s, ""), "Land km2": round(land[s]), "Mapped cropland km2": round(crop[s], 1)})
            table[s][f"{short}: all land, 0-20 cm ({unit})" if unit else f"{short}: all land, 0-20 cm"] = round(v[allv], 3)
            table[s][f"{short}: cropland, 0-20 cm ({unit})" if unit else f"{short}: cropland, 0-20 cm"] = round(v[top], 3) if has_crop else ""
            table[s][f"{short}: cropland, 20-50 cm ({unit})" if unit else f"{short}: cropland, 20-50 cm"] = round(v[sub], 3) if has_crop and v.get(sub) is not None else ""
        write_layer(key, {
            "label": short, "title": f"Soil {short if short == 'pH' else short.lower()}", "source": "iSDAsoil Africa v1 (Hengl and others, 2021)", "demo": False,
            "subtitle": f"Average {lc}{f' ({unit})' if unit else ''} in the topsoil of each district, over all its land",
            "build": BUILD,
            "categories": cats,
            "how": (f"Each district shows the average {lc} in the top 20 cm of soil over all of its land, so every district is compared on the same basis. "
                    f"The values come from iSDAsoil, a computer model that predicted soil properties across Africa at 30 m from thousands of soil samples and satellite data. "
                    f"Districts are shaded by where they fall among Ghana's 260 districts, in fifths. The shading compares districts with each other. It does not say whether the soil suits a crop. "
                    f"Click a district for the exact figure, the average over mapped cropland and the subsoil where there is enough cropland, and the Ghana average. "
                    f"All soil values for every district can be downloaded as one table."),
            "limits": [
                "These are model predictions, not measurements. They show broad patterns and can be wrong for a single farm or field. They are not a substitute for a soil test on the site.",
                "The shading is relative. 'Highest fifth' means higher than most other districts, not high enough for a crop, and it does not mean better land. Tinga Lens does not give fertiliser or investment advice.",
                "The district value averages all land, including forest, wetlands and settlements, so it can differ from the soil under farms. The cropland-only value is shown in the panel where the district has at least 1 km² of mapped cropland.",
                "Cropland comes from ESA WorldCover, which often classes tree crops such as cocoa and oil palm as tree cover. In the forest belt the cropland-only value is therefore missing or covers only part of the farmland.",
                "The maps describe conditions as predicted from samples and satellite data of about 2001 to 2017. Fertiliser use, erosion and changes in farming since then are not shown.",
                {"soiln": "Total nitrogen is all the nitrogen in the soil, mostly locked in organic matter. It is not the amount plants can take up.",
                 "soilp": "'Extractable' means the part a laboratory method can remove from the soil. Results depend on the method, and the model's values are not directly comparable with a particular laboratory's soil test.",
                 "soilk": "'Extractable' means the part a laboratory method can remove from the soil. Results depend on the method, and the model's values are not directly comparable with a particular laboratory's soil test.",
                 "soilph": "pH is a model estimate of the acidity of the soil. A district average can hide large differences between fields.",
                 "soilom": "Organic matter is not mapped directly. It is estimated as organic carbon times 1.724, a common conversion that varies between soils.",
                 "soilclay": "Texture (clay and sand) is a prediction at 30 m. Fine detail, such as a sandy ridge or a clay hollow, is smoothed away.",
                 "soilsand": "Texture (clay and sand) is a prediction at 30 m. Fine detail, such as a sandy ridge or a clay hollow, is smoothed away.",
                 "soilbd": "Bulk density is a model prediction. It is mostly of use to soil specialists, for example for compaction and water movement."}[key],
                "In dense forest the soil model is less reliable and can show stripes.",
            ],
            "credits": [{"text": "Soil: iSDAsoil, Hengl and others (2021), Scientific Reports 11, 6130, CC BY 4.0", "url": "https://www.isda-africa.com/isdasoil"},
                        {"text": "Cropland: ESA WorldCover 10 m 2021 v200, Zanaga and others (2022), CC BY 4.0", "url": "https://esa-worldcover.org/"}],
            "chart": {"kind": "bars", "unit": unit, "x": ["All land, 0 to 20 cm", "Cropland, 0 to 20 cm", "Cropland, 20 to 50 cm"],
                      "caption": f"Average {lc} in the district{f' ({unit})' if unit else ''}. Cropland bars appear only where there is enough mapped cropland.", "top": "", "bottom": ""},
            "districts": districts,
        })
    if table:
        cols = list(next(iter(table.values())).keys())
        for row in table.values():
            for c in row:
                if c not in cols:
                    cols.append(c)
        with open(DATA / "soil-by-district.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for row in sorted(table.values(), key=lambda r: r["District"]):
                w.writerow(row)
            f.write("\n")
            f.write('"Source: iSDAsoil Africa v1 (Hengl and others, 2021, CC BY 4.0), averaged by district by Tinga Lens (tingalens.org). Model predictions, not soil tests. Cropland: ESA WorldCover 2021."\n')
        print(f"Wrote data/soil-by-district.csv: {len(table)} districts, {len(cols)} columns")


if __name__ == "__main__":
    main()
