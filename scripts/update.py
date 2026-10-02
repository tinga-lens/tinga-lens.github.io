#!/usr/bin/env python3
"""
Tinga Lens - run every layer that is due.

  drought : every run
  soil    : every run, if a NASA Earthdata login is available
  forest  : only when asked (FOREST=true) or when it has never been built,
            because the source changes once a year and the download is large

One layer failing does not stop the others; the run is marked failed at the end.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

jobs = [("drought", "drought.py")]
if os.environ.get("EARTHDATA_USERNAME") or os.environ.get("EARTHDATA_TOKEN"):
    jobs.append(("soil", "smap.py"))
else:
    print("Skipping soil moisture: no EARTHDATA_USERNAME / EARTHDATA_PASSWORD set.")
if os.environ.get("FOREST", "").lower() == "true" or not (DATA / "forest.json").exists():
    jobs.append(("forest", "forest.py"))
else:
    print("Skipping forest loss: already built (tick 'forest' when running by hand to rebuild).")

failed = []
for name, script in jobs:
    print(f"\n===== {name} =====", flush=True)
    if subprocess.run([sys.executable, str(HERE / script)]).returncode != 0:
        failed.append(name)

if failed:
    sys.exit(f"\nThese layers failed: {', '.join(failed)}. The others were updated.")
print("\nAll layers updated.")
