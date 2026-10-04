#!/usr/bin/env python3
"""
Tinga Lens - flood-prone land (trial).

Uses Google Earth Engine to look through ten years of Sentinel-1 radar images and count,
for every 40 m piece of land, in how many years it was seen under water.

How one radar image is read:
  water     = radar return (VV) below a threshold
  flooded   = water, and clearly darker than that place normally is on the same
              satellite track (its median over REF_YEARS)
  left out  = land that is normally water (JRC Global Surface Water occurrence of
              OCCURRENCE_PCT % or more) and slopes steeper than SLOPE_DEG degrees,
              where radar shadow looks like water
The thresholds, the months used and how many images in a year must agree are still being
chosen. VARIANTS lists the settings the trial compares, against the 2023 lower Volta
flood as mapped by Copernicus GFM.

For each district it reports the land area flooded in at least 1, 2, 3 and 5 of the years,
and the flooded area in each year.

This first version is a TRIAL. It runs a short list of districts, prints the results
and saves them in cache/. It does not publish anything on the site.

Run:
  FLOODPRONE=pilot python scripts/floodprone.py
"""
import datetime as dt
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, DATA, load_districts  # noqa: E402
from ee_check import ee_login  # noqa: E402

# ---- settings you may want to change -------------------------------------
FIRST_YEAR = 2016                       # first full year of Sentinel-1 over Ghana
LAST_YEAR = dt.date.today().year - 1    # last complete year
REF_YEARS = ("2019-01-01", "2022-01-01")  # years that define what a place normally looks like
NOISE_DB = -35.0                        # darker than this is image-edge noise, not water
OCCURRENCE_PCT = 25                     # land that is water this often or more is not counted as flooding
SLOPE_DEG = 5                           # steeper land is left out
SCALE_M = 40                            # size of the pieces of land that are counted
MIN_REF_IMAGES = 10                     # a satellite track needs this many images in REF_YEARS
WORKERS = 4                             # districts worked on at the same time
# Settings being compared in the trial. months = first and last month used; water = VV below this (dB) looks
# like open water; drop = and it must be this much darker than normal; hits = images in one year that must
# show it; vh = if set, the second radar channel (VH) must also be below this.
VARIANTS = {
    "A": {"months": (4, 11), "water": -17.0, "drop": 3.0, "hits": 1, "vh": None},
    "B": {"months": (6, 10), "water": -18.0, "drop": 3.0, "hits": 1, "vh": None},
    "C": {"months": (6, 10), "water": -18.0, "drop": 3.0, "hits": 2, "vh": None},
    "D": {"months": (6, 10), "water": -20.0, "drop": 4.0, "hits": 2, "vh": None},
    "E": {"months": (6, 10), "water": -18.0, "drop": 3.0, "hits": 2, "vh": -25.0},
    "F": {"months": (6, 10), "water": -20.0, "drop": 4.0, "hits": 3, "vh": -26.0},
}
EVENT = ("2023-09-15", "2023-11-16")    # the lower Volta flood already on the site, for comparison
PILOT = ["North Tongu", "Central Tongu", "South Tongu", "Ada East", "Ada West", "Asuogyaman", "Keta Municipal",
         "Talensi", "Bawku West", "Builsa South", "Central Gonja", "Kwahu Afram Plains North", "Accra Metropolis"]
# --------------------------------------------------------------------------

YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
STEPS = [1, 2, 3, 5]
SETTINGS = [FIRST_YEAR, LAST_YEAR, REF_YEARS, NOISE_DB, OCCURRENCE_PCT, SLOPE_DEG, SCALE_M, MIN_REF_IMAGES, EVENT, 2]


def sign(v):
    return hashlib.md5(json.dumps([SETTINGS, v], sort_keys=True).encode()).hexdigest()[:10]


STORE = CACHE / "floodprone"

ee = None


def flag_maker(ref, v):
    """One radar image -> 1 where it shows flooding, judged against the track's normal picture."""
    def flag(im):
        vv = im.select("VV")
        f = vv.lt(v["water"]).And(vv.subtract(ref.select("VV")).lt(-v["drop"])).And(vv.gt(NOISE_DB))
        if v["vh"] is not None:
            f = f.And(im.select("VH").lt(v["vh"]))
        return f.rename("f").toByte()
    return flag


def ask(shape, v):
    """Send one piece of land to Earth Engine; returns a dict of areas in km2 and the number of images used."""
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(geom)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV")))
    if v["vh"] is not None:
        s1 = s1.filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")).select(["VV", "VH"])
    else:
        s1 = s1.select("VV")
    months = ee.Filter.calendarRange(v["months"][0], v["months"][1], "month")
    season = s1.filterDate(f"{FIRST_YEAR}-01-01", f"{LAST_YEAR + 1}-01-01").filter(months)
    counts = ee.Dictionary({"season": season.aggregate_histogram("relativeOrbitNumber_start"),
                            "ref": s1.filterDate(*REF_YEARS).aggregate_histogram("relativeOrbitNumber_start")}).getInfo()
    tracks = [int(float(k)) for k, n in counts["ref"].items() if n >= MIN_REF_IMAGES and k in counts["season"]]
    images = sum(counts["season"][k] for k in counts["season"] if int(float(k)) in tracks)
    if not tracks:
        return {"images": 0}

    zero = ee.ImageCollection([ee.Image(0).rename("f").toByte()])
    per_year = {y: zero for y in YEARS}
    event = zero
    for t in tracks:
        on_track = s1.filter(ee.Filter.eq("relativeOrbitNumber_start", t))
        flag = flag_maker(on_track.filterDate(*REF_YEARS).median(), v)
        in_season = on_track.filter(months)
        event = event.merge(on_track.filterDate(*EVENT).map(flag))
        for y in YEARS:
            per_year[y] = per_year[y].merge(in_season.filterDate(f"{y}-01-01", f"{y + 1}-01-01").map(flag))
    year_flag = {y: per_year[y].sum().gte(v["hits"]) for y in YEARS}
    n_years = ee.ImageCollection([year_flag[y] for y in YEARS]).sum()

    often_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0).gte(OCCURRENCE_PCT)
    steep = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).unmask(0).gt(SLOPE_DEG)
    counted = often_water.Or(steep).Not()
    km2 = ee.Image.pixelArea().divide(1e6)

    bands = [km2.rename("district"), km2.updateMask(counted).rename("counted")]
    bands += [km2.updateMask(counted.And(n_years.gte(k))).rename(f"in{k}") for k in STEPS]
    bands += [km2.updateMask(counted.And(year_flag[y])).rename(f"y{y}") for y in YEARS]
    bands += [km2.updateMask(counted.And(event.max())).rename("event")]
    out = ee.Image.cat(bands).reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=SCALE_M,
                                           maxPixels=1e11, tileScale=4).getInfo()
    out = {k: float(v or 0) for k, v in out.items()}
    out["images"] = images
    return out


