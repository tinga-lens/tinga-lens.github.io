#!/usr/bin/env python3
"""
Tinga Lens - vegetation greenness layer.

Source: NASA VIIRS monthly vegetation index (VNP13A3, 1 km NDVI), from 2012.
NDVI runs from about 0 (bare ground) to about 0.9 (dense green vegetation).

Indicator: average NDVI of each district for the latest month, compared with
the same calendar month in every earlier year.

Only good-quality pixels are used. In the rainy season the south is often
cloudy, so a district is not rated when too few of its pixels are usable.

Needs the same NASA Earthdata login as the soil moisture layer:
  EARTHDATA_USERNAME and EARTHDATA_PASSWORD   (or EARTHDATA_TOKEN)

Run:
  python scripts/vegetation.py          # real data
  python scripts/vegetation.py --demo   # made-up data, only for previewing the site
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, CACHE, DATA, MON, WETNESS, load_districts, wetness_category, write_layer, ym_text  # noqa: E402

# ---- settings you may want to change -------------------------------------
SHORT_NAME = "VNP13A3"
VERSION = "002"                          # change here if NASA releases a new version
TILES = ["h17v07", "h18v07", "h17v08", "h18v08"]   # the four 10-degree tiles covering Ghana
FIRST_MONTH = (2012, 2)                  # first full month of VIIRS
MAX_RELIABILITY = 4                      # pixel reliability rank kept (0 best ... 4 pass; 5+ poor or cloudy)
MIN_USABLE = 0.30                        # share of a district's pixels that must be usable
MIN_REF_YEARS = 5                        # earlier years needed before a month is rated
HISTORY_MONTHS = 12
SAVE_EVERY = 20
RETRIES = 3
# --------------------------------------------------------------------------
CACHE_FILE = CACHE / "vegetation.npz"

# the standard NASA sinusoidal grid used by MODIS and VIIRS land products
R = 6371007.181
TILE_M = 1111950.5197
X_MIN, Y_MAX = -20015109.354, 10007554.677
NPIX = 1200
SINU = f"+proj=sinu +R={R} +lon_0=0 +units=m +no_defs"


def tile_transform(tile):
    h, v = int(tile[1:3]), int(tile[4:6])
    pix = TILE_M / NPIX
    return Affine(pix, 0, X_MIN + h * TILE_M, 0, -pix, Y_MAX - v * TILE_M)


def district_index(gdf_sinu, tile):
    """Raster of district numbers (1..n, 0 = outside Ghana) on one tile's grid."""
    return rasterize(((g, i + 1) for i, g in enumerate(gdf_sinu.geometry)),
                     out_shape=(NPIX, NPIX), transform=tile_transform(tile), fill=0, dtype="int32")


def read_ndvi(fobj):
    """Return NDVI (float, NaN where missing) and the pixel reliability rank from one file."""
    import h5py
    found = {}

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            low = name.lower()
            if low.endswith("ndvi"):
                found["ndvi"] = obj
            elif "pixel reliability" in low:
                found["rel"] = obj

    with h5py.File(fobj, "r") as f:
        f.visititems(visit)
        if "ndvi" not in found or "rel" not in found:
            raise KeyError("NDVI or pixel reliability dataset not found in file")
        d = found["ndvi"]
        raw = d[...].astype("float32")
        sf = float(np.ravel(d.attrs.get("scale_factor", 10000.0))[0])
        rel = found["rel"][...].astype("int16")
    ndvi = raw / sf if sf > 1 else raw * sf        # stored as whole numbers, e.g. 6500 = 0.65
    ndvi[(ndvi < -0.2) | (ndvi > 1.0)] = np.nan
    return ndvi, rel


