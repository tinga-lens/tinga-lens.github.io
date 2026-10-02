# Tinga Lens

Open, satellite-based environmental monitoring for Ghana, by district.

| Layer | Source | Updates | Script |
|---|---|---|---|
| Drought (rainfall vs normal) | CHIRPS rainfall | monthly | `scripts/drought.py` |
| Soil moisture (root zone vs normal) | NASA SMAP Level-4 | monthly | `scripts/smap.py` |
| Forest loss (tree cover loss rate) | Global Forest Change | yearly | `scripts/forest.py` |

## How it fits together

- `index.html` is the website. It reads `data/layers.json` to build the tabs, then draws whatever each layer file describes. Adding a layer needs a new script, not a change to the website.
- Each script writes one file in `data/` (for example `data/drought.json`) through `scripts/common.py`.
- `scripts/update.py` runs every layer that is due. `.github/workflows/update.yml` runs it every Monday and publishes any change.
- `data/districts.geojson` holds Ghana's 260 districts (2019 boundaries, simplified).

## Setting up the update on GitHub

1. **Settings → Pages**: deploy from the `main` branch, folder `/ (root)`.
2. **Settings → Actions → General → Workflow permissions**: "Read and write permissions".
3. **Settings → Secrets and variables → Actions → New repository secret**, twice:
   - `EARTHDATA_USERNAME` = your NASA Earthdata username
   - `EARTHDATA_PASSWORD` = your NASA Earthdata password
   Without these, the soil moisture layer is skipped and the rest still runs.
4. **Actions → Update data → Run workflow**. Tick "Rebuild forest loss" once a year, after the new Global Forest Change release.

The first run downloads the full SMAP and forest records and can take an hour or more. Later runs take a few minutes.

## Run it on your own computer

    pip install -r requirements.txt
    python scripts/update.py           # every layer that is due
    python scripts/drought.py --demo   # made-up data, for previewing only (also smap.py, forest.py)
    python -m http.server              # then open http://localhost:8000

## Methods in brief

- **Drought:** rainfall over the latest 3 months, ranked against the same months in 1991-2020. Not rated where normal rainfall is under 30 mm.
- **Soil moisture:** average root-zone (0-100 cm) moisture for the latest complete month, ranked against the same month in every earlier year since 2015. Each month is sampled on 6 days at 10:30 UTC.
- **Forest loss:** average yearly tree cover loss over the last 3 years, as a percentage of tree cover in 2000 (30 m pixels with at least 30% canopy). Not rated where tree cover in 2000 was under 5% of the district.

Settings are at the top of each script.

## Data and licences

- Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara.
- Soil moisture: NASA SMAP L4 (SPL4SMGP), NSIDC DAAC.
- Tree cover: Hansen/UMD/Google/USGS/NASA Global Forest Change, CC BY 4.0.
- Boundaries: geoBoundaries GHA ADM2, CC BY 4.0. Source: USAID Ghana HPNO and Ghana Statistical Service.
- Basemap: © OpenStreetMap contributors. Map library: Leaflet (BSD 2-Clause).
