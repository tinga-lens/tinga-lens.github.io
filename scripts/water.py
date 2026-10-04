#!/usr/bin/env python3
"""
Tinga Lens - surface water change.

Source: JRC Global Surface Water v1.4 (Pekel et al. 2016), which maps open water on every
cloud-free Landsat image from 1984 to 2021 at 30 m. Its "transition" map compares the first
and the last year in which each place was seen, and says whether permanent or seasonal water
appeared, disappeared or stayed.

For each district this script adds up those classes: permanent water gained and lost, and
seasonal water gained and lost. Nothing is modelled here.

The map is read through Google Earth Engine.

Run:
  python scripts/water.py
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
from floodhazard import retry  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 1                               # raise this to make the weekly update rebuild the layer
SOURCE = "JRC/GSW1_4/GlobalSurfaceWater"
PERIOD = (1984, 2021)
SCALE_M = 30
WORKERS = 4
SMALL = 0.1                             # a net change smaller than this many km2 is "little change"
# --------------------------------------------------------------------------

# transition classes in the source
CLASSES = {1: "permanent", 2: "new_permanent", 3: "lost_permanent", 4: "seasonal", 5: "new_seasonal",
           6: "lost_seasonal", 7: "seasonal_to_permanent", 8: "permanent_to_seasonal"}
CATS = [
    {"key": "w0", "label": "Lost more than 1 km²", "note": "", "color": "#8c510a", "lo": -1e12},
    {"key": "w1", "label": "Lost 0.1 to 1 km²", "note": "", "color": "#d8b365", "lo": -1},
    {"key": "w2", "label": "Little change", "note": "", "color": "#f1eee6", "lo": -SMALL},
    {"key": "w3", "label": "Gained 0.1 to 1 km²", "note": "", "color": "#9ecae1", "lo": SMALL},
    {"key": "w4", "label": "Gained 1 to 10 km²", "note": "", "color": "#4292c6", "lo": 1},
    {"key": "w5", "label": "Gained more than 10 km²", "note": "", "color": "#084594", "lo": 10},
]
STORE = CACHE / "water"
ee = None


def ask(shape):
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    tr = ee.Image(SOURCE).select("transition").unmask(0)
    km2 = ee.Image.pixelArea().divide(1e6)
    bands = [km2.rename("district")] + [km2.updateMask(tr.eq(c)).rename(name) for c, name in CLASSES.items()]
    out = retry(lambda: ee.Image.cat(bands).reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=SCALE_M,
                                                         maxPixels=1e11, tileScale=4).getInfo())
    return {k: float(v or 0) for k, v in out.items()}


def one(row):
    f = STORE / f"{row.shapeID}_b{BUILD}.json"
    if f.exists():
        return json.loads(f.read_text())
    res = ask(row.geometry.simplify(0.0003).buffer(0))
    f.write_text(json.dumps(res))
    return res


def signed(x):
    return f"{x:+,.1f} km²" if abs(x) >= 0.05 else "0.0 km²"


def main():
    global ee
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    rows = list(load_districts().itertuples())
    print(f"Surface water change: {len(rows)} districts", flush=True)
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

    first, last = PERIOD
    districts, tot = {}, {"gain": 0.0, "loss": 0.0}
    for sid, (name, r) in results.items():
        gain = r["new_permanent"] + r["seasonal_to_permanent"]
        loss = r["lost_permanent"] + r["permanent_to_seasonal"]
        net = gain - loss
        then = r["permanent"] + loss
        now = r["permanent"] + gain
        tot["gain"] += gain
        tot["loss"] += loss
        cat = [c["key"] for c in CATS if net >= c["lo"]][-1]
        if abs(net) < SMALL:
            cat = "w2"
        bars = [loss, gain, r["lost_seasonal"], r["new_seasonal"]]
        districts[sid] = {
            "name": name, "cat": cat, "big": signed(net),
            "big_note": f"net change in permanent water between the first and last years seen, {first} to {last}",
            "tip": f"Permanent water {signed(net)}",
            "rows": [
                ["Permanent water, first years", f"{then:,.1f} km²"],
                [f"Permanent water, {last}", f"{now:,.1f} km²"],
                ["New permanent water", f"{gain:,.1f} km²"],
                ["Permanent water lost", f"{loss:,.1f} km²"],
                ["New seasonal water", f"{r['new_seasonal']:,.1f} km²"],
                ["Seasonal water lost", f"{r['lost_seasonal']:,.1f} km²"],
            ],
            "v": [round(x, 2) for x in bars], "c": [cat] * len(bars),
        }
    print(f"Permanent water across Ghana: gained {tot['gain']:,.0f} km2, lost {tot['loss']:,.0f} km2")
    top = sorted(((num, d["name"]) for d in districts.values() for num in [float(d["big"].split()[0].replace(",", ""))]), reverse=True)
    print("Largest gains: " + "; ".join(f"{n} {a:+,.1f}" for a, n in top[:6]))
    print("Largest losses: " + "; ".join(f"{n} {a:+,.1f}" for a, n in top[-6:][::-1]))

    write_layer("water", {
        "label": "Surface water change", "title": "Surface water change", "source": "JRC Global Surface Water v1.4 (Landsat)", "demo": False,
        "subtitle": f"Permanent water gained or lost, {first} to {last}", "build": BUILD,
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Landsat satellites have photographed Ghana since {first}. The Global Surface Water project marked open water on every cloud-free image "
                f"up to {last}, and compared the first and the last year in which each 30 m piece of land was seen. Each district shows the net change in "
                f"permanent water, meaning water present all year: new permanent water minus permanent water lost. "
                f"Click a district for the amounts gained and lost, and for seasonal water."),
        "limits": [
            "New water is not always natural. Reservoirs such as Bui, small dams and dugouts, and water-filled mining pits all count as new permanent water.",
            "Clear Landsat images of Ghana are scarce before about 2000, so the \"first year\" differs from place to place and is often later than 1984.",
            f"The record ends in {last}. Changes since then are not shown.",
            "Water narrower than about 30 m, and water under trees or floating plants, is missed.",
            "Lake Volta's level rises and falls from year to year, so gains and losses along its shore partly reflect which years happened to be compared.",
            "The figure is surface area. It says nothing about depth, volume or water quality.",
        ],
        "credits": [{"text": "Surface water: Pekel et al. (2016), JRC Global Surface Water v1.4, European Commission Joint Research Centre and Google",
                     "url": "https://global-surface-water.appspot.com/"}],
        "chart": {"kind": "bars", "unit": "km²", "x": ["Permanent lost", "Permanent new", "Seasonal lost", "Seasonal new"],
                  "caption": "Water lost and gained (square kilometres).", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