def read_with_retry(earthaccess, granule, key):
    for attempt in range(1, RETRIES + 1):
        try:
            fobj = earthaccess.open([granule])[0]
            try:
                return read_ndvi(fobj)
            finally:
                try:
                    fobj.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"  {key}: attempt {attempt} failed ({type(e).__name__}: {str(e)[:120]})", flush=True)
            if attempt < RETRIES:
                time.sleep(20 * attempt)
                try:
                    earthaccess.login(strategy="environment")
                except Exception:
                    pass
    return None


def tally(ndvi, rel, idx, nd):
    """Per district: sum of NDVI over usable pixels, and how many pixels were usable."""
    ok = (idx > 0) & ~np.isnan(ndvi) & (rel >= 0) & (rel <= MAX_RELIABILITY)
    s = np.bincount(idx[ok], weights=ndvi[ok], minlength=nd + 1)[1:]
    n = np.bincount(idx[ok], minlength=nd + 1)[1:]
    return s.astype("float32"), n.astype("int32")


def load_cache():
    if not CACHE_FILE.exists():
        return {}
    z = np.load(CACHE_FILE, allow_pickle=False)
    return {k: (z["s"][i], z["n"][i]) for i, k in enumerate(z["keys"].tolist())}


def save_cache(have):
    CACHE.mkdir(exist_ok=True)
    keys = sorted(have)
    np.savez_compressed(CACHE_FILE, keys=np.array(keys),
                        s=np.stack([have[k][0] for k in keys]), n=np.stack([have[k][1] for k in keys]))


def load_real(gdf, today):
    import earthaccess
    from common import earthdata_login
    earthdata_login()                                  # tries several times; exits with a plain message if NASA is unreachable
    have = load_cache()
    found = earthaccess.search_data(short_name=SHORT_NAME, version=VERSION, count=-1, bounding_box=BBOX,
                                    temporal=(f"{FIRST_MONTH[0]}-{FIRST_MONTH[1]:02d}-01", today.isoformat()))
    todo = {}
    for g in found:
        name = g.data_links()[0].rsplit("/", 1)[1]
        m = re.search(r"\.A(\d{4})(\d{3})\.(h\d{2}v\d{2})\.", name)
        if not m or m.group(3) not in TILES:
            continue
        day = dt.date(int(m.group(1)), 1, 1) + dt.timedelta(days=int(m.group(2)) - 1)
        key = f"{day.year}-{day.month:02d}|{m.group(3)}"
        if key not in have:
            todo[key] = g
    print(f"{len(found)} files listed, {len(todo)} to read, {len(have)} cached")
    if not found and not have:
        sys.exit(f"No {SHORT_NAME} v{VERSION} files were found. Check VERSION in scripts/vegetation.py.")

    gs = gdf.to_crs(SINU)
    index = {t: district_index(gs, t) for t in TILES}
    done, skipped = 0, []
    for key in sorted(todo):
        got = read_with_retry(earthaccess, todo[key], key)
        if got is None:
            skipped.append(key)
            continue
        have[key] = tally(got[0], got[1], index[key.split("|")[1]], len(gdf))
        done += 1
        if done % SAVE_EVERY == 0:
            save_cache(have)
            print(f"  {done} files read (up to {key})", flush=True)
    if skipped:
        print(f"Could not read {len(skipped)} file(s), they will be tried again next run: {', '.join(skipped)}")
    save_cache(have)
    total = sum(np.bincount(index[t].ravel(), minlength=len(gdf) + 1)[1:] for t in TILES)   # pixels per district
    return have, total, f"NASA VIIRS {SHORT_NAME} v{VERSION}"


