#!/usr/bin/env python3
"""
Tinga Lens - which crops are grown where (model estimate), by district.

Source: SPAM 2020, the Spatial Production Allocation Model of the International Food Policy Research
Institute (IFPRI) and partners. SPAM shares national and regional crop statistics out over a 10 km grid,
using satellite maps of cropland and how suitable the land is for each crop. It estimates harvested area
for 46 crops and crop groups. It is a model, not an observation of fields.

This script adds that grid up by district. Each grid cell is shared between the districts it overlaps in
proportion to the overlapping area. It publishes:
  * "crops": the crop with the largest harvested area in each district, and the top five crops;
  * one layer for each of the main crops: harvested area in each district.

No Earth Engine is used. The data are free downloads from Harvard Dataverse.

Run (a trial that lists the files, prints Ghana's totals and publishes nothing, then the full run):
  CROPS=trial python scripts/crops.py
  python scripts/crops.py
"""
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BBOX, CACHE, load_districts, prefer_ipv4, write_layer  # noqa: E402

# ---- settings you may want to change -------------------------------------
BUILD = 1                              # raise this to make the weekly update rebuild the layers
DOI = "doi:10.7910/DVN/SWPENT"         # SPAM 2020 on Harvard Dataverse
DATAVERSE = "https://dataverse.harvard.edu"
TECH = "A"                             # all production systems together (rainfed and irrigated)
MAIN = ["MAIZ", "CASS", "YAMS", "RICE", "PLNT", "COCO", "SORG", "PMIL", "GROU"]   # crops that get their own tab
NAMES = {
    "WHEA": "Wheat", "RICE": "Rice", "MAIZ": "Maize", "BARL": "Barley", "PMIL": "Pearl millet", "SMIL": "Small millet",
    "SORG": "Sorghum", "OCER": "Other cereals", "POTA": "Potato", "SWPO": "Sweet potato", "YAMS": "Yam", "CASS": "Cassava",
    "ORTS": "Other roots and tubers", "BEAN": "Bean", "CHIC": "Chickpea", "COWP": "Cowpea", "PIGE": "Pigeon pea",
    "LENT": "Lentil", "OPUL": "Other pulses", "SOYB": "Soybean", "GROU": "Groundnut", "CNUT": "Coconut", "OILP": "Oil palm",
    "SUNF": "Sunflower", "RAPE": "Rapeseed", "SESA": "Sesame", "SUGC": "Sugar cane", "SUGB": "Sugar beet", "COTT": "Cotton",
    "OFIB": "Other fibre crops", "ACOF": "Arabica coffee", "RCOF": "Robusta coffee", "COCO": "Cocoa", "TEAS": "Tea",
    "TOBA": "Tobacco", "BANA": "Banana", "PLNT": "Plantain", "TROF": "Tropical fruit", "TEMF": "Temperate fruit",
    "VEGE": "Vegetables", "REST": "Rest of crops",
}
SKIP = {"REST"}                        # left out of the rankings: it is a catch-all, not a crop
TRIAL_ROWS = 12
# --------------------------------------------------------------------------

STORE = CACHE / "crops"
PALETTE = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#1f78b4", "#b2182b", "#666666"]
GREENS = ["#eef4e6", "#cfe3bd", "#9ccb88", "#56a05f", "#1f6b43"]
FIFTHS = ["Lowest fifth", "Lower fifth", "Middle fifth", "Higher fifth", "Highest fifth"]


def name_of(code):
    return NAMES.get(code, code.title())


