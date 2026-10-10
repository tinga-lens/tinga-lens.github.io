#!/usr/bin/env python3
"""
Tinga Lens - Rainy Season Tracker (EXPERIMENTAL, version 0.1).

For every district: when did the rains start this year, and is that earlier or
later than usual?  The rules below are CANDIDATE rules taken from methods used for
West African rainfall. They have not yet been checked against station records, so
the layer is published as experimental.

Rules (all settings are at the top of this file):
  Season window  southern districts: onset sought from 1 March to 31 July
                 northern districts: onset sought from 1 April to 31 August
  Rain test      a day D passes when D itself has rain (1 mm or more) and the 3 days D, D+1, D+2 add up to at least 20 mm
  Dry spell      a run of days that are each under 1 mm
  Onset          the first day that passes the rain test and is NOT followed by a dry spell
                 of 7 days or more in the next 21 days
  False start    a day that passes the rain test but IS followed by such a dry spell
  Possible start the rain test is passed but fewer than 21 days of data follow, so it cannot
                 be confirmed yet
  Usual          the median onset date in the baseline years (1991-2020)

Run:
  python scripts/rainy_season.py                 # real data (downloads daily CHIRPS)
  python scripts/rainy_season.py --demo          # made-up data, only for previewing the site
  python scripts/rainy_season.py --probe         # only test the download addresses, then stop
  python scripts/rainy_season.py --first-year N  # real data, baseline starting in year N (quick trial)
  python scripts/rainy_season.py --self-test     # test the rules on made-up rainfall, then stop

Data: CHIRPS daily rainfall, Climate Hazards Center, UC Santa Barbara (public domain).
Boundaries: geoBoundaries GHA ADM2 (CC BY 4.0).
"""
import argparse
import datetime as dt
import gzip
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, CACHE, MON, ROOT, write_layer  # noqa: E402

BUILD = 1

# ---- settings you may want to change -------------------------------------
BASELINE = (1991, 2020)          # years that define "usual"
NORTH_LAT = 8.5                  # districts whose centre is north of this use the northern window
WINDOW = {                       # (month, day) the onset is sought from and until
    "south": ((3, 1), (7, 31)),
    "north": ((4, 1), (8, 31)),
}
RAIN_DAYS = 3                    # days added together for the rain test
RAIN_MM = 20.0                   # mm needed in those days
DRY_MM = 1.0                     # a day under this is a dry day
DRY_RUN = 7                      # dry days in a row that make a dry spell
CONFIRM_DAYS = 21                # days after the rain test that are checked for a dry spell
USUAL_DAYS = 7                   # within this many days of the median counts as "about usual"
MUCH_DAYS = 14                   # this many days or more counts as "much" earlier or later
MIN_BASELINE_YEARS = 20          # fewer years with an onset than this: the district is not rated
FETCH_FROM = (3, 1)              # the cache holds these days of each year ...
FETCH_TO = (9, 30)               # ... up to here (the north window ends 31 Aug, plus 21 days to confirm)
REFRESH_DAYS = 12                # always download the newest days again: recent CHIRPS values are revised

BASE = os.environ.get("TINGA_CHIRPS_BASE", "https://data.chc.ucsb.edu/products")
# Daily CHIRPS files, tried in this order for each day. Check these addresses with --probe before the
# first full run; the Climate Hazards Center has moved folders between releases.
URLS = [
    BASE + "/CHIRPS-2.0/africa_daily/tifs/p05/{y}/chirps-v2.0.{y}.{m:02d}.{d:02d}.tif.gz",    # final
    BASE + "/CHIRPS-2.0/prelim/global_daily/tifs/p05/{y}/chirps-v2.0.{y}.{m:02d}.{d:02d}.tif",  # preliminary, newest days
]
PRODUCT = "CHIRPS v2.0 daily (final, with preliminary values for the newest days)"
# --------------------------------------------------------------------------

