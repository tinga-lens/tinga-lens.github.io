#!/usr/bin/env python3
"""
Tinga Lens - Dry Spells (EXPERIMENTAL, version 0.1).

For every district: what was the longest run of dry days during the main rainy season, and is that longer
or shorter than usual?  It uses the daily CHIRPS rainfall that the rainy-season tracker has already saved
(cache/rainy_season_daily.npz), so it downloads nothing and needs no Google Earth Engine.

Rules (all settings are at the top of this file):
  Dry day        a day with less than 1 mm of rain (the same as the rainy-season tracker)
  Dry spell      dry days in a row; a day with no data ends the run and is never counted as dry
  Period         starts on the district's usual start of the rains (the median start in 1991-2020, from the
                 rainy-season tracker) and lasts 90 days. The same dates are used in every year, so the
                 years can be compared like with like.  While the season is still running, only the days
                 that have passed are used, in every year.
  Why not the year's own start?  The rainy-season tracker only confirms a start when no 7-day dry spell
                 follows it, so measuring dry spells after the year's own start would hide them.
  Usual          the median of the longest dry spell in the baseline years (1991-2020)
  Colour         where this year's longest spell ranks among the baseline years (ties count half), except that a
                 spell within 2 days of the usual is always "about usual": in a district whose spells are all
                 short, one day more or less can move the rank a long way and means nothing

Run:
  python scripts/dryspell.py               # real data (reads the saved daily rainfall)
  python scripts/dryspell.py --demo        # made-up data, only for previewing the site
  python scripts/dryspell.py --self-test   # test the rules on made-up rainfall, then stop

Data: CHIRPS daily rainfall, Climate Hazards Center, UC Santa Barbara (public domain).
Boundaries: geoBoundaries GHA ADM2 (CC BY 4.0).
"""
import argparse
import datetime as dt
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CACHE, MON, ROOT, write_layer  # noqa: E402

spec = importlib.util.spec_from_file_location("rs", HERE / "rainy_season.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

BUILD = 1

# ---- settings you may want to change -------------------------------------
BASELINE = rs.BASELINE           # years that define "usual"
DRY_MM = rs.DRY_MM               # a day under this is a dry day
SPAN = 90                        # days measured, from the usual start of the rains
LONG_SPELL = 10                  # a spell this long or longer is counted separately
MIN_DIFF = 2                     # a spell within this many days of the usual (median) counts as "about usual", whatever its rank
MIN_MEASURED = 7                 # fewer days than this have passed: too early to say
MIN_DATA = 0.8                   # a year needs at least this share of the days to have data
CACHE_FILE = CACHE / "rainy_season_daily.npz"
# --------------------------------------------------------------------------

CATEGORIES = [
    {"key": "much_long", "label": "Much longer than usual", "note": "longest 10% of years", "color": "#8c510a"},
    {"key": "long", "label": "Longer than usual", "note": "longest 10 to 30%", "color": "#d8b365"},
    {"key": "usual", "label": "About usual", "note": "middle 40%, or within 2 days of usual", "color": "#f3efe4"},
    {"key": "short", "label": "Shorter than usual", "note": "shortest 10 to 30%", "color": "#5ab4ac"},
    {"key": "much_short", "label": "Much shorter than usual", "note": "shortest 10% of years", "color": "#01665e"},
    {"key": "not_yet", "label": "Too early", "note": f"under {MIN_MEASURED} days of the period have passed", "color": "#d9d9d9"},
    {"key": "not_rated", "label": "Not rated", "note": "too few years, or rainfall days missing", "color": "#bdbdbd"},
]
NAMES = {c["key"]: c["label"] for c in CATEGORIES}
COLORS = {c["key"]: c["color"] for c in CATEGORIES}


# ============================================================ the rules (pure functions, tested below)
def dry_runs(x, dry=DRY_MM):
    """[(start index, length), ...] for every run of days under `dry` mm. A day with no data (NaN) ends a run."""
    runs, start = [], None
    for i, v in enumerate(x):
        if not np.isnan(v) and v < dry:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - start))
            start = None
    if start is not None:
        runs.append((start, len(x) - start))
    return runs


def summarise(x):
    """(longest spell, where it starts, number of spells of LONG_SPELL days or more, total rain) for a window of daily rain."""
    runs = dry_runs(x)
    if not runs:
        return 0, None, 0, float(np.nansum(x))
    start, length = max(runs, key=lambda r: (r[1], -r[0]))      # the longest; the earliest if there is a tie
    return length, start, sum(1 for _, n in runs if n >= LONG_SPELL), float(np.nansum(x))


