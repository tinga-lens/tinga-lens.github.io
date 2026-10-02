#!/usr/bin/env python3
"""
Tinga Lens - soil moisture layer.

Source: NASA SMAP Level-4 (SPL4SMGP), 9 km, surface (0-5 cm) and root zone
(0-100 cm) soil moisture. It merges SMAP satellite observations into a land
model, so it has no gaps.

Indicator: average root-zone soil moisture for the latest complete month,
compared with the same calendar month in every earlier year of the SMAP record
(2015 onwards).

To keep downloads small, each month is sampled on SAMPLE_DAYS at one time of
day, and only the Ghana window of each file is read.

Needs a free NASA Earthdata login, given through environment variables:
  EARTHDATA_USERNAME and EARTHDATA_PASSWORD   (or EARTHDATA_TOKEN)

Run:
  python scripts/smap.py          # real data
  python scripts/smap.py --demo   # made-up data, only for previewing the site
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, CACHE, MON, WETNESS, load_districts, wetness_category, write_layer, ym_text  # noqa: E402

# ---- settings you may want to change -------------------------------------
SHORT_NAME = "SPL4SMGP"
VERSION = "008"                         # change here if NASA releases a new version
FIRST_MONTH = (2015, 4)                 # first full month of SMAP L4
SAMPLE_DAYS = [3, 8, 13, 18, 23, 28]    # days of each month that are read
SAMPLE_TIME = "T103000"                 # one 3-hourly file per sampled day (10:30 UTC)
MIN_REF_YEARS = 5                       # earlier years needed before a month is rated
HISTORY_MONTHS = 12
SAVE_EVERY = 25                         # save progress after this many files
# --------------------------------------------------------------------------
CACHE_FILE = CACHE / "smap_l4.npz"


def month_list(first, last):
    out, (y, m) = [], first
    while (y, m) <= last:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def day_key(y, m, d):
    return f"{y}{m:02d}{d:02d}"


def load_cache():
    if not CACHE_FILE.exists():
        return {}, None
    z = np.load(CACHE_FILE, allow_pickle=False)
    root, surf = z["root"], z["surf"]
    have = {k: (root[i], surf[i]) for i, k in enumerate(z["days"].tolist())}
    return have, (z["lat"], z["lon"])


def save_cache(have, grid):
    CACHE.mkdir(exist_ok=True)
    days = sorted(have)
    np.savez_compressed(CACHE_FILE, days=np.array(days), lat=grid[0], lon=grid[1],
                        root=np.stack([have[k][0] for k in days]), surf=np.stack([have[k][1] for k in days]))


def read_window(fobj, grid_slices):
    """Read the Ghana window of one SMAP file. Returns root, surface, (rows, cols, lat, lon)."""
    import h5py
    with h5py.File(fobj, "r") as f:
        if grid_slices is None:
            lat = f["cell_lat"][:, 0]
            lon = f["cell_lon"][0, :]
            rows = np.nonzero((lat >= BBOX[1]) & (lat <= BBOX[3]))[0]
            cols = np.nonzero((lon >= BBOX[0]) & (lon <= BBOX[2]))[0]
            grid_slices = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1),
                           lat[rows[0]:rows[-1] + 1], lon[cols[0]:cols[-1] + 1])
        r, c = grid_slices[0], grid_slices[1]
        out = []
        for name in ("sm_rootzone", "sm_surface"):
            a = f["Geophysical_Data"][name][r, c].astype("float32")
            a[(a < 0) | (a > 1)] = np.nan          # fill value is -9999
            out.append(a)
    return out[0], out[1], grid_slices


def load_real(today):
    import earthaccess
    auth = earthaccess.login(strategy="environment")
    if not getattr(auth, "authenticated", False):
        sys.exit("NASA Earthdata login failed. Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD.")

    have, grid = load_cache()
    slices = None
    months = month_list(FIRST_MONTH, (today.year, today.month))
    done = 0
    for (y, m) in months:
        wanted = [day_key(y, m, d) for d in SAMPLE_DAYS]
        missing = [k for k in wanted if k not in have]
        if not missing:
            continue
        last_day = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
        found = earthaccess.search_data(short_name=SHORT_NAME, version=VERSION, count=-1,
                                        temporal=(f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last_day}"))
        pick = {}
        for g in found:
            name = g.data_links()[0].rsplit("/", 1)[1]
            for k in missing:
                if f"_{k}{SAMPLE_TIME}_" in name:
                    pick[k] = g
        if not pick:
            continue
        keys = sorted(pick)
        files = earthaccess.open([pick[k] for k in keys])
        for k, fobj in zip(keys, files):
            root, surf, slices_new = read_window(fobj, slices)
            if slices is None:
                slices = slices_new
                if grid is not None and (len(grid[0]) != len(slices[2]) or len(grid[1]) != len(slices[3])):
                    sys.exit("SMAP grid differs from the cache; delete the cache folder and run again.")
                grid = (slices[2], slices[3])
            have[k] = (root, surf)
            done += 1
            if done % SAVE_EVERY == 0:
                save_cache(have, grid)
                print(f"  {done} files read (up to {k})", flush=True)
    if not have:
        sys.exit(f"No {SHORT_NAME} v{VERSION} files were found. Check VERSION in scripts/smap.py.")
    save_cache(have, grid)
    print(f"{done} new file(s) read, {len(have)} in total")
    return have, grid, f"NASA SMAP L4 ({SHORT_NAME} v{VERSION})"


def load_demo(today):
    rng = np.random.default_rng(11)
    lat = np.arange(BBOX[3] - 0.04, BBOX[1], -0.08)
    lon = np.arange(BBOX[0] + 0.04, BBOX[2], 0.08)
    la = lat[:, None] * np.ones((1, len(lon)))
    lo = lon[None, :] * np.ones((len(lat), 1))
    north = np.clip((la - 6.5) / 3.0, 0, 1)
    last = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    have = {}
    for (y, m) in month_list(FIRST_MONTH, last):
        season = north * (0.12 + 0.16 * np.exp(-((m - 8.5) ** 2) / 6)) + (1 - north) * (0.24 + 0.08 * np.sin((m - 3) / 12 * 2 * np.pi))
        f = np.exp(rng.normal(0, 0.06) + rng.normal(0, 0.04) * (la - 8) + rng.normal(0, 0.04) * (lo + 1))
        for d in SAMPLE_DAYS:
            root = (season * f).astype("float32")
            have[day_key(y, m, d)] = (root, (root * 0.9).astype("float32"))
    return have, (lat, lon), "DEMO (made-up numbers)"


def cells_per_district(gdf, lat, lon, valid):
    """For each district, the land grid cells whose centre falls inside it (or the nearest one)."""
    la, lo = np.meshgrid(lat, lon, indexing="ij")
    ok = np.nonzero(valid.ravel())[0]                  # cells that hold data (not sea)
    la, lo = la.ravel()[ok], lo.ravel()[ok]
    pts = gpd.GeoDataFrame({"cell": ok}, geometry=gpd.points_from_xy(lo, la), crs=gdf.crs)
    hit = gpd.sjoin(pts, gdf[["geometry"]], predicate="within")
    groups = hit.groupby("index_right")["cell"].apply(np.array).to_dict()
    out = []
    for i, geom in enumerate(gdf.geometry):
        if i in groups:
            out.append(groups[i])
        else:   # district smaller than a grid cell: use the nearest cell centre
            p = geom.representative_point()
            out.append(np.array([ok[np.argmin((la - p.y) ** 2 + (lo - p.x) ** 2)]]))
    return out


def monthly_district_means(have, cells):
    """Months with every sample day present -> (months, root[time, district], surf[time, district])."""
    months, root, surf = [], [], []
    ym = sorted({(int(k[:4]), int(k[4:6])) for k in have})
    for (y, m) in ym:
        keys = [day_key(y, m, d) for d in SAMPLE_DAYS]
        if not all(k in have for k in keys):
            continue
        r = np.mean(np.stack([have[k][0] for k in keys]), axis=0).ravel()
        s = np.mean(np.stack([have[k][1] for k in keys]), axis=0).ravel()
        months.append((y, m))
        root.append([np.nanmean(r[c]) for c in cells])
        surf.append([np.nanmean(s[c]) for c in cells])
    return months, np.array(root), np.array(surf)


def assess(months, x, t):
    """Compare month t with the same calendar month in all earlier years."""
    y, m = months[t]
    ref_i = [i for i, (yy, mm) in enumerate(months) if mm == m and yy < y]
    if len(ref_i) < MIN_REF_YEARS:
        return None
    ref, cur = x[ref_i], x[t]
    normal = ref.mean(axis=0)
    pctile = ((ref < cur).sum(axis=0) + 0.5 * (ref == cur).sum(axis=0)) / len(ref_i) * 100
    return cur, normal, cur / normal * 100, pctile, len(ref_i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    args = ap.parse_args()
    today = dt.date.today()
    gdf = load_districts()
    have, (lat, lon), source = (load_demo if args.demo else load_real)(today)
    valid = ~np.isnan(next(iter(have.values()))[0])
    cells = cells_per_district(gdf, lat, lon, valid)
    months, root, surf = monthly_district_means(have, cells)
    if not months:
        sys.exit("No complete month of SMAP data yet.")
    T = len(months) - 1
    now = assess(months, root, T)
    if now is None:
        sys.exit("Not enough earlier years to compare with.")
    cur, normal, pct, pctile, n = now
    s_now = assess(months, surf, T)
    steps = list(range(max(0, T - HISTORY_MONTHS + 1), T + 1))
    hist = [assess(months, root, t) for t in steps]
    y, m = months[T]
    label = f"{y}-{m:02d}"
    print(f"{len(months)} complete months, latest = {label}, compared with {n} earlier years, grid {len(lat)}x{len(lon)}")

    notes = ["driest 10% of years", "driest 30% of years", "middle 40% of years",
             "wettest 30% of years", "wettest 10% of years"]
    cats = [dict(c, note=t) for c, t in zip(WETNESS, notes)]
    names = {c["key"]: c["label"] for c in cats}
    districts = {}
    for i, row in gdf.iterrows():
        if np.isnan(cur[i]):
            continue
        cat = wetness_category(pctile[i])
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{pct[i]:.0f}%",
            "big_note": f"of normal root-zone soil moisture, {ym_text(label)}",
            "tip": f"{names[cat]} · {pct[i]:.0f}% of normal",
            "rows": [
                ["Root zone (0–100 cm)", f"{cur[i]:.2f} m³/m³"],
                [f"Normal for {MON[m - 1]}", f"{normal[i]:.2f} m³/m³"],
                ["Surface (0–5 cm)", f"{s_now[0][i]:.2f} m³/m³ ({s_now[2][i]:.0f}% of normal)"],
                ["Earlier years that were drier", f"{round(pctile[i] / 100 * n)} of {n}"],
            ],
            "v": [None if h is None else round(float(h[2][i] - 100), 1) for h in hist],
            "c": ["normal" if h is None else wetness_category(h[3][i]) for h in hist],
        }

    write_layer("soil", {
        "label": "Soil moisture", "title": "Root-zone soil moisture compared with normal",
        "subtitle": f"{ym_text(label)}, against {MON[m - 1]} in {n} earlier years",
        "source": source, "demo": bool(args.demo), "categories": cats,
        "how": (f"Each district shows the average moisture in the top metre of soil for {ym_text(label)}, compared with "
                f"{MON[m - 1]} in each earlier year since 2015. \"Very dry\" means this year ranks in the driest 10% of "
                "those years, \"dry\" in the driest 30%, and the same in reverse for \"wet\" and \"very wet\"."),
        "limits": [
            "The values come from NASA's SMAP Level-4 product, which blends satellite observations into a land model. It is an estimate, not a direct measurement at depth.",
            f"The SMAP record starts in 2015, so \"normal\" rests on only {n} earlier years. Rankings are coarser than for rainfall.",
            "The grid is about 9 km. It suits district averages, not individual farms, and small districts rest on one or two grid cells.",
            "Under dense forest in the south the satellite signal is weak, so values there lean more on the model.",
            f"Each month is sampled on {len(SAMPLE_DAYS)} days at one time of day, not averaged over every hour.",
            "The estimates have not been checked against soil sensors in Ghana.",
        ],
        "credits": [{"text": "Soil moisture: NASA SMAP L4 (SPL4SMGP), NSIDC DAAC", "url": "https://nsidc.org/data/spl4smgp"}],
        "chart": {"kind": "diverging", "cap": 50, "unit": "% vs normal",
                  "x": [MON[months[t][1] - 1] for t in steps],
                  "caption": "Past 12 months, root zone", "top": "wetter than normal", "bottom": "drier"},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