CATEGORIES = [
    {"key": "much_early", "label": "Much earlier", "note": f"{MUCH_DAYS}+ days before usual", "color": "#2166ac"},
    {"key": "early", "label": "Earlier", "note": f"{USUAL_DAYS} to {MUCH_DAYS} days before usual", "color": "#92c5de"},
    {"key": "usual", "label": "About usual", "note": f"within {USUAL_DAYS} days of usual", "color": "#f1f1f1"},
    {"key": "late", "label": "Later", "note": f"{USUAL_DAYS} to {MUCH_DAYS} days after usual", "color": "#f4a582"},
    {"key": "much_late", "label": "Much later", "note": f"{MUCH_DAYS}+ days after usual", "color": "#b2182b"},
    {"key": "possible", "label": "Possible start", "note": "rain test passed, not yet confirmed", "color": "#fee08b"},
    {"key": "not_started", "label": "Not started", "note": "no start yet this season", "color": "#d9d9d9"},
    {"key": "none", "label": "No start found", "note": "no start in the season window", "color": "#8c8c8c"},
    {"key": "not_rated", "label": "Not rated", "note": "too few years of history", "color": "#bdbdbd"},
]
NAMES = {c["key"]: c["label"] for c in CATEGORIES}


# ============================================================ the rules (pure functions, tested below)
def longest_dry_run(x):
    """Longest run of consecutive days under DRY_MM in x (days with no data do not count as dry)."""
    best = run = 0
    for v in x:
        if not np.isnan(v) and v < DRY_MM:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def find_onset(r, lo, hi):
    """
    Look for the start of the rains in daily rainfall r (mm, NaN = no data), testing days lo..hi inclusive.
    Returns (kind, index, false_starts):
      kind  'onset'    index = first day that passes the rain test with no dry spell after it
            'possible' index = first day that passes the test but cannot be confirmed (data ends too soon)
            'none'     index = None: no day passed
      false_starts = number of separate false starts found before that day (a new one needs 7+ days gap)
    """
    false_starts, last_fs = 0, -10 ** 6
    n = len(r)
    for d in range(lo, hi + 1):
        if d + RAIN_DAYS > n:
            break
        w = r[d:d + RAIN_DAYS]
        if np.isnan(w).any() or w[0] < DRY_MM or w.sum() < RAIN_MM:      # the first day must itself be a rain day
            continue
        after = r[d + RAIN_DAYS:d + RAIN_DAYS + CONFIRM_DAYS]
        known = int((~np.isnan(after)).sum()) if len(after) else 0
        if longest_dry_run(after) >= DRY_RUN:
            if d - last_fs >= DRY_RUN:
                false_starts += 1
            last_fs = d
            continue
        if known < CONFIRM_DAYS:        # no dry spell yet, but the checking period is not complete
            return "possible", d, false_starts
        return "onset", d, false_starts
    return "none", None, false_starts


def classify(days_from_usual):
    if days_from_usual <= -MUCH_DAYS:
        return "much_early"
    if days_from_usual < -USUAL_DAYS:
        return "early"
    if days_from_usual <= USUAL_DAYS:
        return "usual"
    if days_from_usual < MUCH_DAYS:
        return "late"
    return "much_late"