def get(url, **kw):
    for attempt in range(1, 5):
        try:
            r = requests.get(url, timeout=120, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  request failed ({type(e).__name__}), attempt {attempt}", flush=True)
            if attempt == 4:
                raise
            time.sleep(15 * attempt)


def find_files():
    """List the files of the SPAM 2020 dataset on Dataverse; returns (list of (name, id, size), licence)."""
    r = get(f"{DATAVERSE}/api/datasets/:persistentId/", params={"persistentId": DOI}).json()
    ver = r["data"]["latestVersion"]
    files = [(f["dataFile"]["filename"], f["dataFile"]["id"], f["dataFile"].get("filesize", 0)) for f in ver["files"]]
    lic = ver.get("license")
    lic = lic.get("name") if isinstance(lic, dict) else lic
    return files, lic or ver.get("termsOfUse", "not stated")


def pick_harvested_tif(files):
    cands = [f for f in files if "harvest" in f[0].lower() and f[0].lower().endswith(".zip") and re.search(r"tif", f[0], re.I)]
    if not cands:
        cands = [f for f in files if "harvest" in f[0].lower() and re.search(r"tif", f[0], re.I)]
    return sorted(cands)[-1] if cands else None


def download(fid, dest):
    with get(f"{DATAVERSE}/api/access/datafile/{fid}", params={"format": "original"}, stream=True) as r:
        with open(dest, "wb") as out:
            for chunk in r.iter_content(1 << 22):
                out.write(chunk)


def read_ghana(zpath):
    """-> (affine transform, {crop code: 2-D array of harvested hectares}) for the window around Ghana."""
    import rasterio
    from rasterio.windows import Window, from_bounds
    from rasterio.io import MemoryFile
    out, tf = {}, None
    with zipfile.ZipFile(zpath) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".tif")]
        print(f"  {len(members)} map files in the download; first few: {members[:4]}", flush=True)
        for n in members:
            m = re.search(r"_([A-Za-z0-9]{3,5})_([A-Za-z])\.tif$", n)
            if not m or m.group(2).upper() != TECH:
                continue
            kind = re.search(r"_([HAYPhayp])_[A-Za-z0-9]{3,5}_[A-Za-z]\.tif$", n)
            if kind and kind.group(1).upper() != "H":      # harvested area only, not physical area, yield or production
                continue
            code = m.group(1).upper()
            with MemoryFile(z.read(n)) as mf, mf.open() as src:
                w0 = from_bounds(*BBOX, transform=src.transform)
                w = Window(int(round(w0.col_off)), int(round(w0.row_off)), int(round(w0.width)), int(round(w0.height)))
                a = src.read(1, window=w, masked=True).astype("float64").filled(0)
                a[~np.isfinite(a)] = 0
                a[a < 0] = 0
                if tf is None:
                    tf = src.window_transform(w)
                    print(f"  grid: {a.shape[1]} x {a.shape[0]} cells, cell size {abs(src.transform.a):.4f} degrees", flush=True)
                out[code] = a
    return tf, out


