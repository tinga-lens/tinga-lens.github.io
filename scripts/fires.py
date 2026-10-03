#!/usr/bin/env python3
"""
Tinga Lens - fires layer.

Source: NASA FIRMS active fire detections from the VIIRS sensor (375 m), from 2012.
Each detection is a satellite overpass seeing a hot spot; one fire can produce
several detections.

Indicator: detections in each district over the last WINDOW days, compared with
the same days of the year in every earlier year.

Needs a free FIRMS map key in the environment variable FIRMS_MAP_KEY
(request one at https://firms.modaps.eosdis.nasa.gov/api/map_key/).

Run:
  python scripts/fires.py          # real data
  python scripts/fires.py --demo   # made-up data, only for previewing the site
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, CACHE, DATA, MON, load_districts, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
SENSOR = "VIIRS_SNPP"            # FIRMS source; "_SP" (final) and "_NRT" (recent) are added automatically
START = dt.date(2012, 1, 20)     # first day of the VIIRS record
WINDOW = 30                      # days compared
CHUNK = 5                        # days per request (FIRMS allows at most 5)
QUIET = 3                        # under this many detections now and normally, a district is "quiet"
MIN_REF_YEARS = 5
SAVE_EVERY = 50                  # save progress after this many requests
POINT_DAYS = 7                   # individual detections are published for this many recent days
POINT_LIMIT = 15000              # most detections published (the strongest are kept if there are more)
API = os.environ.get("TINGA_FIRMS_BASE", "https://firms.modaps.eosdis.nasa.gov/api")
# --------------------------------------------------------------------------
CACHE_FILE = CACHE / "fires.npz"

CATS = [
    {"key": "far_fewer", "label": "Far fewer fires", "note": "under half of normal", "color": "#4575b4", "max": 50},
    {"key": "fewer", "label": "Fewer", "note": "50 to 80%", "color": "#abd9e9", "max": 80},
    {"key": "normal", "label": "Near normal", "note": "80 to 125%", "color": "#f3efe4", "max": 125},
    {"key": "more", "label": "More", "note": "125 to 200%", "color": "#fdae61", "max": 200},
    {"key": "far_more", "label": "Far more fires", "note": "over double normal", "color": "#d73027", "max": 1e12},
    {"key": "quiet", "label": "Quiet", "note": "few fires now or normally", "color": "#bdbdbd"},
]


def get(s, url):
    for attempt in range(1, 5):
        try:
            r = s.get(url, timeout=120)
            if r.status_code == 200:
                return r.text
            msg = f"HTTP {r.status_code}"
        except Exception as e:
            msg = type(e).__name__
        print(f"  request failed ({msg}), attempt {attempt}", flush=True)
        time.sleep(30 * attempt)       # also covers the FIRMS limit of 5000 requests per 10 minutes
    return None


def availability(s, key):
    """Dates covered by the final (SP) and recent (NRT) records. Returns {source: (first, last)}."""
    out = {}
    txt = get(s, f"{API}/data_availability/csv/{key}/ALL")
    if txt and txt.lower().startswith("data_id"):
        df = pd.read_csv(io.StringIO(txt))
        for _, r in df.iterrows():
            out[r["data_id"]] = (dt.date.fromisoformat(r["min_date"]), dt.date.fromisoformat(r["max_date"]))
    elif txt and "invalid" in txt.lower():
        sys.exit("FIRMS did not accept the map key. Check the FIRMS_MAP_KEY secret.")
    return out


def fetch(s, key, source, start, days):
    """Detections for `days` days from `start`. Returns a table, or None if the request failed."""
    box = ",".join(str(v) for v in BBOX)
    txt = get(s, f"{API}/area/csv/{key}/{source}/{box}/{days}/{start.isoformat()}")
    if txt is None:
        return None
    if not txt.lstrip().lower().startswith("latitude"):
        if "invalid" in txt.lower() and "key" in txt.lower():
            sys.exit("FIRMS did not accept the map key. Check the FIRMS_MAP_KEY secret.")
        print(f"  unexpected reply for {source} {start}: {txt[:120]!r}")
        return None
    df = pd.read_csv(io.StringIO(txt))
    if df.empty:
        return df
    df = df[~df["confidence"].astype(str).str.lower().str.startswith("l")]      # drop low-confidence detections
    if "type" in df.columns:
        df = df[df["type"].fillna(0).astype(int) == 0]                         # keep vegetation fires, drop gas flares etc.
    return df


def count_by_district(df, gdf, day0, ndays):
    """Table of detections -> counts[day, district]."""
    out = np.zeros((ndays, len(gdf)), "int32")
    if df is None or df.empty:
        return out
    pts = gpd.GeoDataFrame({"day": (pd.to_datetime(df["acq_date"]).dt.date.map(lambda d: (d - day0).days)).to_numpy()},
                           geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs=gdf.crs)
    hit = gpd.sjoin(pts, gdf[["geometry"]], predicate="within")
    hit = hit[(hit["day"] >= 0) & (hit["day"] < ndays)]
    np.add.at(out, (hit["day"].to_numpy(), hit["index_right"].to_numpy()), 1)
    return out


def write_points(frames, gdf, first, last):
    """Publish each recent detection (place, time, strength) for the map."""
    cols = ["lat", "lon", "date", "time", "confidence", "frp", "daynight", "district"]
    rows, capped = [], False
    if frames:
        df = pd.concat(frames, ignore_index=True)
        df = df[(df["acq_date"] >= first.isoformat()) & (df["acq_date"] <= last.isoformat())]
        if len(df):
            pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs=gdf.crs)
            hit = gpd.sjoin(pts, gdf[["shapeName", "geometry"]], predicate="within")      # keeps detections inside Ghana only
            if len(hit) > POINT_LIMIT and "frp" in hit:
                hit, capped = hit.sort_values("frp", ascending=False).head(POINT_LIMIT), True
            for _, r in hit.sort_values("acq_date").iterrows():
                t = r.get("acq_time", "")
                t = f"{int(t):04d}" if str(t).strip() not in ("", "nan") else ""
                frp = r.get("frp", "")
                rows.append([round(float(r["latitude"]), 4), round(float(r["longitude"]), 4), r["acq_date"],
                             f"{t[:2]}:{t[2:]}" if t else "", str(r.get("confidence", "")),
                             "" if pd.isna(frp) or frp == "" else round(float(frp), 1),
                             "" if pd.isna(r.get("daynight", "")) else str(r.get("daynight", "")), r["shapeName"]])
    (DATA / "fire_points.json").write_text(json.dumps({
        "through": last.isoformat(), "days": POINT_DAYS, "capped": capped, "fields": cols, "points": rows,
        "source": f"NASA FIRMS {SENSOR.replace('_', ' ')}, low-confidence detections removed",
    }, separators=(",", ":")))
    print(f"Wrote data/fire_points.json: {len(rows)} detections, {first} to {last}")


def load_real(gdf, today):
    import requests
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        sys.exit("FIRMS_MAP_KEY is not set.")
    s = requests.Session()
    avail = availability(s, key)
    sp, nrt = f"{SENSOR}_SP", f"{SENSOR}_NRT"
    print("FIRMS record:", {k: tuple(map(str, v)) for k, v in avail.items() if k in (sp, nrt)} or "availability not reported")
    sp_last = avail.get(sp, (None, today - dt.timedelta(days=120)))[1]     # final data usually lags a few months
    last_day = min(avail.get(nrt, (None, today))[1], today)

    ndays = (last_day - START).days + 1
    counts = np.zeros((ndays, len(gdf)), "int32")
    final_through = START - dt.timedelta(days=1)       # everything up to here is final and never re-read
    if CACHE_FILE.exists():
        z = np.load(CACHE_FILE, allow_pickle=False)
        old = z["counts"]
        if old.shape[1] == len(gdf):
            n = min(len(old), ndays)
            counts[:n] = old[:n]
            final_through = dt.date.fromisoformat(str(z["final_through"]))

    def save():
        CACHE.mkdir(exist_ok=True)
        np.savez_compressed(CACHE_FILE, counts=counts, final_through=np.array(final_through.isoformat()))

    d = final_through + dt.timedelta(days=1)
    total_chunks = max(0, ((last_day - d).days + CHUNK) // CHUNK)
    print(f"Reading {d} to {last_day}: about {total_chunks} request(s)")
    done, failed, stalled = 0, 0, False
    recent, first_recent = [], last_day - dt.timedelta(days=POINT_DAYS - 1)
    while d <= last_day:
        days = min(CHUNK, (last_day - d).days + 1)
        end = d + dt.timedelta(days=days - 1)
        i0 = (d - START).days
        if end <= sp_last:                               # fully inside the final record
            df = fetch(s, key, sp, d, days)
        elif d > sp_last:                                # fully in the recent, near-real-time record
            df = fetch(s, key, nrt, d, days)
        else:                                            # the block spans both: final days plus recent days
            a, b = fetch(s, key, sp, d, days), fetch(s, key, nrt, d, days)
            if a is None or b is None:
                df = None
            else:
                a = a[a["acq_date"] <= sp_last.isoformat()] if not a.empty else a
                b = b[b["acq_date"] > sp_last.isoformat()] if not b.empty else b
                df = pd.concat([a, b], ignore_index=True)
        if df is None:
            failed += 1
            stalled = True                               # do not mark later days as final past a gap
        else:
            counts[i0:i0 + days] = count_by_district(df, gdf, d, days)
            if end >= first_recent and not df.empty:
                recent.append(df)
            if end <= sp_last and not stalled:
                final_through = end
        done += 1
        if done % SAVE_EVERY == 0:
            save()
            print(f"  {done} requests done (up to {end})", flush=True)
        d = end + dt.timedelta(days=1)
    save()
    write_points(recent, gdf, first_recent, last_day)
    if failed:
        print(f"{failed} request(s) failed; those days will be read again next run.")
    if failed > total_chunks / 2 and total_chunks > 4:
        sys.exit("Most FIRMS requests failed; not publishing.")
    return counts, last_day, f"NASA FIRMS {SENSOR.replace('_', ' ')}"


def load_demo(gdf, today):
    rng = np.random.default_rng(9)
    last_day = today - dt.timedelta(days=1)
    ndays = (last_day - START).days + 1
    lat = gdf.geometry.representative_point().y.to_numpy()
    area = gdf.geometry.area.to_numpy()
    base = area / area.mean() * np.clip((lat - 5.5) / 3, 0.05, 1.5)
    doy = np.array([(START + dt.timedelta(days=i)).timetuple().tm_yday for i in range(ndays)])
    year = np.array([(START + dt.timedelta(days=i)).year for i in range(ndays)])
    season = np.exp(-(((doy + 60) % 365 - 75) ** 2) / 1800) + 0.03          # peaks around December-January
    yf = {y: rng.uniform(0.6, 1.5) for y in np.unique(year)}
    lam = season[:, None] * base[None, :] * np.array([yf[y] for y in year])[:, None] * 1.2
    return rng.poisson(lam).astype("int32"), last_day, "DEMO (made-up numbers)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    args = ap.parse_args()
    today = dt.date.today()
    gdf = load_districts()
    counts, last_day, source = (load_demo if args.demo else load_real)(gdf, today)

    def window(end):
        """Detections per district in the WINDOW days ending on `end`."""
        i1 = (end - START).days + 1
        return counts[max(0, i1 - WINDOW):i1].sum(axis=0) if i1 >= WINDOW else None

    cur = window(last_day)
    refs = []
    for y in range(last_day.year - 1, START.year - 1, -1):
        try:
            w = window(last_day.replace(year=y))
        except ValueError:                                # 29 February
            w = window(last_day.replace(year=y, day=28))
        if w is not None:
            refs.append(w)
    if cur is None or len(refs) < MIN_REF_YEARS:
        sys.exit("Not enough fire data to compare with earlier years.")
    refs = np.array(refs)
    normal = refs.mean(axis=0)
    n = len(refs)
    first = last_day - dt.timedelta(days=WINDOW - 1)
    period = f"{first.day} {MON[first.month - 1]} to {last_day.day} {MON[last_day.month - 1]} {last_day.year}"

    # monthly totals for the last 12 complete months (for the chart)
    months = []
    y, m = last_day.year, last_day.month
    for _ in range(12):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        months.append((y, m))
    months.reverse()
    monthly = []
    for (yy, mm) in months:
        a = (dt.date(yy, mm, 1) - START).days
        b = (dt.date(yy + (mm == 12), mm % 12 + 1, 1) - START).days
        monthly.append(counts[max(a, 0):max(b, 0)].sum(axis=0))
    monthly = np.array(monthly)

    districts = {}
    for i, row in gdf.iterrows():
        c, nm = int(cur[i]), float(normal[i])
        quiet = c < QUIET and nm < QUIET
        pct = c / nm * 100 if nm > 0 else float("inf")
        cat = "quiet" if quiet else next(k["key"] for k in CATS if pct < k.get("max", -1))
        more = int((refs[:, i] > c).sum())
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{c:,}",
            "big_note": f"fire detections, {period}" + ("" if quiet or nm == 0 else f" ({pct:.0f}% of normal)"),
            "tip": f"{c:,} detections" + ("" if quiet or nm == 0 else f" · {pct:.0f}% of normal"),
            "rows": [
                ["Normal for these dates", f"{nm:,.0f}"],
                ["Earlier years with more fires", f"{more} of {n}"],
                ["Past 12 months", f"{int(monthly[:, i].sum()):,}"],
            ],
            "v": [int(x) for x in monthly[:, i]],
            "c": [cat] * 12,
        }
    print(f"Fires through {last_day}: {int(cur.sum()):,} detections in the last {WINDOW} days (normal {normal.sum():,.0f}), {n} earlier years")

    # every complete month on record, for looking back
    all_months, (yy, mm) = [], (START.year, START.month + 1)          # first full month
    while (yy, mm) < (last_day.year, last_day.month):
        all_months.append((yy, mm))
        yy, mm = (yy + 1, 1) if mm == 12 else (yy, mm + 1)
    per_month = np.array([counts[(dt.date(a, b, 1) - START).days:(dt.date(a + (b == 12), b % 12 + 1, 1) - START).days].sum(axis=0)
                          for (a, b) in all_months])
    (DATA / "fires_history.json").write_text(json.dumps({
        "kind": "count", "months": [f"{a}-{b:02d}" for (a, b) in all_months], "base_label": f"Last {WINDOW} days",
        "breaks": [c["max"] for c in CATS[:4]], "quiet": QUIET, "min_years": MIN_REF_YEARS,
        "note": "Pick a year and month to see the detections in that month, compared with the same month in other years.",
        "counts": {row.shapeID: [int(v) for v in per_month[:, i]] for i, row in gdf.iterrows()},
    }, separators=(",", ":")))
    print(f"Wrote data/fires_history.json: {len(all_months)} months")

    write_layer("fires", {
        "history": "data/fires_history.json",
        "label": "Fires", "title": "Fire activity compared with normal",
        "subtitle": f"{period}, against the same dates in {n} earlier years",
        "source": source, "demo": bool(args.demo),
        "categories": [{k: c[k] for k in ("key", "label", "note", "color")} for c in CATS],
        "how": (f"Each district shows how many fire detections satellites recorded over the last {WINDOW} days, compared with "
                f"the average for the same dates in {n} earlier years. A detection is one satellite overpass seeing a hot spot "
                "about 375 metres across, so one fire can be counted several times."),
        "limits": [
            "Satellites pass over a few times a day and cannot see through thick cloud or smoke, so short or small fires are missed.",
            "Detections are not burned area. A district with many detections may have had a few long-lasting fires.",
            "Most fires in Ghana's savanna are seasonal bush and farm fires. The map does not say whether a fire was planned or harmful.",
            f"Districts with fewer than {QUIET} detections both now and normally are shown as quiet. The main fire season runs from about November to April.",
            "The most recent weeks use rapid-release data that NASA later revises.",
        ],
        "credits": [{"text": "Fires: NASA FIRMS, VIIRS 375 m active fire detections", "url": "https://firms.modaps.eosdis.nasa.gov/"}],
        "chart": {"kind": "bars", "unit": "detections", "x": [MON[mm - 1] for (_, mm) in months],
                  "caption": "Detections in each of the past 12 months", "top": "", "bottom": ""},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