def self_test():
    """Check the rules on rainfall whose answer is known. Stops with an error if anything is wrong."""
    def series(spec, n=60):
        r = np.zeros(n, "float32")
        for i, v in spec.items():
            r[i] = v
        return r
    # 1. clean start: 25 mm on day 10, then regular rain
    r = series({10: 25, 14: 6, 18: 8, 22: 5, 27: 7, 31: 9, 36: 6})
    assert find_onset(r, 0, 30)[:2] == ("onset", 10), find_onset(r, 0, 30)
    # 2. false start: 25 mm on day 5, then 10 dry days, then a proper start on day 30
    r = series({5: 25, 30: 22, 34: 6, 38: 5, 42: 8, 46: 7, 50: 6})
    kind, idx, fs = find_onset(r, 0, 40)
    assert (kind, idx, fs) == ("onset", 30, 1), (kind, idx, fs)
    # 3. a 6-day dry spell is not enough to be a false start
    r = series({5: 25, 12: 4, 18: 5, 24: 6, 30: 5})
    assert find_onset(r, 0, 30)[:2] == ("onset", 5)
    # 4. not enough rain: 19 mm over 3 days never passes
    r = series({10: 10, 11: 9})
    assert find_onset(r, 0, 40)[0] == "none"
    # 5. rain test passed but the data ends 10 days later: possible, not onset
    r = series({10: 25, 14: 5, 18: 6})[:21]
    assert find_onset(r, 0, 20)[:2] == ("possible", 10), find_onset(r, 0, 20)
    # 6. missing data inside the 3-day test is skipped, not counted as rain
    r = series({10: 25, 14: 6, 18: 8, 22: 5, 27: 7, 31: 9, 36: 6})
    r[11] = np.nan
    assert find_onset(r, 0, 30)[0] != "onset" or find_onset(r, 0, 30)[1] != 10
    # 7. categories
    assert [classify(x) for x in (-20, -10, 0, 7, 8, 14, 30)] == ["much_early", "early", "usual", "usual", "late", "much_late", "much_late"]
    # 8. dry run counting
    assert longest_dry_run(np.array([0, 0, 5, 0, 0, 0, np.nan, 0], "float32")) == 3
    print("self-test passed: 8 checks")


# ============================================================ data
def date_range(y):
    a, b = dt.date(y, *FETCH_FROM), dt.date(y, *FETCH_TO)
    return [a + dt.timedelta(i) for i in range((b - a).days + 1)]


def session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    s.headers["User-Agent"] = "tinga-lens/0.1"
    return s


def fetch_day(s, day):
    """Rainfall (mm) over the Ghana window for one day, or None when no product has this day."""
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.windows import from_bounds
    from rasterio.windows import transform as window_transform
    for tmpl in URLS:
        url = tmpl.format(y=day.year, m=day.month, d=day.day)
        try:
            r = s.get(url, timeout=180)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        raw = gzip.decompress(r.content) if url.endswith(".gz") else r.content
        with MemoryFile(raw) as mem, mem.open() as src:
            win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win).astype("float32")
            nodata = src.nodata if src.nodata is not None else -9999
            arr[(arr == nodata) | (arr < 0)] = np.nan
            return arr, window_transform(win, src.transform)
    return None


def probe():
    s = session()
    for y in (2019, dt.date.today().year):
        day = dt.date(y, 4, 15)
        for tmpl in URLS:
            url = tmpl.format(y=y, m=day.month, d=day.day)
            try:
                code = s.get(url, stream=True, timeout=60).status_code
            except Exception as e:
                code = type(e).__name__
            print(f"{code}  {url}")