def pct_rank(v, base):
    """Share of the baseline values that are shorter than v, counting ties as half (0 to 100)."""
    b = np.asarray(base, "float64")
    return float(((b < v).sum() + 0.5 * (b == v).sum()) / len(b) * 100)


def classify(pct):
    if pct >= 90:
        return "much_long"
    if pct >= 70:
        return "long"
    if pct <= 10:
        return "much_short"
    if pct <= 30:
        return "short"
    return "usual"


def rate(length, base):
    """Category for a longest spell, given the baseline values: its rank, unless it is within MIN_DIFF days of the median."""
    if abs(length - float(np.median(base))) <= MIN_DIFF:
        return "usual"
    return classify(pct_rank(length, base))


def window(med_doy, year, n_days, span=SPAN):
    """(first index, number of days) of the period in a year whose rainfall starts on 1 March (index 0)."""
    day = dt.date(2001, 1, 1) + dt.timedelta(int(round(med_doy)) - 1)
    a = max(0, (dt.date(year, day.month, day.day) - dt.date(year, *rs.FETCH_FROM)).days)
    return a, max(0, min(span, n_days - a))


def self_test():
    """Check the rules on rainfall whose answer is known. Stops with an error if anything is wrong."""
    nan = np.nan
    # 1. runs, and NaN ends a run
    assert dry_runs(np.array([0, 0, 5, 0, 0, 0, nan, 0], "float32")) == [(0, 2), (3, 3), (7, 1)]
    assert dry_runs(np.array([0.9, 1.0, 0.0], "float32")) == [(0, 1), (2, 1)]            # 1.0 mm is not dry
    assert dry_runs(np.array([], "float32")) == []
    # 2. a run that reaches the end of the window is counted
    assert dry_runs(np.array([5, 0, 0, 0], "float32")) == [(1, 3)]
    # 3. summary: longest, where, long spells, total rain
    x = np.array([0] * 4 + [8] + [0] * 12 + [3] + [0] * 10 + [6] + [0] * 2, "float32")
    assert summarise(x) == (12, 5, 2, 17.0), summarise(x)
    # 4. a tie for longest reports the earlier one
    x = np.array([0] * 5 + [9] + [0] * 5, "float32")
    assert summarise(x)[:2] == (5, 0)
    # 5. no dry day at all
    assert summarise(np.array([5, 6, 7], "float32"))[:3] == (0, None, 0)
    # 6. percentile rank counts ties as half
    base = [3, 4, 5, 5, 5, 6, 7, 8, 9, 10]
    assert pct_rank(11, base) == 100 and pct_rank(2, base) == 0
    assert pct_rank(5, base) == (2 + 1.5) / 10 * 100
    assert pct_rank(7, [7] * 20) == 50
    # 7. categories, including the boundaries
    assert [classify(p) for p in (100, 90, 89.9, 70, 69.9, 50, 30.1, 30, 10.1, 10, 0)] == \
        ["much_long", "much_long", "long", "long", "usual", "usual", "usual", "short", "short", "much_short", "much_short"]
    # 8. a spell within 2 days of the median is "about usual" even when its rank is extreme
    b = [3] * 5 + [4] * 10 + [5] * 8 + [6] * 4 + [8] * 3                      # median 4
    assert rate(3, b) == "usual" and rate(6, b) == "usual" and classify(pct_rank(3, b)) == "much_short"
    assert rate(7, b) == "much_long" and rate(1, b) == "much_short"
    # 9. windows: a late-March start gives a 90-day period that begins on that date; it is cut at the end of the saved days
    n = len(rs.date_range(2001))
    a, k = window(79, 2001, n)                       # day 79 = 20 March
    assert (a, k) == (19, 90), (a, k)
    assert window(79, 2004, len(rs.date_range(2004)))[0] == 19      # same calendar date in a leap year
    assert window(150, 2001, n) == (rs.date_range(2001).index(dt.date(2001, 5, 30)), 90)     # day 150 = 30 May
    a, k = window(250, 2001, n)                      # a start so late the period would run past 30 September
    assert a + k == n and k < 90, (a, k)
    print("self-test passed: 9 checks")


# ============================================================ data
def load_saved(gdf):
    """The daily rainfall saved by the rainy-season tracker, as {date: array}, or None when it is missing or out of date."""
    if not CACHE_FILE.exists():
        return None
    z = np.load(CACHE_FILE, allow_pickle=False)
    if z["ids"].tolist() != gdf.shapeID.tolist():
        return None
    vals, dates = z["vals"], z["dates"]
    return {dt.date.fromordinal(int(o)): vals[i] for i, o in enumerate(dates)}


