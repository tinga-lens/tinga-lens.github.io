#!/usr/bin/env python3
"""
TingaLens - minerals and energy layer.

Source: U.S. Geological Survey (National Minerals Information Center), "Compilation of Geospatial Data (GIS)
for the Mineral Industries and Related Infrastructure of Africa", data release, https://doi.org/10.5066/P97EQWXP
(public domain). The geodatabase is a static compilation, so this script is run by hand when USGS publishes a new
version. It is NOT part of the daily update.

It reads three point layers (facilities, deposits, exploration sites), keeps the records for Ghana, gives each one a
resource group, a record type and a status, places it in a district, and writes:
  data/minerals.json   every record with coordinates, plus counts for each district

Run:
  python scripts/process_minerals.py /path/to/Africa_GIS.gdb
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import write_layer   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GDB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Africa_GIS.gdb")

DOI = "https://doi.org/10.5066/P97EQWXP"
RELEASE = "2024-07-03"      # date of the USGS metadata for this release

# resource groups shown on the site
RESOURCES = [
    ("gold", "Gold"), ("oil_gas", "Oil and gas"), ("bauxite", "Bauxite and aluminium"), ("manganese", "Manganese"),
    ("diamond", "Diamond"), ("iron", "Iron"), ("lithium", "Lithium"), ("limestone", "Limestone and cement"),
    ("salt", "Salt"), ("other", "Other"),
]
KEY = {  # USGS commodity name -> group
    "gold": "gold", "silver": "gold", "petroleum": "oil_gas", "natural gas": "oil_gas", "crude petroleum": "oil_gas",
    "bauxite": "bauxite", "aluminum": "bauxite", "aluminium": "bauxite", "gallium": "bauxite", "alumina": "bauxite",
    "manganese": "manganese", "diamond": "diamond", "iron": "iron", "iron ore": "iron", "lithium": "lithium",
    "limestone": "limestone", "cement": "limestone", "salt": "salt",
}
FACILITY_TYPE = {
    "Mines and Quarries": "Mine or quarry", "Mineral Processing Plants": "Processing plant", "Oil and Gas Fields": "Oil or gas field",
    "Oil and Gas Refineries and (or) Petrochemical Complexes": "Refinery", "Brine": "Brine (salt) site",
}
STATUS = {"Assumed Active": "Assumed active", "C&M": "Closed or on care and maintenance", "Development": "In development"}


def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "<na>", "null") else s


def group(names, deposit_type=""):
    tags = []
    for n in names:
        k = KEY.get(n.lower())
        if k is None and n:
            k = "other"
        if "bauxite" in deposit_type.lower() and n.lower() == "gallium":
            k = "bauxite"
        if k and k not in tags:
            tags.append(k)
    return tags or ["other"]


def read(layer):
    g = gpd.read_file(GDB, layer=layer)
    g = g[g["Country"] == "Ghana"].copy()
    return g.to_crs(4326)


def main():
    recs = []
    # ---- facilities: mines, plants, oil and gas fields (USGS Minerals Yearbook, Volume III)
    for _, r in read("AFR_Mineral_Facilities").iterrows():
        names = [clean(r.get("DsgAttr02"))]
        commodity = ", ".join(n for n in names if n)
        tags = group(names)
        recs.append({
            "id": clean(r["FeatureUID"]), "name": clean(r["FeatureNam"]), "kind": "facility",
            "type": FACILITY_TYPE.get(clean(r["FeatureTyp"]), clean(r["FeatureTyp"])),
            "res": tags[0], "tags": tags, "commodity": commodity,
            "status": STATUS.get(clean(r["LocOpStat"]), clean(r["LocOpStat"])),
            "who": clean(r.get("OperateNam")) or clean(r.get("OwnerName1")),
            "detail": "; ".join(x for x in [clean(r.get("DsgAttr03")), (f"Capacity {clean(r.get('DsgAttr07'))} {clean(r.get('DsgAttr08'))}" if clean(r.get("DsgAttr07")) else ""),
                                            (f"Reference year {clean(r.get('DsgAttr06'))}" if clean(r.get("DsgAttr06")) else "")] if x),
            "src": clean(r.get("InfSource1")), "g": r.geometry,
        })
    # ---- deposits: documented mineral deposits (USGS Professional Paper 1802 and related releases)
    for _, r in read("AFR_Mineral_Deposits").iterrows():
        names = [clean(r.get(f"DsgAttr0{i}")) for i in range(1, 9)]
        names = [n for n in names if n]
        dt = clean(r.get("DsgAttr09"))
        tags = group(names, dt)
        recs.append({
            "id": clean(r["FeatureUID"]), "name": clean(r["FeatureNam"]), "kind": "deposit", "type": "Documented deposit",
            "res": tags[0], "tags": tags, "commodity": ", ".join(names), "status": "Documented deposit",
            "who": "", "detail": dt, "src": clean(r.get("InfSource1")), "g": r.geometry,
        })
    # ---- exploration and development projects (USGS World Minerals Exploration Database)
    for _, r in read("AFR_Mineral_Exploration").iterrows():
        names = [clean(r.get(f"DsgAttr0{i}")) for i in range(1, 9)]
        names = [n for n in names if n]
        tags = group(names)
        act = clean(r.get("DsgAttr11"))
        recs.append({
            "id": clean(r["FeatureUID"]), "name": clean(r["FeatureNam"]), "kind": "exploration", "type": "Exploration or development project",
            "res": tags[0], "tags": tags, "commodity": ", ".join(names), "status": clean(r["LocOpStat"]) or "Exploration",
            "who": clean(r.get("OwnerName")), "detail": (f"Last verified active: {act}" if act else ""),
            "src": clean(r.get("InfSource1")), "g": r.geometry,
        })

    # ---- place every record in a district; a record outside every district is offshore or unplaced
    geo = json.load(open(DATA / "districts.geojson", encoding="utf8"))
    regions = json.load(open(DATA / "regions.json", encoding="utf8"))
    polys = [(f["properties"]["shapeID"], f["properties"]["shapeName"], shape(f["geometry"])) for f in geo["features"]]
    out, outside = [], []
    for r in recs:
        p = r.pop("g")
        lon, lat = float(p.x), float(p.y)
        hit = next(((i, n) for i, n, poly in polys if poly.contains(p)), None)
        if hit is None:     # a point on a boundary or just off the coast: use the nearest district if it is within 2 km
            d, i, n = min(((poly.distance(p), i, n) for i, n, poly in polys), key=lambda x: x[0])
            hit = (i, n) if d < 0.02 else None
        r.update({"lat": round(lat, 5), "lon": round(lon, 5), "d": hit[0] if hit else None, "dn": hit[1] if hit else None,
                  "region": regions.get(hit[0], "") if hit else ""})
        if not hit:
            outside.append(r["name"])
        out.append(r)

    # ---- counts for each district: record type x resource group
    by = defaultdict(lambda: defaultdict(int))
    for r in out:
        if r["d"]:
            by[r["d"]][f'{r["kind"]}:{r["res"]}'] += 1
    totals = defaultdict(int)
    for r in out:
        totals[f'{r["kind"]}'] += 1
    # a mine that is also listed as a deposit or project is counted once in each list, never added across lists
    doc = {
        "source": "U.S. Geological Survey, National Minerals Information Center. Compilation of Geospatial Data (GIS) for the Mineral Industries and Related Infrastructure of Africa. USGS data release.",
        "doi": DOI, "release": RELEASE, "licence": "Public domain (USGS)",
        "resources": [{"key": k, "label": l} for k, l in RESOURCES],
        "kinds": {"facility": "Mines, plants and oil and gas facilities", "deposit": "Documented deposits", "exploration": "Exploration and development projects"},
        "counts": dict(totals), "records": len(out), "outside_districts": outside,
        "districts": {i: dict(v) for i, v in by.items()},
        "points": out,
    }
    (DATA / "minerals.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    # ---- the district layer shown on the home map: what kind of record the district has, never a total
    cats = [("none", "No record", "not a sign of no minerals", "#e6e6e1"),
            ("x", "Exploration project only", "", "#f3dfa8"), ("d", "Documented deposit", "with or without exploration projects", "#dba75b"),
            ("f", "Mine, plant or oil and gas field", "with or without deposits and projects", "#8f4f1a")]
    label = dict(RESOURCES)
    districts = {}
    for i, name, _poly in polys:
        here = [r for r in out if r["d"] == i]
        n = {k: sum(1 for r in here if r["kind"] == k) for k in ("facility", "deposit", "exploration")}
        cat = "f" if n["facility"] else "d" if n["deposit"] else "x" if n["exploration"] else "none"
        res = [label[k] for k, _ in RESOURCES if any(k in r["tags"] for r in here)]
        biggest = {"f": "Mine, plant or field", "d": "Documented deposit", "x": "Exploration project", "none": "No record"}[cat]
        districts[i] = {
            "name": name, "cat": cat, "big": biggest if here else "None",
            "big_note": "is the highest kind of record in this district. The three kinds are not added together, and one site can appear in more than one." if here else "recorded in the USGS compilation. This does not mean the district has no minerals.",
            "tip": biggest if here else "No record",
            "rows": [["Mines, plants and fields", str(n["facility"])], ["Documented deposits", str(n["deposit"])], ["Exploration projects", str(n["exploration"])],
                     ["Resources recorded", ", ".join(res) if res else "None"]],
            "v": [n["facility"], n["deposit"], n["exploration"]], "c": ["f", "d", "x"], "records": len(here),
        }
    write_layer("minerals_map", {
        "label": "Minerals & energy", "title": "Documented mineral and energy sites", "subtitle": f"Records in the USGS compilation, {RELEASE[:4]} release",
        "source": f"{doc['source']} {DOI}", "demo": False,
        "categories": [{"key": k, "label": l, "note": n, "color": c} for k, l, n, c in cats],
        "how": "Each district is coloured by the highest kind of record the U.S. Geological Survey has for it: a mine, plant or oil and gas field; a documented mineral deposit; or an exploration project. Click a district to see how many of each kind are recorded and which resources. The full map of points, with filters, is on the Minerals & Energy page.",
        "limits": ["This is a record of documented sites, not a complete inventory. Many Ghanaian mines and deposits are not in it, and a district with no record may still have minerals.",
                   "The three kinds of record overlap: a mine can also be listed as a deposit or a project. They are shown separately and never added into a total.",
                   "Facility status reflects the USGS source year, not today. Locations are those USGS published. They are not a licence, boundary or survey.",
                   "Offshore oil and gas fields (Jubilee, TEN, Sankofa) lie outside every district and are not counted here. They are on the Minerals & Energy page."],
        "credits": [{"text": "U.S. Geological Survey, Compilation of Geospatial Data (GIS) for the Mineral Industries and Related Infrastructure of Africa", "url": DOI}],
        "chart": {"kind": "bars", "unit": "", "x": ["Mines, plants, fields", "Deposits", "Exploration"], "caption": "Records of each kind in the district", "top": "", "bottom": ""},
        "districts": districts,
    })
    print(f"Wrote data/minerals.json: {len(out)} records ({dict(totals)}), {len(by)} districts with records, {len(outside)} outside every district: {outside}")


if __name__ == "__main__":
    main()
