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

Run:
  python scripts/floodprone.py                    every district, then publish data/floodprone.json
  FLOODPRONE=pilot python scripts/floodprone.py   compare the settings on a few districts; publishes nothing
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
from common import CACHE, DATA, load_districts, write_layer  # noqa: E402
from ee_check import ee_login  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 2                               # raise this to make the weekly update rebuild the layer
FIRST_YEAR = 2016                       # earliest year considered; thinly imaged early years are dropped (see choose_years)
THIN_YEAR = 0.6                         # a year with fewer images than this share of the usual number is "thin"
SHORE_WATER_PCT = 75                    # water this often or more is permanent water
SHORE_CELL_M = 3000                     # the lake-shore zone is worked out on cells this wide
SHORE_FRACTION = 0.2                    # a cell with this share of permanent water, and the cells beside it, is lake shore
SHORE_MIN_LAT = 6.2                     # only north of this, so the coast and its lagoons are not treated as lake shore
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
CHOSEN = "E"     # the setting used for the published map; see docs/validation.md for why
MIN_KM2 = 0.1    # less than this is shown as "none detected"
CATS = [
    {"key": "p0", "label": "None detected", "note": "", "color": "#f1eee6", "max": MIN_KM2},
    {"key": "p1", "label": "Under 1 km²", "note": "", "color": "#bfd3e6", "max": 1},
    {"key": "p2", "label": "1 to 5 km²", "note": "", "color": "#8c96c6", "max": 5},
    {"key": "p3", "label": "5 to 20 km²", "note": "", "color": "#88419d", "max": 20},
    {"key": "p4", "label": "Over 20 km²", "note": "", "color": "#4d004b", "max": 1e12},
    {"key": "out", "label": "Not assessed", "note": "no usable radar images", "color": "#bdbdbd"},
]
EVENT = ("2023-09-15", "2023-11-16")    # the lower Volta flood already on the site, for comparison
PILOT = ["North Tongu", "Central Tongu", "South Tongu", "Ada East", "Ada West", "Asuogyaman", "Keta Municipal",
         "Talensi", "Bawku West", "Builsa South", "Central Gonja", "Kwahu Afram Plains North", "Accra Metropolis"]
# --------------------------------------------------------------------------

YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
STEPS = [1, 2, 3, 5]
SETTINGS = [REF_YEARS, NOISE_DB, OCCURRENCE_PCT, SLOPE_DEG, SCALE_M, MIN_REF_IMAGES, EVENT,
            SHORE_WATER_PCT, SHORE_CELL_M, SHORE_FRACTION, SHORE_MIN_LAT, 3]
GHANA = [-3.3, 4.7, 1.3, 11.2]          # west, south, east, north


def sign(v):
    return hashlib.md5(json.dumps([SETTINGS, YEARS, v], sort_keys=True).encode()).hexdigest()[:10]


