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
  flood      : only when it has never been built (or FLOOD=true); it maps a past event
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

if os.environ.get("FLOOD", "").lower() == "true" or not (DATA / "flood.json").exists():
    jobs.append(("observed flooding", "flood.py"))  # one-off: a past flood event

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

if os.environ.get("PRESSURE", "").lower() == "true" or not (DATA / "pressure.json").exists():
    jobs.append(("human pressure", "pressure.py"))  # one-off: a fixed published dataset

failed = []
for name, script in jobs:
    print(f"\n===== {name} =====", flush=True)
    if subprocess.run([sys.executable, str(HERE / script)]).returncode != 0:
        failed.append(name)

if failed:
    sys.exit(f"\nThese layers failed: {', '.join(failed)}. The others were updated.")
print("\nAll layers updated.")