def measure(shape, v, depth=0):
    """Ask for one piece; if Earth Engine says it is too big, cut it in four and add the answers."""
    for attempt in range(1, 6):
        try:
            return ask(shape, v)
        except Exception as e:
            msg = str(e).lower()
            if ("timed out" in msg or "memory" in msg or "too large" in msg) and depth < 3:
                w, s, e_, n = shape.bounds
                mx, my = (w + e_) / 2, (s + n) / 2
                total = {}
                for q in (box(w, s, mx, my), box(mx, s, e_, my), box(w, my, mx, n), box(mx, my, e_, n)):
                    part = shape.intersection(q)
                    if part.is_empty or part.area == 0:
                        continue
                    for k, v in measure(part, v, depth + 1).items():
                        total[k] = max(total.get(k, 0), v) if k == "images" else total.get(k, 0) + v
                return total
            if any(x in msg for x in ("too many", "429", "rate", "unavailable", "internal", "deadline", "connection", "reset")) and attempt < 5:
                time.sleep(20 * attempt)
                continue
            raise


def one(row, v):
    f = STORE / f"{row.shapeID}_{sign(v)}.json"
    if f.exists():
        return row.shapeName, json.loads(f.read_text()), 0.0
    t0 = time.time()
    res = measure(row.geometry.simplify(0.0003).buffer(0), v)
    f.write_text(json.dumps(res))
    return row.shapeName, res, time.time() - t0


def gfm_event():
    """Flooded area per district for the same event from the layer already on the site (Copernicus GFM)."""
    try:
        d = json.loads((DATA / "flood.json").read_text())["districts"]
        return {x["name"]: float(x["big"].split()[0].replace(",", "")) if x["big"][:1].isdigit() else 0.0
                for x in d.values() if x["cat"] != "out"}
    except Exception:
        return {}


def main():
    global ee
    if os.environ.get("FLOODPRONE", "pilot").lower() != "pilot":
        sys.exit("Only the trial is available so far. Run with FLOODPRONE=pilot.")
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    rows = [r for r in load_districts().itertuples() if r.shapeName in PILOT]
    gfm = gfm_event()
    print(f"Trial: {len(rows)} districts, {FIRST_YEAR} to {LAST_YEAR}, {SCALE_M} m, {len(VARIANTS)} settings", flush=True)
    t0, failed = time.time(), []
    for key, v in VARIANTS.items():
        done = []
        with ThreadPoolExecutor(WORKERS) as pool:
            futures = {pool.submit(one, r, v): r.shapeName for r in rows}
            for fut in futures:
                try:
                    done.append(fut.result())
                except Exception as e:
                    failed.append(f"{key}/{futures[fut]}")
                    print(f"  FAILED {key} {futures[fut]}: {type(e).__name__}: {str(e)[:300]}", flush=True)
        print(f"\n=== Setting {key}: months {v['months'][0]}-{v['months'][1]}, VV below {v['water']} dB, drop {v['drop']} dB, "
              f"{v['hits']} image(s) a year" + (f", VH below {v['vh']} dB" if v["vh"] is not None else "") + " ===")
        print(f"{'district':26}{'counted':>8}{'in 1':>8}{'in 2':>8}{'in 3':>8}{'in 5':>8}{'yr mean':>8}{'yr max':>8}{'2023ev':>8}{'GFM':>7}{'images':>7}")
        for name, r, secs in sorted(done):
            if not r.get("images"):
                print(f"{name:26}  no usable radar images")
                continue
            ys = [r[f"y{y}"] for y in YEARS]
            g = f"{gfm[name]:7.1f}" if name in gfm else "      -"
            print(f"{name:26}{r['counted']:8.0f}" + "".join(f"{r[f'in{k}']:8.1f}" for k in STEPS)
                  + f"{sum(ys) / len(ys):8.1f}{max(ys):8.1f}{r['event']:8.1f}{g}{r['images']:7d}", flush=True)
    print("\nAreas in km2. 'in N' = flooded in at least N of the years. 'yr mean' and 'yr max' = flooded area in a year."
          "\n'2023ev' = seen flooded on any image, 15 Sep to 15 Nov 2023. 'GFM' = the figure on the site for that event.")
    print(f"Trial finished in {(time.time() - t0) / 60:.1f} minutes. Nothing was published on the site.")
    if failed:
        sys.exit("These failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
