# Tinga Lens

Open, satellite-based environmental monitoring for Ghana, by district.

| Layer | Source | Updates | Script |
|---|---|---|---|
| Drought (rainfall vs normal) | CHIRPS rainfall | monthly | `scripts/drought.py` |
| Soil moisture (root zone vs normal) | NASA SMAP Level-4 | monthly | `scripts/smap.py` |
| Vegetation (greenness vs normal) | NASA VIIRS NDVI | monthly | `scripts/vegetation.py` |
| Fires (detections vs normal) | NASA FIRMS | weekly | `scripts/fires.py` |
| Fire risk (experimental chance of fire, next 5 days) | Model on SMAP, FIRMS, CHIRPS, VIIRS | weekly | `scripts/fire_risk.py` |
| Forest loss (tree cover loss rate) | Global Forest Change | yearly | `scripts/forest.py` |

## How it fits together

- `index.html` is the website. It reads `data/layers.json` to build the tabs, then draws whatever each layer file describes. Adding a layer needs a new script, not a change to the website.
- Each script writes one file in `data/` (for example `data/drought.json`) through `scripts/common.py`.
- `scripts/update.py` runs every layer that is due. `.github/workflows/update.yml` runs it every Monday and publishes any change.
- `data/districts.geojson` holds Ghana's 260 districts (2019 boundaries, simplified).
- `about.html` is the About page. `data/site.json` holds its settings: founder name, contact email, LinkedIn link and the sign-up form link. Leave a value empty to hide that part.

## Setting up the update on GitHub

1. **Settings → Pages**: deploy from the `main` branch, folder `/ (root)`.
2. **Settings → Actions → General → Workflow permissions**: "Read and write permissions".
3. **Settings → Secrets and variables → Actions → New repository secret**, three times:
   - `EARTHDATA_USERNAME` = your NASA Earthdata username
   - `EARTHDATA_PASSWORD` = your NASA Earthdata password
   - `FIRMS_MAP_KEY` = a free key from https://firms.modaps.eosdis.nasa.gov/api/map_key/
   Without the Earthdata login, soil moisture and vegetation are skipped. Without the FIRMS key, fires is skipped. The rest still runs.
4. **Actions → Update data → Run workflow**. Tick "Rebuild forest loss" once a year, after the new Global Forest Change release.

The first run of a new layer downloads its full record and can take one to three hours. Later runs take a few minutes.

## Run it on your own computer

    pip install -r requirements.txt
    python scripts/update.py           # every layer that is due
    python scripts/drought.py --demo   # made-up data, for previewing only (also smap.py, forest.py)
    python -m http.server              # then open http://localhost:8000

## Methods in brief

- **Drought:** rainfall over the latest 3 months, ranked against the same months in 1991-2020. Not rated where normal rainfall is under 30 mm.
- **Soil moisture:** average root-zone (0-100 cm) moisture for the latest complete month, ranked against the same month in every earlier year since 2015. Each month is sampled on 6 days at 10:30 UTC.
- **Vegetation:** average NDVI of good-quality 1 km pixels for the latest month, ranked against the same month in every earlier year since 2012. Not rated when under 30% of a district's pixels are usable.
- **Fires:** VIIRS fire detections over the last 30 days, compared with the average for the same dates in earlier years since 2012. Low-confidence detections are dropped.
- **Fire risk (experimental):** logistic regression for the chance of at least one fire detection in a district in the five days after each sampled day. Predictors are the district's usual fire frequency for those dates and departures from normal in surface and root-zone soil moisture, drying rate, and lagged rainfall and greenness. Every model is tested on fire years left out of training; `data/firerisk_report.json` holds the scores, coefficients and the test of whether root-zone moisture adds skill.
- **Forest loss:** average yearly tree cover loss over the last 3 years, as a percentage of tree cover in 2000 (30 m pixels with at least 30% canopy). Not rated where tree cover in 2000 was under 5% of the district.

Settings are at the top of each script.

## Data and licences

- Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara.
- Soil moisture: NASA SMAP L4 (SPL4SMGP), NSIDC DAAC.
- Vegetation: NASA VIIRS VNP13A3, LP DAAC.
- Fires: NASA FIRMS, VIIRS 375 m active fires.
- Tree cover: Hansen/UMD/Google/USGS/NASA Global Forest Change, CC BY 4.0.
- Boundaries: geoBoundaries GHA ADM2, CC BY 4.0. Source: USAID Ghana HPNO and Ghana Statistical Service.
- Basemap: © OpenStreetMap contributors. Map library: Leaflet (BSD 2-Clause).