class Grid:
    """Turns a daily raster into one number per district."""

    def __init__(self, gdf, shape, tf):
        from rasterio.features import rasterize
        ids = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=shape,
                        transform=tf, fill=0, dtype="int32")
        for i, geom in enumerate(gdf.geometry):       # district smaller than a pixel: use every pixel it touches
            if not (ids == i + 1).any():
                m = rasterize([(geom, 1)], out_shape=shape, transform=tf, fill=0, dtype="uint8", all_touched=True).astype(bool)
                ids[m & (ids == 0)] = i + 1
        self.ids = ids.ravel()
        self.n = len(gdf)

    def means(self, arr):
        a = arr.ravel()
        ok = (self.ids > 0) & ~np.isnan(a)
        tot = np.bincount(self.ids[ok], weights=a[ok], minlength=self.n + 1)[1:]
        cnt = np.bincount(self.ids[ok], minlength=self.n + 1)[1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(cnt > 0, tot / cnt, np.nan).astype("float32")


def load_real(gdf, first_year, today):
    """Returns {date: (districts,) array}. Days that cannot be found are left out."""
    cache_file = CACHE / "rainy_season_daily.npz"
    sid = np.array(gdf.shapeID.tolist())
    have = {}
    if cache_file.exists():
        z = np.load(cache_file, allow_pickle=False)
        if z["ids"].tolist() == sid.tolist():
            vals, dates = z["vals"], z["dates"]          # read each array once (reading z["vals"] inside the loop unpacks the whole file every time)
            have = {dt.date.fromordinal(int(o)): vals[i] for i, o in enumerate(dates)}
    s = session()
    cur = today.year if today >= dt.date(today.year, *FETCH_FROM) else today.year - 1
    wanted = [d for y in range(first_year, cur + 1) for d in date_range(y) if d < today]
    fresh = today - dt.timedelta(REFRESH_DAYS)
    todo = [d for d in wanted if d not in have or d >= fresh]
    print(f"{len(wanted)} days needed, {len(todo)} to download, {len(wanted) - len(todo)} cached")
    grid, missing = None, []
    done = 0
    CHUNK = 400
    for i in range(0, len(todo), CHUNK):
        part = todo[i:i + CHUNK]
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda d: fetch_day(s, d), part))
        for d, r in zip(part, res):
            if r is None:
                missing.append(d)
                have.pop(d, None)
                continue
            arr, tf = r
            if grid is None:
                grid = Grid(gdf, arr.shape, tf)
            have[d] = grid.means(arr)
        done += len(part)
        print(f"  downloaded {done} of {len(todo)}", flush=True)
        save_cache(cache_file, sid, have)         # keep progress, so a stopped run can carry on
    if len(missing) > 0.03 * max(len(todo), 1):
        print(f"WARNING: {len(missing)} days could not be found ({len(missing) / max(len(todo), 1):.0%}). Check the addresses with --probe.")
    if not have:
        sys.exit("No daily CHIRPS data could be reached. Run with --probe and check the addresses in URLS.")
    return {d: v for d, v in have.items() if first_year <= d.year <= cur}, cur


def save_cache(cache_file, sid, have):
    CACHE.mkdir(exist_ok=True)
    keys = sorted(have)
    np.savez_compressed(cache_file, ids=sid, dates=np.array([d.toordinal() for d in keys]),
                        vals=np.stack([have[k] for k in keys]).astype("float32") if keys else np.zeros((0, len(sid)), "float32"))


def load_demo(gdf, today):
    """Made-up daily rainfall with a start date that varies by district and year. For previewing the site only."""
    rng = np.random.default_rng(11)
    cur = today.year if today >= dt.date(today.year, *FETCH_FROM) else today.year - 1
    lat = gdf.geometry.representative_point().y.values
    out = {}
    for y in range(BASELINE[0], cur + 1):
        days = date_range(y)
        shift = rng.normal(0, 9)                                  # a whole-country early or late year
        for d in days:
            out[d] = np.zeros(len(gdf), "float32")
        base = np.where(lat >= NORTH_LAT, 118 + (lat - NORTH_LAT) * 10, 78 - (lat - 4.7) * 3)   # usual onset day of year
        onset = base + shift + rng.normal(0, 5, len(gdf))
        for i in range(len(gdf)):
            doy0 = days[0].timetuple().tm_yday
            p, mean = 0.07, 4.0
            fs = rng.random() < 0.3
            for k, d in enumerate(days):
                doy = doy0 + k
                if fs and abs(doy - (onset[i] - 18)) < 2:
                    out[d][i] = 14
                    continue
                if doy < onset[i]:
                    wet = rng.random() < (0.015 if fs and doy < onset[i] - 6 else p)
                    out[d][i] = rng.exponential(mean) + 1 if wet else 0
                else:
                    wet = rng.random() < (0.5 if doy < onset[i] + 120 else 0.25)
                    out[d][i] = rng.exponential(11) + 1 if wet else 0
                    if doy == int(onset[i]):
                        out[d][i] = 26
        if y == cur and cur == today.year:                       # the current year stops at the last day with data
            for d in days:
                if d >= today - dt.timedelta(3):
                    out.pop(d, None)
    return out, cur


