#!/usr/bin/env python3
"""
Tinga Lens - flood-prone land (trial).

Uses Google Earth Engine to look through ten years of Sentinel-1 radar images and count,
for every 40 m piece of land, in how many years it was seen under water.

How one radar image is read:
  water     = radar return (VV) below WATER_DB
  flooded   = water, and at least DROP_DB darker than that place normally is on the same
              satellite track (its median over REF_YEARS)
  left out  = land that is normally water (JRC Global Surface Water occurrence of
              OCCURRENCE_PCT % or more) and slopes steeper than SLOPE_DEG degrees,
              where radar shadow looks like water
Only images from SEASON (the months when Ghana floods) are used, because dry bare soil
in the dry season can look as dark as water.

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
from common import CACHE, load_districts  # noqa: E402
from ee_check import ee_login  # noqa: E402

# ---- settings you may want to change -------------------------------------
FIRST_YEAR = 2016                       # first full year of Sentinel-1 over Ghana
LAST_YEAR = dt.date.today().year - 1    # last complete year
SEASON = (4, 11)                        # months used: April to November
REF_YEARS = ("2019-01-01", "2022-01-01")  # years that define what a place normally looks like
WATER_DB = -17.0                        # VV below this looks like open water
DROP_DB = 3.0                           # and it must be this much darker than normal
NOISE_DB = -35.0                        # darker than this is image-edge noise, not water
OCCURRENCE_PCT = 25                     # land that is water this often or more is not counted as flooding
SLOPE_DEG = 5                           # steeper land is left out
SCALE_M = 40                            # size of the pieces of land that are counted
MIN_REF_IMAGES = 10                     # a satellite track needs this many images in REF_YEARS
WORKERS = 4                             # districts worked on at the same time
PILOT = ["North Tongu", "Central Tongu", "South Tongu", "Ada East", "Ada West", "Asuogyaman", "Keta Municipal",
         "Talensi", "Bawku West", "Builsa South", "Central Gonja", "Kwahu Afram Plains North", "Accra Metropolis"]
# --------------------------------------------------------------------------

YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
STEPS = [1, 2, 3, 5]
SETTINGS = [FIRST_YEAR, LAST_YEAR, SEASON, REF_YEARS, WATER_DB, DROP_DB, NOISE_DB, OCCURRENCE_PCT, SLOPE_DEG, SCALE_M, MIN_REF_IMAGES]
SIGN = hashlib.md5(json.dumps(SETTINGS).encode()).hexdigest()[:10]
STORE = CACHE / "floodprone"

ee = None


def flag_maker(ref):
    """One radar image -> 1 where it shows flooding, judged against the track's normal picture."""
    def flag(im):
        return im.lt(WATER_DB).And(im.subtract(ref).lt(-DROP_DB)).And(im.gt(NOISE_DB)).rename("f").toByte()
    return flag


def ask(shape):
    """Send one piece of land to Earth Engine; returns a dict of areas in km2 and the number of images used."""
    geom = ee.Geometry(json.loads(json.dumps(mapping(shape))))
    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(geom)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV")).select("VV"))
    season = s1.filterDate(f"{FIRST_YEAR}-01-01", f"{LAST_YEAR + 1}-01-01").filter(ee.Filter.calendarRange(SEASON[0], SEASON[1], "month"))
    counts = ee.Dictionary({"season": season.aggregate_histogram("relativeOrbitNumber_start"),
                            "ref": s1.filterDate(*REF_YEARS).aggregate_histogram("relativeOrbitNumber_start")}).getInfo()
    tracks = [int(float(k)) for k, n in counts["ref"].items() if n >= MIN_REF_IMAGES and k in counts["season"]]
    images = sum(counts["season"][k] for k in counts["season"] if int(float(k)) in tracks)
    if not tracks:
        return {"images": 0}

    zero = ee.ImageCollection([ee.Image(0).rename("f").toByte()])
    per_year = {y: zero for y in YEARS}
    for t in tracks:
        on_track = s1.filter(ee.Filter.eq("relativeOrbitNumber_start", t))
        flag = flag_maker(on_track.filterDate(*REF_YEARS).median())
        in_season = on_track.filter(ee.Filter.calendarRange(SEASON[0], SEASON[1], "month"))
        for y in YEARS:
            per_year[y] = per_year[y].merge(in_season.filterDate(f"{y}-01-01", f"{y + 1}-01-01").map(flag))
    year_flag = {y: per_year[y].max() for y in YEARS}
    n_years = ee.ImageCollection([year_flag[y] for y in YEARS]).sum()

    often_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0).gte(OCCURRENCE_PCT)
    steep = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).unmask(0).gt(SLOPE_DEG)
    counted = often_water.Or(steep).Not()
    km2 = ee.Image.pixelArea().divide(1e6)

    bands = [km2.rename("district"), km2.updateMask(counted).rename("counted")]
    bands += [km2.updateMask(counted.And(n_years.gte(k))).rename(f"in{k}") for k in STEPS]
    bands += [km2.updateMask(counted.And(year_flag[y])).rename(f"y{y}") for y in YEARS]
    out = ee.Image.cat(bands).reduceRegion(reducer=ee.Reducer.sum(), geometry=geom, scale=SCALE_M,
                                           maxPixels=1e11, tileScale=4).getInfo()
    out = {k: float(v or 0) for k, v in out.items()}
    out["images"] = images
    return out