def year_matrix(daily, y, n):
    days = rs.date_range(y)
    m = np.full((len(days), n), np.nan, "float32")
    for k, d in enumerate(days):
        v = daily.get(d)
        if v is not None:
            m[k] = v
    return days, m


def dtext(d):
    return f"{d.day} {MON[d.month - 1]}"


def plural(n, word="day"):
    return f"{n} {word}{'' if n == 1 else 's'}"


# ============================================================ analysis
def build(daily, gdf, cur, today, demo):
    n = len(gdf)
    zone, years, res = rs.analyse(daily, gdf, cur, today, BASELINE[0])
    base_years = [y for y in years if BASELINE[0] <= y <= BASELINE[1]]
    need = min(rs.MIN_BASELINE_YEARS, max(5, len(base_years) * 2 // 3))
    mats = {y: year_matrix(daily, y, n) for y in years}
    days_cur, m_cur = mats[cur]
    seen = np.where(~np.isnan(m_cur).all(axis=1))[0]
    last_cur = int(seen.max()) if len(seen) else -1
    labels = [str(y) for y in years]
    districts = {}

    def not_rated(row, why):
        return {"name": row.shapeName, "cat": "not_rated", "big": "–", "big_note": why, "tip": "Not rated",
                "rows": [], "v": [None] * len(years), "c": ["not_rated"] * len(years)}

    for i, row in gdf.iterrows():
        ons = [res[i][y]["doy"] for y in base_years if res[i].get(y) and res[i][y]["kind"] == "onset"]
        if len(ons) < need:
            districts[row.shapeID] = not_rated(row, "Too few years with a clear start of the rains to work out the usual period.")
            continue
        med = float(np.median(ons))
        a_cur, k_cur = window(med, cur, len(days_cur))
        nd = min(k_cur, last_cur - a_cur + 1)                       # days of the period that have data so far this year
        if nd < MIN_MEASURED:
            districts[row.shapeID] = {"name": row.shapeName, "cat": "not_yet", "big": "–",
                                      "big_note": f"The period starts on {dtext(days_cur[a_cur])}; less than {MIN_MEASURED} days of it have passed.",
                                      "tip": "Too early", "rows": [], "v": [None] * len(years), "c": ["not_yet"] * len(years)}
            continue
        partial = nd < k_cur
        per = {}
        for y in years:
            days, m = mats[y]
            a, _ = window(med, y, len(days))
            x = m[a:a + nd, i]
            if len(x) < nd or np.isnan(x).mean() > 1 - MIN_DATA:
                per[y] = None
                continue
            per[y] = summarise(x)
        now = per.get(cur)
        base = [per[y][0] for y in base_years if per.get(y)]
        if now is None or len(base) < need:
            districts[row.shapeID] = not_rated(row, "Rainfall days are missing for this period, so the longest spell cannot be worked out.")
            continue
        L, s, c10, rain = now
        cat = rate(L, base)
        med_len = float(np.median(base))
        longest = max(base)
        longest_year = [y for y in base_years if per.get(y) and per[y][0] == longest][0]
        c10_med = float(np.median([per[y][2] for y in base_years if per.get(y)]))
        rain_med = float(np.median([per[y][3] for y in base_years if per.get(y)]))
        k_short, k_equal = int((np.array(base) < L).sum()), int((np.array(base) == L).sum())
        win = f"{dtext(days_cur[a_cur])} to {dtext(days_cur[a_cur + nd - 1])}"
        when = f"{dtext(days_cur[a_cur + s])} to {dtext(days_cur[a_cur + s + L - 1])}" if L > 0 else "–"
        usual_text = plural(int(round(med_len)))
        note = (f"Longest run of days under {DRY_MM:g} mm of rain, {win}{' (the season is still running)' if partial else ''}. "
                f"Longer than in {k_short} of {len(base)} years ({BASELINE[0]}–{BASELINE[1]})"
                f"{f', equal in {k_equal}' if k_equal else ''}. Usual (median): {usual_text}.")
        rows = [[f"Longest dry spell, {cur}", plural(L)],
                ["When it happened", when],
                ["Usual longest spell (median)", usual_text],
                [f"Longest in {BASELINE[0]}–{BASELINE[1]}", f"{plural(int(longest))} ({longest_year})"],
                [f"Spells of {LONG_SPELL} days or more", f"{c10} (usual: {int(round(c10_med))})"],
                ["Rain in the period", f"{round(rain)} mm (usual: {round(rain_med)} mm)"],
                ["Period measured", win + (f", {nd} of {k_cur} days" if partial else "")]]
        v, c = [], []
        for y in years:
            p = per.get(y)
            v.append(int(p[0]) if p else None)
            c.append(rate(p[0], base) if p else "not_rated")
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat, "big": plural(L), "big_note": note,
            "tip": f"{NAMES[cat]} · {plural(L)}", "rows": rows, "v": v, "c": c,
            "bc": [COLORS[k] for k in c], "bt": [NAMES[k].lower() if k not in ("not_rated",) else "no value" for k in c],
        }
    return districts, labels


def render(districts, labels, cur, demo, source):
    return {
        "label": "Dry spells", "title": f"Longest dry spell in the main rainy season, {cur} (experimental)",
        "subtitle": f"Days in a row under {DRY_MM:g} mm of rain, over {SPAN} days from the usual start of the rains, compared with {BASELINE[0]}–{BASELINE[1]}",
        "source": source, "demo": demo, "categories": CATEGORIES,
        "how": ("EXPERIMENTAL. This map shows the longest run of dry days in each district during the main rainy season, "
                f"compared with the same dates in {BASELINE[0]}–{BASELINE[1]}. A dry day is a day with under {DRY_MM:g} mm of rain. "
                f"The period starts on the district's usual start of the rains (see the Rainy season tab) and lasts {SPAN} days, "
                "the same dates in every year. The colour shows where this year's longest spell ranks among those years in the same "
                f"district, so a 10-day spell can be about usual in one district and much longer than usual in another. A spell within {MIN_DIFF} days of the usual is always shown as about usual. "
                "The number in the pop-up is the length in days. Southern districts have two rainy seasons; this map covers the first (main) season only."),
        "limits": [
            "Experimental, version 0.1. The dry-spell lengths have not been checked against rain-gauge records. The start dates that place the period were checked against 14 Ghana Meteorological Agency rain gauges and typically differ from the gauges by about three weeks.",
            "Rain is averaged over each district before dry days are counted. Where storms are patchy, a single farm can have a longer dry spell than the district average shows, so these figures tend to be shorter than what one field experiences.",
            f"A day with under {DRY_MM:g} mm counts as dry. Satellite-and-gauge rainfall often records light rain on days that were dry at a gauge, which also shortens dry spells. A different threshold would give different lengths.",
            "The period is the same dates every year, from the usual start of the rains. A year in which the rains start late therefore shows a long dry spell at the start of the period.",
            "Only the main rainy season is covered, and the saved rainfall ends on 30 September. The second, shorter season in the south is not measured.",
            "This is not a forecast, and it is not planting or crop advice. How much a dry spell matters depends on the crop and its growth stage.",
            "Recent days use preliminary rainfall that can be revised, so a spell in progress can change by a few days.",
            "The rainfall estimate is on a grid of about 5 km, so it hides differences inside a district.",
        ],
        "credits": [{"text": "Rainfall: CHIRPS daily, Climate Hazards Center, UC Santa Barbara", "url": "https://www.chc.ucsb.edu/data/chirps"}],
        "chart": {"kind": "bars", "unit": "days", "x": labels,
                  "caption": f"Longest dry spell in the period each year, days ({labels[0]} to {labels[-1]})"},
        "districts": districts,
        "build": BUILD,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    ap.add_argument("--self-test", action="store_true", help="test the rules, then stop")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    import geopandas as gpd
    gdf = gpd.read_file(ROOT / "data" / "districts.geojson").reset_index(drop=True)
    today = dt.date.today()
    if args.demo:
        daily, cur = rs.load_demo(gdf, today)
        source = "DEMO (made-up numbers)"
    else:
        daily = load_saved(gdf)
        if not daily:
            print("Dry spells skipped: the saved daily rainfall (cache/rainy_season_daily.npz) is missing or does not match the districts. "
                  "Build the rainy-season layer first (rainseason = full); this layer needs no download of its own.")
            return
        cur = today.year if today >= dt.date(today.year, *rs.FETCH_FROM) else today.year - 1
        daily = {d: v for d, v in daily.items() if d.year <= cur}
        if not any(d.year == cur for d in daily):
            print(f"Dry spells skipped: no saved rainfall for {cur} yet.")
            return
        source = rs.PRODUCT
    districts, labels = build(daily, gdf, cur, today, args.demo)
    rated = sum(1 for d in districts.values() if d["cat"] not in ("not_rated", "not_yet"))
    if not rated:
        sys.exit("No district could be rated. Check the saved rainfall (too few baseline years?).")
    write_layer("dryspell", render(districts, labels, cur, args.demo, source))


if __name__ == "__main__":
    main()
