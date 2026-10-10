#!/usr/bin/env python3
"""
Tinga Lens - check the rainy-season layer against rain gauges.

For each gauge in data/source/station_onsets.json (start of the rains found from gauge records, 1991-2015),
this takes the CHIRPS daily rainfall already saved for the district that contains the gauge, finds the start
of the rains in each year with the same rule, and compares the two. It repeats this with a few settings of the
rule (what counts as a dry day, how much rain the first test needs) to see which fits the gauges best.

Needs the saved daily rainfall (cache/rainy_season_daily.npz), so it only works after the rainy-season layer has
been built once. It downloads nothing and publishes nothing.

Run in Actions: Run workflow, rainseason = validate.   Locally: python scripts/validate_rainseason.py
"""
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CACHE, ROOT  # noqa: E402

spec = importlib.util.spec_from_file_location("rs", HERE / "rainy_season.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

DRY_VALUES = [1.0, 2.0, 3.0, 5.0]      # mm: a day under this is a dry day
RAIN_VALUES = [20.0, 25.0]             # mm in 3 days for the first test


def day_text(doy):
    return (dt.date(2001, 1, 1) + dt.timedelta(int(round(doy)) - 1)).strftime("%d %b")


def load():
    import geopandas as gpd
    from shapely.geometry import Point
    f = CACHE / "rainy_season_daily.npz"
    if not f.exists():
        sys.exit("No saved daily rainfall found (cache/rainy_season_daily.npz). Build the layer first (rainseason = full).")
    z = np.load(f, allow_pickle=False)
    ids, dates, vals = z["ids"].tolist(), z["dates"], z["vals"]
    daily = {dt.date.fromordinal(int(o)): vals[i] for i, o in enumerate(dates)}
    gdf = gpd.read_file(ROOT / "data" / "districts.geojson").reset_index(drop=True)
    col = {sid: k for k, sid in enumerate(ids)}
    st = json.loads((ROOT / "data" / "source" / "station_onsets.json").read_text())["stations"]
    rows = []
    for s in st:
        p = Point(s["lon"], s["lat"])
        hit = gdf[gdf.geometry.contains(p)]
        if hit.empty:
            hit = gdf.iloc[[int(gdf.geometry.distance(p).values.argmin())]]
        r = hit.iloc[0]
        if r.shapeID not in col:
            print(f"  {s['name']}: district {r.shapeName} not in the saved rainfall, skipped")
            continue
        rows.append((s, r.shapeName, col[r.shapeID]))
    return daily, rows


def satellite_onsets(daily, k, zone, years):
    (m0, d0), (m1, d1) = rs.WINDOW[zone]
    out = {}
    for y in years:
        days = rs.date_range(y)
        r = np.array([daily[d][k] if d in daily else np.nan for d in days], "float32")
        if np.isnan(r).mean() > 0.1:
            continue
        a, b = days.index(dt.date(y, m0, d0)), days.index(dt.date(y, m1, d1))
        kind, i, _ = rs.find_onset(r, a, b)
        if kind == "onset":
            out[y] = (days[i] - dt.date(y, 1, 1)).days + 1
    return out


def main():
    daily, rows = load()
    print(f"{len(rows)} gauges matched to districts\n")
    results = {}
    for dry in DRY_VALUES:
        for rain in RAIN_VALUES:
            rs.DRY_MM, rs.RAIN_MM = dry, rain
            diffs, per, pairs = [], [], []
            for s, name, k in rows:
                g = {int(y): v for y, v in s["onset_doy"].items()}
                sat = satellite_onsets(daily, k, s["zone"], sorted(g))
                common = sorted(set(g) & set(sat))
                if len(common) < 8:
                    continue
                d = np.array([sat[y] - g[y] for y in common], float)
                gv = np.array([g[y] for y in common], float)
                sv = np.array([sat[y] for y in common], float)
                r = float(np.corrcoef(gv, sv)[0, 1]) if gv.std() > 0 and sv.std() > 0 else float("nan")
                per.append((s["name"], name, len(common), float(np.median(d)), float(np.mean(np.abs(d))), r,
                            float(np.median(gv)), float(np.median(sv))))
                diffs.extend(d.tolist())
                pairs.append(r)
            diffs = np.array(diffs)
            results[(dry, rain)] = (per, diffs, np.nanmean(pairs) if pairs else float("nan"))
    print("Setting                         pairs  median gap   mean |gap|  within 14 days  mean correlation")
    print("                                       (sat - gauge)")
    for (dry, rain), (per, diffs, r) in results.items():
        if len(diffs) == 0:
            continue
        print(f"dry day < {dry:.0f} mm, 3-day >= {rain:.0f} mm   {len(diffs):4d}   {np.median(diffs):+6.1f} d    {np.mean(np.abs(diffs)):6.1f} d      "
              f"{np.mean(np.abs(diffs) <= 14):4.0%}          {r:5.2f}")
    best = min((kv for kv in results.items() if len(kv[1][1])), key=lambda kv: np.mean(np.abs(kv[1][1])))
    print(f"\nBest fit by mean absolute gap: dry day < {best[0][0]:.0f} mm, 3-day >= {best[0][1]:.0f} mm")
    for label, key in (("CURRENT SETTING (1 mm, 20 mm)", (1.0, 20.0)), (f"BEST ({best[0][0]:.0f} mm, {best[0][1]:.0f} mm)", best[0])):
        print(f"\n{label}: station, district, years, median gap (sat-gauge), mean |gap|, correlation, gauge median, satellite median")
        for n, dn, ny, md, ma, r, gm, sm in sorted(results[key][0], key=lambda t: t[3]):
            print(f"  {n:18} {dn:26} {ny:3d}  {md:+6.1f} d  {ma:5.1f} d  r={r:5.2f}  gauge {day_text(gm)}  satellite {day_text(sm)}")
    print("\nVALIDATION DONE: nothing published.")


if __name__ == "__main__":
    main()