def measure(shape, depth=0):
    """Ask for one piece; if Earth Engine says it is too big, cut it in four and add the answers."""
    for attempt in range(1, 6):
        try:
            return ask(shape)
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
                    for k, v in measure(part, depth + 1).items():
                        total[k] = max(total.get(k, 0), v) if k == "images" else total.get(k, 0) + v
                return total
            if any(x in msg for x in ("too many", "429", "rate", "unavailable", "internal", "deadline", "connection", "reset")) and attempt < 5:
                time.sleep(20 * attempt)
                continue
            raise


def one(row):
    f = STORE / f"{row.shapeID}.json"
    if f.exists():
        saved = json.loads(f.read_text())
        if saved.get("sign") == SIGN:
            return row.shapeName, saved, 0.0
    t0 = time.time()
    shape = row.geometry.simplify(0.0003).buffer(0)
    res = measure(shape)
    res["sign"] = SIGN
    f.write_text(json.dumps(res))
    return row.shapeName, res, time.time() - t0


def main():
    global ee
    mode = os.environ.get("FLOODPRONE", "pilot").lower()
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    gdf = load_districts()
    if mode != "pilot":
        sys.exit("Only the trial is available so far. Run with FLOODPRONE=pilot.")
    rows = [r for r in gdf.itertuples() if r.shapeName in PILOT]
    missing = sorted(set(PILOT) - {r.shapeName for r in rows})
    if missing:
        print("Not found in the district list:", ", ".join(missing))
    print(f"Trial: {len(rows)} districts, {FIRST_YEAR} to {LAST_YEAR}, months {SEASON[0]} to {SEASON[1]}, {SCALE_M} m, settings {SIGN}", flush=True)

    t0, done, failed = time.time(), [], []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(one, r): r.shapeName for r in rows}
        for fut in futures:
            name = futures[fut]
            try:
                name, res, secs = fut.result()
                done.append((name, res, secs))
                print(f"  done {name} ({'saved earlier' if not secs else f'{secs:.0f} s'})", flush=True)
            except Exception as e:
                failed.append(name)
                print(f"  FAILED {name}: {type(e).__name__}: {str(e)[:300]}", flush=True)

    print(f"\nAll areas in km2. 'in N' = land seen flooded in at least N of the {len(YEARS)} years.")
    print(f"{'district':26}{'area':>8}{'counted':>9}{'in 1':>8}{'in 2':>8}{'in 3':>8}{'in 5':>8}{'images':>8}{'secs':>7}")
    for name, r, secs in sorted(done):
        if not r.get("images"):
            print(f"{name:26}  no usable radar images")
            continue
        print(f"{name:26}{r['district']:8.0f}{r['counted']:9.0f}" + "".join(f"{r[f'in{k}']:8.1f}" for k in STEPS) + f"{r['images']:8d}{secs:7.0f}")
    print("\nFlooded area in each year (km2):")
    print(f"{'district':26}" + "".join(f"{y:>7}" for y in YEARS))
    for name, r, secs in sorted(done):
        if r.get("images"):
            print(f"{name:26}" + "".join(f"{r[f'y{y}']:7.1f}" for y in YEARS))
    print(f"\nTrial finished in {(time.time() - t0) / 60:.1f} minutes. Nothing was published on the site.")
    if failed:
        sys.exit("These districts failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