def choose_years(v):
    """Count the usable radar images of Ghana in each year and drop the thinly imaged years at the start.
    Sentinel-1 took far fewer images of West Africa in its first years, and a year with few images
    cannot show a flood twice, so it would look falsely dry."""
    global YEARS
    box_ = ee.Geometry.Rectangle(GHANA)
    col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(box_).filter(ee.Filter.eq("instrumentMode", "IW"))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
           .filter(ee.Filter.calendarRange(v["months"][0], v["months"][1], "month")))
    if v["vh"] is not None:
        col = col.filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    counts = ee.Dictionary({str(y): col.filterDate(f"{y}-01-01", f"{y + 1}-01-01").size()
                            for y in range(FIRST_YEAR, LAST_YEAR + 1)}).getInfo()
    counts = {int(y): int(n) for y, n in counts.items()}
    usual = sorted(counts.values())[len(counts) // 2]
    first = next(y for y in sorted(counts) if counts[y] >= THIN_YEAR * usual)
    YEARS = [y for y in sorted(counts) if y >= first]
    print("Usable radar images of Ghana in the months read, by year: " + ", ".join(f"{y}: {counts[y]}" for y in sorted(counts)))
    print(f"Usual number {usual}. Years used: {YEARS[0]} to {YEARS[-1]} ({len(YEARS)} years)", flush=True)
    return counts


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
    season = s1.filterDate(f"{YEARS[0]}-01-01", f"{YEARS[-1] + 1}-01-01").filter(months)
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

    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0)
    often_water = occurrence.gte(OCCURRENCE_PCT)
    steep = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003")).unmask(0).gt(SLOPE_DEG)
    counted = often_water.Or(steep).Not()
    # lake shore: coarse cells that are largely permanent water, plus the cells beside them
    share = (occurrence.gte(SHORE_WATER_PCT).reduceResolution(ee.Reducer.mean(), False, 65536)
             .reproject(crs="EPSG:4326", scale=SHORE_CELL_M))
    shore = (share.gte(SHORE_FRACTION).focalMax(1, "square", "pixels").reproject(crs="EPSG:4326", scale=SHORE_CELL_M)
             .And(ee.Image.pixelLonLat().select("latitude").gt(SHORE_MIN_LAT)).unmask(0))
    land = counted.And(shore.Not())          # counted land away from the lake shore
    lake = counted.And(shore)
    km2 = ee.Image.pixelArea().divide(1e6)

    bands = [km2.rename("district"), km2.updateMask(counted).rename("counted"), km2.updateMask(land).rename("land")]
    bands += [km2.updateMask(land.And(n_years.gte(k))).rename(f"in{k}") for k in STEPS]
    bands += [km2.updateMask(lake.And(n_years.gte(k))).rename(f"shore{k}") for k in (1, 2)]
    bands += [km2.updateMask(land.And(year_flag[y])).rename(f"y{y}") for y in YEARS]
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


MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def publish(results, v, counts):
    """results: {shapeID: (name, numbers)} for every district -> data/floodprone.json"""
    n, first, last = len(YEARS), YEARS[0], YEARS[-1]
    season = f"{MONTHS[v['months'][0]]} to {MONTHS[v['months'][1]]}"
    districts, total = {}, 0.0
    for sid, (name, r) in results.items():
        if not r.get("images") or not r.get("land"):
            districts[sid] = {"name": name, "cat": "out", "big": "–", "big_note": "No usable radar images for this district.",
                              "tip": "Not assessed", "rows": [], "v": [0] * n, "c": ["out"] * n}
            continue
        km2 = r["in2"]
        total += km2
        cat = next(c["key"] for c in CATS if km2 < c.get("max", -1))
        ys = [r[f"y{y}"] for y in YEARS]
        top = max(range(n), key=lambda k: ys[k])
        show = lambda x: f"{x:,.1f} km²" if x >= MIN_KM2 else "None detected"
        districts[sid] = {
            "name": name, "cat": cat,
            "big": f"{km2:,.1f} km²" if km2 >= MIN_KM2 else "None",
            "big_note": f"of land seen flooded in at least 2 of the {n} years {first} to {last}",
            "tip": f"{km2:,.1f} km² flooded in 2 or more years" if km2 >= MIN_KM2 else "None detected",
            "rows": [
                ["Share of the district's land", f"{km2 / r['land'] * 100:.1f}%"],
                ["Flooded in at least 1 year", show(r["in1"])],
                ["Flooded in at least 3 years", show(r["in3"])],
                ["Flooded in at least 5 years", show(r["in5"])],
                ["Largest flooded area in one year", f"{ys[top]:,.1f} km² ({YEARS[top]})" if ys[top] >= MIN_KM2 else "–"],
                ["Along Lake Volta and large reservoirs, not counted above", show(r["shore2"])],
                ["Radar images read", f"{int(r['images']):,}"],
            ],
            "v": [round(x, 2) for x in ys], "c": [cat] * n,
        }
    lake_total = sum(r.get("shore2", 0) for _, r in results.values())
    print(f"Flooded in at least 2 of {n} years: {total:,.0f} km2 across Ghana, plus {lake_total:,.0f} km2 along the lake shore")
    write_layer("floodprone", {
        "label": "Flood-prone land", "title": "Flood-prone land", "source": "Sentinel-1 radar, processed by Tinga Lens", "demo": False,
        "subtitle": f"Land seen under water in at least 2 of the {n} years {first} to {last}",
        "build": BUILD, "images_by_year": counts,
        "settings": {"key": CHOSEN, **v, "years": [first, last], "scale_m": SCALE_M, "occurrence_pct": OCCURRENCE_PCT, "slope_deg": SLOPE_DEG},
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Tinga Lens read every Sentinel-1 radar image of Ghana taken from {season} in the years {first} to {last}. "
                f"A piece of land about {SCALE_M} m across is counted as flooded in a year when at least {v['hits']} images that year show it as open water "
                f"and clearly darker than it normally is. Each district shows the area flooded in at least 2 of the {n} years. "
                f"Rivers, lakes, lagoons and other land that is under water {OCCURRENCE_PCT}% of the time or more are not counted. "
                f"Land along Lake Volta and other large reservoirs, where the water rises and falls with the lake, is reported separately and is not in the main figure. "
                + (f"The record starts in {first} because the satellite took too few images of Ghana before then. " if first > FIRST_YEAR else "") +
                f"Click a district to see the flooded area in each year."),
        "limits": [
            "This is Tinga Lens's own reading of the radar images. It has been compared with one mapped flood (lower Volta, 2023) but not checked on the ground.",
            "Radar cannot see water under trees or between buildings, so flooding in forests and towns is mostly missed. City street flooding, as in Accra, does not appear.",
            f"A flood must be seen on at least {v['hits']} images in a year. Each place is imaged every few days, so floods lasting only a day or two are missed.",
            "Land within about 3 to 6 km of Lake Volta and other large reservoirs is set apart as lake shore, using a coarse grid. Some river flooding close to the lake is put there by mistake, and narrow arms of the lake can be missed.",
            "Irrigated rice fields, salt pans, coastal lagoon edges and seasonal wetlands hold water on purpose or every year, and can be counted as flooded.",
            f"Only {season} is read, because dry bare soil in the dry season looks like water to radar. Flooding outside those months is not counted.",
            "The figure is land area. It says nothing about how deep the water was or how many people were affected, and it is not a forecast.",
        ],
        "credits": [{"text": "Radar images: Copernicus Sentinel-1, processed in Google Earth Engine", "url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD"},
                    {"text": "Usual water: JRC Global Surface Water", "url": "https://global-surface-water.appspot.com/"},
                    {"text": "Slope: NASA SRTM", "url": "https://www.earthdata.nasa.gov/data/instruments/srtm"}],
        "chart": {"kind": "bars", "unit": "km²", "x": [str(y) for y in YEARS],
                  "caption": "Land seen flooded in each year (square kilometres).", "top": "", "bottom": ""},
        "districts": districts,
    })


def full():
    """Every district with the chosen setting, then publish."""
    v = VARIANTS[CHOSEN]
    counts = choose_years(v)
    rows = list(load_districts().itertuples())
    print(f"Flood-prone land: {len(rows)} districts, {YEARS[0]} to {YEARS[-1]}, setting {CHOSEN}", flush=True)
    t0, results, failed = time.time(), {}, []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(one, r, v): r for r in rows}
        for k, (fut, r) in enumerate(futures.items(), 1):
            try:
                results[r.shapeID] = (r.shapeName, fut.result()[1])
            except Exception as e:
                failed.append(r.shapeName)
                print(f"  FAILED {r.shapeName}: {type(e).__name__}: {str(e)[:300]}", flush=True)
            if k % 20 == 0:
                print(f"  {k} of {len(rows)} districts, {(time.time() - t0) / 60:.1f} min", flush=True)
    if failed:
        sys.exit(f"{len(failed)} districts failed ({', '.join(failed[:8])}). Finished districts are saved; run again to retry the rest. Nothing was published.")
    publish(results, v, counts)


def main():
    global ee
    mode = os.environ.get("FLOODPRONE", "true").lower()
    ee, project, email = ee_login()
    ee.data.setDeadline(330000)
    STORE.mkdir(parents=True, exist_ok=True)
    if mode != "pilot":
        return full()
    rows = [r for r in load_districts().itertuples() if r.shapeName in PILOT]
    choose_years(VARIANTS[CHOSEN])
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