def weights(tf, shape, gdf):
    """Share of each grid cell that lies in each district (sparse matrix: districts x cells)."""
    import geopandas as gpd
    from scipy import sparse
    from shapely.geometry import box
    rows, cols = shape
    cells = []
    for r in range(rows):
        for c in range(cols):
            x0, y0 = tf * (c, r)
            x1, y1 = tf * (c + 1, r + 1)
            cells.append(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    cg = gpd.GeoDataFrame({"cell": range(len(cells))}, geometry=cells, crs=4326).to_crs(6933)
    cg["cell_area"] = cg.geometry.area
    dg = gdf[["shapeID", "geometry"]].reset_index(drop=True).to_crs(6933)
    dg["di"] = range(len(dg))
    inter = gpd.overlay(cg, dg, how="intersection", keep_geom_type=True)
    inter["frac"] = inter.geometry.area / inter["cell_area"]
    W = sparse.csr_matrix((inter["frac"].clip(0, 1), (inter["di"], inter["cell"])), shape=(len(dg), len(cells)))
    return W


def main():
    trial = os.environ.get("CROPS", "").lower() == "trial"
    prefer_ipv4()
    STORE.mkdir(parents=True, exist_ok=True)
    files, lic = find_files()
    print(f"SPAM 2020 dataset on Dataverse: {len(files)} files. Licence: {lic}")
    for n, i, s in sorted(files)[:TRIAL_ROWS if trial else 0]:
        print(f"   {n}  ({s / 1e6:,.0f} MB)")
    pick = pick_harvested_tif(files)
    if not pick:
        for n, i, sz in sorted(files)[:40]:
            print(f"   {n}  ({sz / 1e6:,.0f} MB)")
        sys.exit("Could not find the harvested-area map files in the dataset. The file list is printed above; send it to the developer. Nothing was published.")
    name, fid, size = pick
    print(f"Using {name} ({size / 1e6:,.0f} MB)", flush=True)
    version = (re.search(r"(spam\d{4}[A-Za-z0-9.]*)", name, re.I) or re.search(r"(v\d[\w.]*)", name) or [None, "SPAM 2020"])[1]

    cache = STORE / f"ghana_{TECH}_b{BUILD}.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        tf = __import__("affine").Affine(*z["tf"])
        grids = {k[2:]: z[k] for k in z.files if k.startswith("g_")}
    else:
        zpath = STORE / "harvested.zip"
        t0 = time.time()
        download(fid, zpath)
        print(f"  downloaded in {(time.time() - t0) / 60:.1f} min", flush=True)
        tf, grids = read_ghana(zpath)
        zpath.unlink(missing_ok=True)
        if not grids:
            sys.exit("No crop maps for all production systems were found inside the download. Nothing was published.")
        np.savez_compressed(cache, tf=np.array(tf)[:6], **{f"g_{k}": v for k, v in grids.items()})
    codes = sorted(grids)
    shape = next(iter(grids.values())).shape
    print(f"{len(codes)} crops read: {', '.join(codes)}")
    print("Harvested area inside the window (all of it, not only Ghana), hectares, largest first:")
    for c in sorted(codes, key=lambda c: -grids[c].sum())[:14]:
        print(f"   {c:5s} {name_of(c):24s} {grids[c].sum():>14,.0f}")

    gdf = load_districts()
    W = weights(tf, shape, gdf)
    flat = {c: grids[c].ravel() for c in codes}
    ha = {c: W @ flat[c] for c in codes}                                      # hectares in each district
    land_km2 = (gdf.to_crs(6933).geometry.area / 1e6).to_numpy()
    nat = {c: float(ha[c].sum()) for c in codes}
    print("Ghana totals after sharing the grid out among districts (hectares):")
    for c in sorted(codes, key=lambda c: -nat[c])[:14]:
        print(f"   {c:5s} {name_of(c):24s} {nat[c]:>12,.0f}")
    if trial:
        print("Trial finished. Nothing was published. Check that the totals look sensible for Ghana, then run it again without the trial setting.")
        return

    ids = list(gdf["shapeID"])
    ranked = [c for c in codes if c not in SKIP]
    total = {i: sum(ha[c][i] for c in ranked) for i in range(len(ids))}
    top = {i: sorted(ranked, key=lambda c: -ha[c][i])[:5] for i in range(len(ids))}
    lead = {i: (top[i][0] if total[i] > 1 else None) for i in range(len(ids))}
    counts = {}
    for v in lead.values():
        if v:
            counts[v] = counts.get(v, 0) + 1
    order = sorted(counts, key=lambda c: -counts[c])
    shown = order[:len(PALETTE) - 1]
    color = {c: PALETTE[i] for i, c in enumerate(shown)}
    color["_other"] = PALETTE[-1]
    keyof = lambda c: f"k_{c}" if c in shown else "k_other"
    mains = [c for c in MAIN if c in codes]
    chart_x = [name_of(c) for c in mains]

    def chart_for(i, highlight=None):
        return {"v": [round(float(ha[c][i]), 1) for c in mains],
                "bc": [("#2D6A4F" if (highlight is None or c == highlight) else "#b8c4bd") for c in mains]}

    credits = [{"text": f"Crop areas: SPAM 2020 ({version}), International Food Policy Research Institute and partners, open data (see the licence on the dataset page)",
                "url": "https://www.mapspam.info/"},
               {"text": "Boundaries are 2019 districts; each 10 km grid cell is shared between districts by overlapping area", "url": "https://www.geoboundaries.org"}]
    limits = [
        "This is a model estimate, not a record of what each farmer planted. SPAM shares national and regional crop statistics out over a 10 km grid, using satellite cropland maps and the suitability of the land for each crop.",
        "The grid cells are about 85 km², similar in size to many districts. Each cell is shared between the districts it overlaps by area, so figures for small districts mostly reflect the surrounding cells. Differences between neighbouring districts can be an artefact of the grid.",
        "The estimates are built mainly on statistics for 2019 to 2021 and show one typical year, not this season or a trend.",
        "Ghana's district crop statistics were not available to the model at district level, so the district pattern comes from the model, not from district records.",
        "Harvested area counts each harvest, so land harvested twice in a year is counted twice and the total can exceed the cropland area. Rainfed and irrigated land are added together.",
        "Crop groups such as 'other roots and tubers' hide individual crops. In SPAM, cocoyam is not a crop of its own.",
    ]

    # ---- main crop layer ----
    districts = {}
    for i, sid in enumerate(ids):
        nm = gdf.loc[i, "shapeName"]
        if not lead[i]:
            districts[sid] = {"name": nm, "cat": "none", "big": "–", "big_note": "No crop area estimated for this district.", "tip": "No crop area estimated",
                              "rows": [], "v": chart_for(i)["v"], "bc": chart_for(i)["bc"], "c": ["none"] * len(mains)}
            continue
        rows = [[f"{n + 1}. {name_of(c)}", f"{ha[c][i]:,.0f} ha ({ha[c][i] / total[i] * 100:.0f}% of harvested area)"] for n, c in enumerate(top[i])]
        rows.append(["All crops, harvested area", f"{total[i]:,.0f} ha"])
        cat = keyof(lead[i])
        districts[sid] = {"name": nm, "cat": cat, "big": name_of(lead[i]),
                          "big_note": f"has the largest harvested area of any crop in the district, {ha[lead[i]][i] / total[i] * 100:.0f}% of the total (model estimate)",
                          "tip": f"{name_of(lead[i])}, {ha[lead[i]][i] / total[i] * 100:.0f}% of harvested area",
                          "rows": rows, **{k: v for k, v in chart_for(i).items()}, "c": [cat] * len(mains)}
    cats = [{"key": keyof(c), "label": name_of(c), "note": "", "color": color[c]} for c in shown]
    if len(order) > len(shown):
        cats.append({"key": "k_other", "label": "Other crops", "note": "", "color": color["_other"]})
    cats.append({"key": "none", "label": "No estimate", "note": "", "color": "#bdbdbd"})
    print("Leading crop by number of districts: " + ", ".join(f"{name_of(c)} {counts[c]}" for c in order))
    write_layer("crops", {
        "label": "Main crops", "title": "Main crop in each district (model estimate)", "source": f"SPAM 2020 ({version})", "demo": False,
        "subtitle": "The crop with the largest harvested area, from a published model of crop areas",
        "build": BUILD, "categories": cats,
        "how": ("Each district is coloured by the crop with the largest estimated harvested area. The estimates come from SPAM 2020, a model that shares national and regional "
                "crop statistics out over a 10 km grid. Click a district for its five largest crops. This is an estimate of the usual crop pattern, not a survey of what is planted this season."),
        "limits": limits, "credits": credits,
        "chart": {"kind": "bars", "unit": "ha", "x": chart_x, "caption": "Estimated harvested area of the main crops in the district (hectares)", "top": "", "bottom": ""},
        "districts": districts,
    })

    # ---- one layer for each main crop ----
    for c in mains:
        v = ha[c]
        share = np.where(land_km2 > 0, v / (land_km2 * 100) * 100, 0)           # percent of the district's land
        pos = share[v >= 1]
        cuts = np.percentile(pos, [20, 40, 60, 80]) if len(pos) else []
        n_pos = int((v >= 1).sum())
        rank = {i: r + 1 for r, i in enumerate(sorted(range(len(ids)), key=lambda i: -v[i]))}
        districts = {}
        for i, sid in enumerate(ids):
            nm = gdf.loc[i, "shapeName"]
            if v[i] < 1:
                cat = "none"
                big, note, tip = "None", f"No {name_of(c).lower()} estimated in this district", "None estimated"
            else:
                k = int(np.searchsorted(cuts, share[i], side="right"))
                cat = f"n{k}"
                big, note, tip = f"{v[i]:,.0f} ha", f"estimated harvested area of {name_of(c).lower()}, {FIFTHS[k].lower()} of districts by share of land", f"{v[i]:,.0f} ha, {share[i]:.1f}% of the land"
            rows = [["Harvested area (model estimate)", f"{v[i]:,.0f} ha"], ["Share of the district's land", f"{share[i]:.1f}%"],
                    ["Share of Ghana's estimated area", f"{v[i] / nat[c] * 100:.2f}%" if nat[c] else "–"],
                    ["Rank by area", f"{rank[i]} of {len(ids)}"]] if v[i] >= 1 else []
            districts[sid] = {"name": nm, "cat": cat, "big": big, "big_note": note, "tip": tip, "rows": rows, **chart_for(i, c), "c": [cat] * len(mains)}
        write_layer(f"crop_{c.lower()}", {
            "label": name_of(c), "title": f"{name_of(c)}: estimated harvested area", "source": f"SPAM 2020 ({version})", "demo": False,
            "subtitle": f"Estimated harvested area of {name_of(c).lower()} in each district (model estimate)",
            "build": BUILD,
            "categories": [{"key": f"n{k}", "label": FIFTHS[k], "note": "share of land", "color": GREENS[k]} for k in range(5)] + [{"key": "none", "label": "None estimated", "note": "", "color": "#bdbdbd"}],
            "how": (f"Each district shows the estimated harvested area of {name_of(c).lower()} from SPAM 2020, a model that shares national and regional crop statistics out over a 10 km grid. "
                    "Colours rank districts by the share of their land, in fifths. Click a district for the area in hectares and the district's rank."),
            "limits": limits, "credits": credits,
            "chart": {"kind": "bars", "unit": "ha", "x": chart_x, "caption": f"Estimated harvested area of the main crops in the district (hectares). Dark bar: {name_of(c).lower()}.", "top": "", "bottom": ""},
            "districts": districts,
        })
        print(f"{name_of(c)}: {n_pos} districts with an estimate, {nat[c]:,.0f} ha in Ghana")


if __name__ == "__main__":
    main()