def load_demo(gdf, today):
    rng = np.random.default_rng(5)
    nd = len(gdf)
    lat = gdf.geometry.representative_point().y.to_numpy()
    north = np.clip((lat - 6.5) / 3.0, 0, 1)
    total = np.full(nd, 400)
    last = (today.year, today.month - 2) if today.month > 2 else (today.year - 1, today.month + 10)
    have, (y, m) = {}, FIRST_MONTH
    while (y, m) <= last:
        season = north * (0.25 + 0.4 * np.exp(-((m - 9) ** 2) / 8)) + (1 - north) * (0.6 + 0.12 * np.sin((m - 4) / 12 * 2 * np.pi))
        ndvi = season * np.exp(rng.normal(0, 0.04) + rng.normal(0, 0.03) * (lat - 8)) * rng.uniform(0.97, 1.03, nd)
        usable = np.where((north < 0.3) & (5 <= m <= 9), rng.uniform(0.1, 0.6, nd), rng.uniform(0.7, 1.0, nd))
        n = (total * usable).astype("int32")
        for i, t in enumerate(TILES):                     # spread over the four tiles
            have[f"{y}-{m:02d}|{t}"] = ((ndvi * n / 4).astype("float32"), (n // 4).astype("int32"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return have, total, "DEMO (made-up numbers)"


def monthly(have, total):
    """Months with all four tiles -> (months, ndvi[time, district], usable share[time, district])."""
    months, mean, share = [], [], []
    for ym in sorted({k.split("|")[0] for k in have}):
        keys = [f"{ym}|{t}" for t in TILES]
        if not all(k in have for k in keys):
            continue
        s = sum(have[k][0].astype("float64") for k in keys)
        n = sum(have[k][1].astype("float64") for k in keys)
        frac = n / np.maximum(total, 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where((n > 0) & (frac >= MIN_USABLE), s / n, np.nan)
        months.append((int(ym[:4]), int(ym[5:7])))
        mean.append(v)
        share.append(frac)
    return months, np.array(mean), np.array(share)


def assess(months, x, t):
    """Compare month t with the same calendar month in all earlier years, district by district."""
    y, m = months[t]
    ref_i = [i for i, (yy, mm) in enumerate(months) if mm == m and yy < y]
    cur = x[t]
    nd = x.shape[1]
    normal, pct, pctile, nref = (np.full(nd, np.nan) for _ in range(4))
    if not ref_i:
        return cur, normal, pct, pctile, nref
    ref = x[ref_i]
    valid = ~np.isnan(ref)
    cnt = valid.sum(axis=0)
    ok = (cnt >= MIN_REF_YEARS) & ~np.isnan(cur)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.nansum(ref, axis=0) / np.maximum(cnt, 1)
        less = (np.where(valid, ref, np.inf) < cur).sum(axis=0) + 0.5 * (np.where(valid, ref, np.inf) == cur).sum(axis=0)
        normal[ok] = mean[ok]
        pct[ok] = cur[ok] / mean[ok] * 100
        pctile[ok] = less[ok] / cnt[ok] * 100
    nref[ok] = cnt[ok]
    return cur, normal, pct, pctile, nref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use made-up data (site preview only)")
    args = ap.parse_args()
    today = dt.date.today()
    gdf = load_districts()
    have, total, source = (load_demo if args.demo else load_real)(gdf, today)
    months, ndvi, share = monthly(have, total)
    if not months:
        sys.exit("No complete month of vegetation data yet.")
    T = len(months) - 1
    cur, normal, pct, pctile, nref = assess(months, ndvi, T)
    steps = list(range(max(0, T - HISTORY_MONTHS + 1), T + 1))
    hist = [assess(months, ndvi, t) for t in steps]
    y, m = months[T]
    label = f"{y}-{m:02d}"
    print(f"{len(months)} complete months, latest = {label}, rated districts = {int((~np.isnan(pctile)).sum())} of {len(gdf)}")

    labels = ["Much less green", "Less green", "Near normal", "Greener", "Much greener"]
    notes = ["lowest 10% of years", "lowest 30% of years", "middle 40% of years", "highest 30% of years", "highest 10% of years"]
    cats = [dict(c, label=lab, note=t) for c, lab, t in zip(WETNESS, labels, notes)]
    cats.append({"key": "cloud", "label": "Too cloudy", "note": "not rated", "color": "#bdbdbd"})
    names = {c["key"]: c["label"] for c in cats}

    districts = {}
    for i, row in gdf.iterrows():
        rated = not np.isnan(pctile[i])
        cat = wetness_category(pctile[i]) if rated else "cloud"
        rows = [["Usable pixels this month", f"{share[T][i] * 100:.0f}%"]]
        if rated:
            rows = [["Greenness (NDVI)", f"{cur[i]:.2f}"], [f"Normal for {MON[m - 1]}", f"{normal[i]:.2f}"],
                    ["Earlier years that were less green", f"{round(pctile[i] / 100 * nref[i])} of {int(nref[i])}"]] + rows
        districts[row.shapeID] = {
            "name": row.shapeName, "cat": cat,
            "big": f"{pct[i]:.0f}%" if rated else "–",
            "big_note": (f"of normal greenness, {ym_text(label)}" if rated
                         else "Too few cloud-free pixels this month to rate this district."),
            "tip": f"{names[cat]} · {pct[i]:.0f}% of normal" if rated else "Too cloudy to rate",
            "rows": rows,
            "v": [None if np.isnan(h[2][i]) else round(float(h[2][i] - 100), 1) for h in hist],
            "c": ["cloud" if np.isnan(h[3][i]) else wetness_category(h[3][i]) for h in hist],
        }

    (DATA / "vegetation_history.json").write_text(json.dumps({
        "kind": "anomaly", "months": [f"{yy}-{mm:02d}" for (yy, mm) in months], "min_years": MIN_REF_YEARS,
        "unrated": {"key": "cloud", "text": "Too few cloud-free pixels, or too few other years, to rate this district."},
        "words": {"less": "less green"},
        "note": "Pick any month since 2012. Grey districts were too cloudy that month.",
        "series": [{"key": "ndvi", "label": "Greenness (NDVI)", "short": "NDVI", "noun": "greenness", "unit": "", "decimals": 2}],
        "values": {"ndvi": {row.shapeID: [None if np.isnan(v) else round(float(v), 4) for v in ndvi[:, i]]
                            for i, row in gdf.iterrows()}},
    }, separators=(",", ":")))
    print(f"Wrote data/vegetation_history.json: {len(months)} months")

    write_layer("vegetation", {
        "history": "data/vegetation_history.json",
        "label": "Vegetation", "title": "Vegetation greenness compared with normal",
        "subtitle": f"{ym_text(label)}, against {MON[m - 1]} in earlier years since 2012",
        "source": source, "demo": bool(args.demo), "categories": cats,
        "how": (f"Each district shows how green its vegetation was in {ym_text(label)}, compared with {MON[m - 1]} in each "
                "earlier year since 2012. Greenness is measured by NDVI, a satellite index that rises with the amount of "
                "healthy green leaves. \"Much less green\" means this year ranks in the lowest 10% of those years."),
        "limits": [
            "Greenness covers all vegetation: crops, grass, bush and forest. A low value can come from poor rains, late planting, fire, clearing or harvest.",
            f"Clouds hide the ground. A district is not rated when under {MIN_USABLE * 100:.0f}% of its pixels were usable that month, which is common in the south during the rains.",
            "The grid is about 1 km, so it suits district averages, not individual farms.",
            "The record starts in 2012, so \"normal\" rests on about a dozen years.",
            "The monthly file is published about six weeks after the month ends.",
        ],
        "credits": [{"text": "Vegetation: NASA VIIRS VNP13A3, LP DAAC", "url": "https://lpdaac.usgs.gov/products/vnp13a3v002/"}],
        "chart": {"kind": "diverging", "cap": 30, "unit": "% vs normal",
                  "x": [MON[months[t][1] - 1] for t in steps],
                  "caption": "Past 12 months", "top": "greener than normal", "bottom": "less green"},
        "districts": districts,
    })


if __name__ == "__main__":
    main()
