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
         ("fires", "Fires"), ("firerisk", "Fire risk"), ("forest", "Forest loss"), ("floodprone", "Flood-prone land"), ("floodhazard", "River flood hazard"), ("water", "Surface water change"), ("flood", "Flood 2023: lower Volta"), ("flood2020", "Flood 2020: northern Ghana"), ("cropland", "Cropland"), ("soiln", "Nitrogen"), ("soilp", "Phosphorus"), ("soilk", "Potassium"), ("soilph", "Soil pH"), ("soilom", "Organic matter"), ("soilclay", "Clay"), ("soilsand", "Sand"), ("soilbd", "Bulk density"), ("crops", "Main crops"), ("crop_maiz", "Maize"), ("crop_cass", "Cassava"), ("crop_yams", "Yam"), ("crop_rice", "Rice"), ("crop_plnt", "Plantain"), ("crop_coco", "Cocoa"), ("crop_sorg", "Sorghum"), ("crop_pmil", "Pearl millet"), ("crop_grou", "Groundnut"), ("pressure", "Human pressure"), ("pressurechange", "Pressure change"), ("urban", "Urban growth"), ("biodiversity", "Recorded species")]
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


def prefer_ipv4():
    """GitHub's servers have no IPv6 route, and a host that also has an IPv6 address can fail with
    'Network is unreachable'. Ask for IPv4 addresses only."""
    import socket
    try:
        import urllib3.util.connection as c
        c.allowed_gai_family = lambda: socket.AF_INET
    except Exception:
        pass


def earthdata_login(tries=5):
    """Log in to NASA Earthdata, trying again if NASA cannot be reached. Stops quietly if it never answers."""
    import sys
    import time
    prefer_ipv4()
    import earthaccess
    for attempt in range(1, tries + 1):
        try:
            auth = earthaccess.login(strategy="environment")
            if getattr(auth, "authenticated", False):
                return auth
            sys.exit("NASA Earthdata did not accept the login. Check EARTHDATA_USERNAME and EARTHDATA_PASSWORD.")
        except SystemExit:
            raise
        except Exception as e:
            print(f"  NASA Earthdata could not be reached ({type(e).__name__}), attempt {attempt} of {tries}", flush=True)
            if attempt < tries:
                time.sleep(45 * attempt)
    sys.exit("NASA Earthdata could not be reached. The existing map is kept and this layer will be tried again on the next run.")
