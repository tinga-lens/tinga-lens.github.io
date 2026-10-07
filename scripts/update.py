#!/usr/bin/env python3
"""
Tinga Lens - run every layer that is due.

  drought    : every run
  soil       : every run, if a NASA Earthdata login is available
  vegetation : every run, if a NASA Earthdata login is available
  fires      : every run, if a FIRMS map key is available
  fire risk  : every run, after soil moisture and fires (it reads what they saved)
  biodiversity: once a month, if a GBIF login is available
  pressure   : only when it has never been built (or PRESSURE=true); the source is a fixed published dataset
  flood-prone: only when it has never been built, its script has a newer BUILD number, or FLOODPRONE=true;
               needs a Google Earth Engine key
  water      : only when it has never been built or its script has a newer BUILD number; needs the same key
  flood hazard: only when it has never been built or its script has a newer BUILD number; needs the same key
  flood      : only when an event has never been built, its script has a newer BUILD number, or FLOOD=true; it maps past events
  urban      : only when it has never been built (or URBAN=true); the source changes with each new release
  forest     : only when asked (FOREST=true) or when it has never been built,
               because the source changes once a year and the download is large

One layer failing does not stop the others; the run is marked failed at the end.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

if os.environ.get("EE_CHECK", "").lower() == "true":      # only test the Google Earth Engine key, then stop
    print("===== Earth Engine check =====", flush=True)
    sys.exit(subprocess.run([sys.executable, str(HERE / "ee_check.py")]).returncode)

if os.environ.get("FLOODPRONE", "").lower() == "pilot":   # only run the flood-prone trial (publishes nothing), then stop
    print("===== flood-prone land (trial) =====", flush=True)
    sys.exit(subprocess.run([sys.executable, str(HERE / "floodprone.py")]).returncode)

earthdata = bool(os.environ.get("EARTHDATA_USERNAME") or os.environ.get("EARTHDATA_TOKEN"))
jobs = [("drought", "drought.py")]
if earthdata:
    jobs += [("soil", "smap.py"), ("vegetation", "vegetation.py")]
else:
    print("Skipping soil moisture and vegetation: no EARTHDATA_USERNAME / EARTHDATA_PASSWORD set.")
if os.environ.get("FIRMS_MAP_KEY"):
    jobs.append(("fires", "fires.py"))
else:
    print("Skipping fires: no FIRMS_MAP_KEY set.")
if earthdata and os.environ.get("FIRMS_MAP_KEY"):
    jobs.append(("fire risk", "fire_risk.py"))      # needs the soil moisture and fires records; downloads nothing
if os.environ.get("FOREST", "").lower() == "true" or not (DATA / "forest.json").exists():
    jobs.append(("forest", "forest.py"))
else:
    print("Skipping forest loss: already built (tick 'forest' when running by hand to rebuild).")

if os.environ.get("URBAN", "").lower() == "true" or not (DATA / "urban.json").exists():
    jobs.append(("urban growth", "urban.py"))       # one-off: the source changes only with a new release

def is_old(key, script):
    """True when the published layer is missing or was built by an older version of its script."""
    import json, re
    f = DATA / f"{key}.json"
    if not f.exists():
        return True
    want = int(re.search(r"^BUILD = (\d+)", (HERE / script).read_text(), re.M).group(1))
    return json.loads(f.read_text()).get("build", 1) < want


if os.environ.get("EE_SERVICE_ACCOUNT_KEY"):     # the layers that use Google Earth Engine
    if os.environ.get("FLOODPRONE", "").lower() == "true" or is_old("floodprone", "floodprone.py"):
        jobs.append(("flood-prone land", "floodprone.py"))       # about once a year
    if is_old("floodhazard", "floodhazard.py"):
        jobs.append(("river flood hazard", "floodhazard.py"))    # one-off: a fixed published dataset
    # cropland and soil nutrients: only when asked for, or when a published layer was built by an older version
    if os.environ.get("AGRICULTURE", "").lower() in ("true", "full", "trial") or ((DATA / "cropland.json").exists() and is_old("cropland", "agriculture.py")):
        jobs.append(("cropland and soil nutrients", "agriculture.py"))
    if is_old("water", "water.py"):
        jobs.append(("surface water change", "water.py"))        # one-off: a fixed published dataset
else:
    print("Skipping flood-prone land, river flood hazard and surface water change: no EE_SERVICE_ACCOUNT_KEY set.")

if os.environ.get("FLOOD", "").lower() == "true" or is_old("flood", "flood.py") or is_old("flood2020", "flood.py"):
    jobs.append(("observed flooding", "flood.py"))  # one-off: past flood events

# which crops are grown where (SPAM 2020, a plain download; no Earth Engine). Only when asked for, or when a published layer is out of date.
if os.environ.get("CROPS", "").lower() in ("true", "full", "trial") or ((DATA / "crops.json").exists() and is_old("crops", "crops.py")):
    jobs.append(("crops (SPAM 2020)", "crops.py"))

if os.environ.get("GBIF_USER") and os.environ.get("GBIF_PWD"):
    import datetime, json
    f = DATA / "biodiversity.json"
    this_month = f.exists() and json.loads(f.read_text()).get("updated", "")[:7] == datetime.date.today().isoformat()[:7]
    if os.environ.get("BIODIVERSITY", "").lower() == "true" or not this_month:
        jobs.append(("biodiversity", "biodiversity.py"))    # once a month
    else:
        print("Skipping biodiversity: already built this month.")
else:
    print("Skipping biodiversity: no GBIF_USER / GBIF_PWD set.")

def pressure_is_old():
    import json, re
    want = int(re.search(r"^BUILD = (\d+)", (HERE / "pressure.py").read_text(), re.M).group(1))
    return json.loads((DATA / "pressure.json").read_text()).get("build", 1) < want


if os.environ.get("PRESSURE", "").lower() == "true" or not (DATA / "pressure.json").exists() or pressure_is_old():
    jobs.append(("human pressure", "pressure.py"))  # one-off: a fixed published dataset

failed = []
for name, script in jobs:
    print(f"\n===== {name} =====", flush=True)
    if subprocess.run([sys.executable, str(HERE / script)]).returncode != 0:
        failed.append(name)

if failed:
    sys.exit(f"\nThese layers failed: {', '.join(failed)}. The others were updated.")
print("\nAll layers updated.")