# ============================================================ analysis
def analyse(daily, gdf, cur, today, first_year):
    lat = gdf.geometry.representative_point().y.values
    zone = np.where(lat >= NORTH_LAT, "north", "south")
    years = list(range(first_year, cur + 1))
    res = {}
    for i in range(len(gdf)):
        (m0, d0), (m1, d1) = WINDOW[zone[i]]
        per_year = {}
        for y in years:
            days = date_range(y)
            r = np.array([daily[d][i] if d in daily else np.nan for d in days], "float32")
            a = days.index(dt.date(y, m0, d0))
            b = days.index(dt.date(y, m1, d1))
            if np.isnan(r[a:b + 1]).mean() > 0.5:
                per_year[y] = None
                continue
            kind, idx, fs = find_onset(r, a, b)
            doy = (days[idx] - dt.date(y, 1, 1)).days + 1 if idx is not None else None
            longest = None
            if kind == "onset":
                longest = longest_dry_run(r[idx + RAIN_DAYS:idx + RAIN_DAYS + 30])
            rain_since = float(np.nansum(r[:idx + 1])) if idx is not None else float(np.nansum(r[a:]))
            known_to = days[max(j for j in range(len(days)) if not np.isnan(r[j]))] if (~np.isnan(r)).any() else None
            per_year[y] = dict(kind=kind, doy=doy, date=days[idx] if idx is not None else None, false_starts=fs,
                               longest_dry=longest, rain=rain_since, known_to=known_to, window_end=dt.date(y, m1, d1))
        res[i] = per_year
    return zone, years, res


def doy_text(doy, year=2001):
    d = dt.date(year, 1, 1) + dt.timedelta(int(round(doy)) - 1)
    return f"{d.day} {MON[d.month - 1]}"


