"""
Tinga Lens - shared helpers.

Every layer script ends by calling write_layer(key, payload). The website
(index.html) draws whatever the payload describes, so a new layer needs a new
script but no change to the website.

Payload fields the website reads:
  label, title, subtitle, updated, source, demo
  categories : [{key, label, note, color}]      legend, in order
  counts     : {category key: number of districts}
  how        : one paragraph, "how to read this map"
  limits     : [sentences]
  credits    : [{text, url}]
  chart      : {caption, top, bottom, kind: "diverging"|"bars", x: [labels]}
  districts  : {shapeID: {name, cat, big, big_note, tip, rows: [[label, value]],
                          v: [numbers or null], c: [category keys]}}
"""
import datetime as dt
import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = ROOT / "cache"
DISTRICTS = DATA / "districts.geojson"
BBOX = (-3.5, 4.5, 1.5, 11.5)        # west, south, east, north (Ghana + margin)

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# order of the tabs on the website; layers without a data file are left out
ORDER = [("drought", "Drought"), ("soil", "Soil moisture"), ("vegetation", "Vegetation"),
         ("fires", "Fires"), ("firerisk", "Fire risk"), ("forest", "Forest loss")]
PLANNED = ["Mining"]

BOUNDARY_CREDIT = {"text": "Boundaries: geoBoundaries (CC BY 4.0; source USAID Ghana HPNO and Ghana Statistical Service)",
                   "url": "https://www.geoboundaries.org"}

# dry-to-wet colours shared by the rainfall and soil moisture layers (colour-blind safe)
WETNESS = [
    {"key": "very_dry", "label": "Very dry", "color": "#8c510a"},
    {"key": "dry", "label": "Dry", "color": "#d8b365"},
    {"key": "normal", "label": "Near normal", "color": "#f3efe4"},
    {"key": "wet", "label": "Wet", "color": "#5ab4ac"},
    {"key": "very_wet", "label": "Very wet", "color": "#01665e"},
]


def load_districts():
    return gpd.read_file(DISTRICTS).reset_index(drop=True)


def ym_text(label):
    """'2026-08' -> 'Aug 2026'"""
    y, m = label.split("-")
    return f"{MON[int(m) - 1]} {y}"


def wetness_category(pctile):
    """Rank among reference years (0 = driest) -> category key."""
    if pctile <= 10:
        return "very_dry"
    if pctile <= 30:
        return "dry"
    if pctile < 70:
        return "normal"
    if pctile < 90:
        return "wet"
    return "very_wet"


def write_layer(key, payload):
    """Save data/<key>.json and refresh data/layers.json (the list of tabs)."""
    payload = {"key": key, "updated": dt.date.today().isoformat(), **payload}
    counts = {}
    for d in payload["districts"].values():
        counts[d["cat"]] = counts.get(d["cat"], 0) + 1
    payload["counts"] = counts
    DATA.mkdir(exist_ok=True)
    (DATA / f"{key}.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    write_manifest()
    print(f"Wrote data/{key}.json: {len(payload['districts'])} districts, {counts}")


def write_manifest():
    layers = [{"key": k, "label": lab, "file": f"data/{k}.json"}
              for k, lab in ORDER if (DATA / f"{k}.json").exists()]
    (DATA / "layers.json").write_text(json.dumps({"layers": layers, "planned": PLANNED}, indent=1))
