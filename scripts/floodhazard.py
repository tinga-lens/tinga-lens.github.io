#!/usr/bin/env python3
"""
Tinga Lens - river flood hazard.

Source: Global river flood hazard maps v2.1 from the European Commission's Joint Research
Centre (JRC), part of the Copernicus Emergency Management Service (GloFAS). The maps are a
computer model of how far and how deep large rivers would spread in floods of seven sizes,
from one expected about every 10 years to one expected about every 500 years, on a 90 m grid.

For each district this script reports the land area inside the flooded zone for each flood
size, and for the 1-in-100-year flood the people and built-up area inside it
(Global Human Settlement Layer, 2020).

The maps are read through Google Earth Engine. Nothing is modelled here: the script only
adds up the published maps by district.

Run:
  python scripts/floodhazard.py
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shapely.geometry import mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, load_districts, write_layer  # noqa: E402
from ee_check import ee_login  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 1                               # raise this to make the weekly update rebuild the layer
HAZARD = "JRC/CEMS_GLOFAS/FloodHazard/v2_1"
POPULATION = "JRC/GHSL/P2023A/GHS_POP/2020"
BUILT = "JRC/GHSL/P2023A/GHS_BUILT_S/2020"
PERIODS = [10, 20, 50, 75, 100, 200, 500]   # flood sizes in the source: once in this many years on average
MAIN = 100                              # the flood size shown on the map
DEEP_M = 1.0                            # "deep" water: at least this many metres
SCALE_M = 90
WORKERS = 4
# --------------------------------------------------------------------------

CATS = [
    {"key": "h0", "label": "None", "note": "", "color": "#f1eee6", "max": 0.1},
    {"key": "h1", "label": "Under 2% of the land", "note": "", "color": "#fed98e", "max": 2},
    {"key": "h2", "label": "2 to 5%", "note": "", "color": "#fe9929", "max": 5},
    {"key": "h3", "label": "5 to 10%", "note": "", "color": "#d95f0e", "max": 10},
    {"key": "h4", "label": "Over 10%", "note": "", "color": "#993404", "max": 1e12},
]
STORE = CACHE / "floodhazard"
ee = None


def retry(fn):
    for attempt in range(1, 6):
        try:
            return fn()
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in ("too many", "429", "rate", "unavailable", "internal", "deadline", "connection", "reset", "timed out")) and attempt < 5:
                time.sleep(20 * attempt)
                continue
            raise


def ask(shape):
    """One district -> areas in km2 for each flood size, and people and built-up area inside the main flood zone."""
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    haz = ee.ImageCollection(HAZARD).filterBounds(geom).mosaic()
    land = haz.select("permanent_water_class").unmask(0).neq(1)       # rivers and lakes themselves are not counted
    km2 = ee.Image.pixelArea().divide(1e6)
    zone = {p: haz.select(f"RP{p}_depth").unmask(0).gt(0).And(land) for p in PERIODS}
    bands = [km2.rename("district"), km2.updateMask(land).rename("land")]
    bands += [km2.updateMask(zone[p]).rename(f"rp{p}") for p in PERIODS]
    bands += [km2.updateMask(haz.select(f"RP{MAIN}_depth").unmask(0).gte(DEEP_M).And(land)).rename("deep")]
    out = retry(lambda: ee.Image.cat(bands).reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=SCALE_M,
                                                         maxPixels=1e11, tileScale=4).getInfo())
    out = {k: float(v or 0) for k, v in out.items()}
    try:        # people and buildings, counted on the population grid so that no one is counted twice
        pop = ee.Image(POPULATION).select("population_count")
        built = ee.Image(BUILT).select("built_surface")
        b2 = ee.Image.cat([pop.rename("pop"), pop.updateMask(zone[MAIN]).rename("pop_in"),
                           built.rename("built"), built.updateMask(zone[MAIN]).rename("built_in")])
        ex = retry(lambda: b2.reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, crs=pop.projection(),
                                           maxPixels=1e11, tileScale=4).getInfo())
        out.update({k: float(v or 0) for k, v in ex.items()})
    except Exception as e:
        out["exposure_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


def one(row):
    f = STORE / f"{row.shapeID}_b{BUILD}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = ask(row.geometry.simplify(0.0003).buffer(0))
    if "exposure_error" not in res:
        f.write_text(json.dumps(res))
    return res


def people(n):
    return "fewer than 100" if n < 100 else f"about {round(n, -2):,.0f}" if n < 10000 else f"about {round(n, -3):,.0f}"


def main():
    global ee
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    rows = list(load_districts().itertuples())
    print(f"River flood hazard: {len(rows)} districts", flush=True)
    t0, results, failed = time.time(), {}, []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(one, r): r for r in rows}
        for k, (fut, r) in enumerate(futures.items(), 1):
            try:
                results[r.shapeID] = (r.shapeName, fut.result())
            except Exception as e:
                failed.append(r.shapeName)
                print(f"  FAILED {r.shapeName}: {type(e).__name__}: {str(e)[:300]}", flush=True)
            if k % 40 == 0:
                print(f"  {k} of {len(rows)} districts, {(time.time() - t0) / 60:.1f} min", flush=True)
    if failed:
        sys.exit(f"{len(failed)} districts failed ({', '.join(failed[:8])}). Finished districts are saved; run again to retry the rest. Nothing was published.")

    errors = [r["exposure_error"] for _, r in results.values() if "exposure_error" in r]
    exposure = not errors
    if errors:
        print(f"People and built-up area could not be read for {len(errors)} districts, so they are left out. First error: {errors[0]}")

    districts, tot = {}, {"area": 0.0, "pop": 0.0}
    for sid, (name, r) in results.items():
        if not r.get("land"):
            districts[sid] = {"name": name, "cat": "h0", "big": "–", "big_note": "No value for this district.", "tip": "No value",
                              "rows": [], "v": [0] * len(PERIODS), "c": ["h0"] * len(PERIODS)}
            continue
        area = r[f"rp{MAIN}"]
        pct = area / r["land"] * 100
        cat = next(c["key"] for c in CATS if pct < c["max"])
        tot["area"] += area
        show = lambda x: f"{x:,.1f} km²" if x >= 0.05 else "None"
        detail = [
            ["Land inside that flood zone", show(area)],
            [f"Of which {DEEP_M:g} m deep or more", show(r["deep"])],
            ["In a 1-in-10-year flood", show(r["rp10"])],
            ["In a 1-in-500-year flood", show(r["rp500"])],
        ]
        if exposure:
            tot["pop"] += r["pop_in"]
            detail += [
                ["People living inside the 1-in-100-year zone (2020)", people(r["pop_in"]) + (f", {r['pop_in'] / r['pop'] * 100:.0f}% of the district" if r["pop"] > 0 else "")],
                ["Built-up area inside the zone (2020)", f"{r['built_in'] / 1e6:,.2f} km²"],
            ]
        districts[sid] = {
            "name": name, "cat": cat, "big": f"{pct:.1f}%",
            "big_note": f"of the district's land lies inside the modelled 1-in-{MAIN}-year river flood zone",
            "tip": f"{pct:.1f}% of the land, {area:,.0f} km²",
            "rows": detail, "v": [round(r[f"rp{p}"], 1) for p in PERIODS], "c": [cat] * len(PERIODS),
        }
    print(f"Inside the 1-in-{MAIN}-year zone: {tot['area']:,.0f} km2 of land" + (f", about {tot['pop']:,.0f} people" if exposure else ""))
    top = sorted(((d["v"][PERIODS.index(MAIN)], d["name"], d["big"]) for d in districts.values()), reverse=True)[:8]
    print("Largest areas: " + "; ".join(f"{n} {a:,.0f} km2 ({b})" for a, n, b in top))

    write_layer("floodhazard", {
        "label": "River flood hazard", "title": "River flood hazard", "source": "JRC global river flood hazard maps v2.1", "demo": False,
        "subtitle": f"Share of each district's land inside the modelled 1-in-{MAIN}-year river flood zone",
        "build": BUILD, "exposure": exposure,
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"This map comes from a computer model, not from satellite observations of floods. The European Commission's Joint Research Centre "
                f"modelled how far large rivers would spread in floods of different sizes, on a 90 m grid. A 1-in-{MAIN}-year flood is one so large "
                f"that it has about a 1% chance of happening in any year. Each district shows the share of its land inside that modelled flood zone. "
                f"Rivers and lakes themselves are not counted. Click a district for other flood sizes"
                + (", and for the people and built-up area inside the zone." if exposure else ".")),
        "limits": [
            "This is a model result. It shows where river water could reach in a flood of a given size, not where it has flooded or will flood next.",
            "Only larger rivers are modelled. Small streams, blocked drains and street flooding in towns are not included, so city flooding such as Accra's does not appear.",
            "Flooding from the sea is not included.",
            "The source documentation does not say that flood defences or dam operations are represented. Do not assume the Akosombo, Kpong, Bui or Bagre dams are taken into account.",
            "The model works on a 90 m grid with global elevation data. It can be wrong for a single village or field.",
            "People and built-up area come from the Global Human Settlement Layer for 2020, which spreads census counts over mapped buildings. They are estimates, rounded here." if exposure else "People and buildings inside the zone are not reported yet.",
            "This is hazard and exposure, not risk: it says nothing about how well people can cope with a flood.",
        ],
        "credits": [{"text": "Flood hazard: Baugh et al. (2024), Global river flood hazard maps v2.1, European Commission Joint Research Centre",
                     "url": "http://data.europa.eu/89h/jrc-floods-floodmapgl_rp50y-tif"}]
                   + ([{"text": "People and built-up area: Global Human Settlement Layer (GHS-POP and GHS-BUILT-S R2023A), European Commission JRC",
                        "url": "https://human-settlement.emergency.copernicus.eu/"}] if exposure else []),
        "chart": {"kind": "bars", "unit": "km²", "x": [f"1 in {p}" for p in PERIODS],
                  "caption": "Land inside the flood zone for each flood size (square kilometres). Larger, rarer floods are to the right.", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