def build(daily, gdf, cur, today, first_year, demo):
    zone, years, res = analyse(daily, gdf, cur, today, first_year)
    districts, counts = {}, {}
    base_years = [y for y in years if BASELINE[0] <= y <= BASELINE[1]]
    labels = [str(y) for y in years]
    for i, row in gdf.iterrows():
        py = res[i]
        ons = [py[y]["doy"] for y in base_years if py.get(y) and py[y]["kind"] == "onset"]
        now = py.get(cur)
        if len(ons) < min(MIN_BASELINE_YEARS, max(5, len(base_years) * 2 // 3)) or now is None:
            continue
        med = float(np.median(ons))
        lo, hi = min(ons), max(ons)
        if now["kind"] == "onset":
            diff = now["doy"] - med
            cat = classify(diff)
        elif now["kind"] == "possible":
            cat, diff = "possible", None
        else:
            cat, diff = ("none", None) if today > now["window_end"] else ("not_started", None)
        counts[cat] = counts.get(cat, 0) + 1
        usual = f"{doy_text(med)} (median {BASELINE[0]}–{BASELINE[1]})"
        if cat in ("possible",):
            big, note = doy_text(now["doy"]), f"The rain test was passed on this date, but it is too soon to confirm. Usual start: {doy_text(med)}."
        elif cat == "not_started":
            big, note = "Not yet", f"No start yet in {cur}. Usual start: {doy_text(med)}."
        elif cat == "none":
            big, note = "None found", f"No start was found in the season window in {cur}. Usual start: {doy_text(med)}."
        else:
            n = abs(round(diff))
            how = "about usual" if cat == "usual" else f"{n} day{'s' if n != 1 else ''} {'earlier' if diff < 0 else 'later'} than usual"
            big, note = doy_text(now["doy"]), f"Rains started, {how}. Usual start: {doy_text(med)}."
        rows = [["Start of rains " + str(cur), big if cat not in ("not_started", "none") else "–"],
                ["Usual start (median)", doy_text(med)],
                [f"Earliest and latest, {BASELINE[0]}–{BASELINE[1]}", f"{doy_text(lo)} and {doy_text(hi)}"],
                ["False starts this season", str(now["false_starts"])]]
        if now.get("longest_dry") is not None:
            rows.append(["Longest dry spell in the next 30 days", f"{now['longest_dry']} days"])
        rows.append([f"Rain since {MON[WINDOW[zone[i]][0][0] - 1]} {WINDOW[zone[i]][0][1]}", f"{round(now['rain'])} mm"])
        v, c = [], []
        for y in years:
            p = py.get(y)
            if p and p["kind"] == "onset":
                dd = p["doy"] - med
                v.append(round(dd))
                c.append(classify(dd))
            else:
                v.append(None)
                c.append("none" if p else "not_rated")
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat, "big": big, "big_note": note,
            "tip": NAMES[cat] + (f" · {big}" if cat not in ("not_started", "none") else ""),
            "rows": rows, "v": v, "c": c,
        }
    return districts, counts, labels


def render(districts, counts, labels, cur, demo, source):
    return {
        "label": "Rainy season", "title": f"When the rains started, {cur} (experimental)",
        "subtitle": f"Compared with the usual start in {BASELINE[0]}–{BASELINE[1]}. Southern districts from 1 March, northern from 1 April",
        "source": source, "demo": demo, "categories": CATEGORIES,
        "how": ("EXPERIMENTAL. This map shows when the main rainy season began in each district, compared with the usual "
                f"date. The start is the first day when 3 days together bring at least {RAIN_MM:.0f} mm and no dry spell of "
                f"{DRY_RUN} days or more follows in the next {CONFIRM_DAYS} days. \"Usual\" is the median start in "
                f"{BASELINE[0]}–{BASELINE[1]}. Southern districts have two rainy seasons; this map shows the first (main) season only."),
        "limits": [
            "Experimental, version 0.1. The rules have not yet been checked against rain-gauge records, so a date may differ from what people on the ground saw.",
            "This shows when rain started in satellite and rain-gauge data. It is not planting advice and not a forecast.",
            "A different rule would give a different date. The rule used is stated above and may change after testing.",
            "The rainfall estimate is on a grid of about 5 km and is averaged over each district, so it hides differences inside a district.",
            "Recent days use preliminary data that can be revised, so a possible or new start date can move by a few days.",
            "Districts near the boundary between the southern and northern rainfall zones may be assigned the wrong season window.",
        ],
        "credits": [{"text": "Rainfall: CHIRPS daily, Climate Hazards Center, UC Santa Barbara", "url": "https://www.chc.ucsb.edu/data/chirps"}],
        "chart": {"kind": "diverging", "cap": 30, "unit": "days vs usual", "x": labels,
                  "caption": f"Start of the rains each year, days from the usual date ({labels[0]} to {labels[-1]})",
                  "top": "later than usual", "bottom": "earlier"},
        "districts": districts,
        "build": BUILD,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    ap.add_argument("--probe", action="store_true", help="only test the download addresses")
    ap.add_argument("--self-test", action="store_true", help="test the rules, then stop")
    ap.add_argument("--first-year", type=int, default=BASELINE[0], help="first year to download (quick trial)")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.probe:
        return probe()
    import geopandas as gpd
    gdf = gpd.read_file(ROOT / "data" / "districts.geojson").reset_index(drop=True)
    today = dt.date.today()
    if args.demo:
        daily, cur = load_demo(gdf, today)
        source = "DEMO (made-up numbers)"
    else:
        daily, cur = load_real(gdf, args.first_year, today)
        source = PRODUCT
    trial = os.environ.get("RAINSEASON", "").lower() == "trial"
    if trial and not args.demo:
        args.first_year = BASELINE[1] - 4          # a quick check on the last 5 baseline years
    first = max(BASELINE[0], args.first_year) if not args.demo else BASELINE[0]
    districts, counts, labels = build(daily, gdf, cur, today, first, args.demo)
    if not districts:
        sys.exit("No district could be rated. Check the data (too few baseline years?).")
    layer = render(districts, counts, labels, cur, args.demo, source)
    if trial and not args.demo:
        import json
        CACHE.mkdir(exist_ok=True)
        (CACHE / "rainseason_trial.json").write_text(json.dumps(layer))
        print(f"TRIAL: nothing published. {len(districts)} districts rated, counts {counts}")
        print("Sample:", {d["name"]: d["big"] for d in list(districts.values())[:8]})
        return
    write_layer("rainseason", layer)


if __name__ == "__main__":
    main()
