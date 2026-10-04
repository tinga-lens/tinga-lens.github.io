# Tinga Lens

**Live site: https://tingalens.org**

**See Ghana's environment changing.**

Tinga Lens is an independent environmental monitoring platform for Ghana. It uses publicly available Earth observation,
climate and geospatial datasets, and processing code written for this project, to publish information for each of Ghana's districts.

Platform: https://tingalens.org

## Modules

| Module | Products | Status |
|---|---|---|
| Drought | Rainfall anomaly (CHIRPS), soil moisture anomaly (NASA SMAP Level-4) | Published |
| Fire | Active fire detections (NASA FIRMS), fire probability (experimental model) | Published |
| Vegetation & Forest | Vegetation greenness anomaly (NASA VIIRS), tree cover loss (Global Forest Change) | Published |
| Flood | Observed flooding, flood susceptibility | In development, no data |
| Urban Exposure | Urban growth, exposure to flood-prone land | In development, no data |

## Data philosophy

Tinga Lens distinguishes between:

1. **Observed**: what a satellite recorded
2. **Environmental condition**: an observation compared with what is normal for the place and season
3. **Modeled risk**: a statistical estimate made by Tinga Lens

Each product documents its source, method, resolution, validation, limitations and version. The site shows no placeholder numbers.

## Project structure

- `index.html`, `pages/`: the website pages
- `css/`, `js/`: styles and the web application (`js/app.js` is the map, `js/config.js` the product register)
- `data/`: processed results the pages read (see `docs/data_dictionary.md`)
- `scripts/`: the processing code, in Python; one script per product, run by `scripts/update.py`
- `docs/`: changelog, validation, limitations, data dictionary
- `.github/workflows/update.yml`: runs the processing every Monday and publishes any change

Processing runs in GitHub Actions with Python. Google Earth Engine is not used.

## Running the update

Repository secrets needed (Settings → Secrets and variables → Actions):

- `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`: a free NASA Earthdata login (soil moisture, vegetation)
- `FIRMS_MAP_KEY`: a free NASA FIRMS key (fires)

Then: Actions → Update data → Run workflow. Tick "Rebuild forest loss" once a year.

On your own computer:

    pip install -r requirements.txt
    python scripts/update.py
    python -m http.server        # then open http://localhost:8000

## Independence

Tinga Lens uses only publicly available datasets and independently developed processing code.
This repository contains no university research code, unpublished models, restricted or laboratory data.

## Data and licences

- Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara
- Soil moisture: NASA SMAP L4 (SPL4SMGP), NSIDC DAAC
- Vegetation: NASA VIIRS VNP13A3, LP DAAC
- Fires: NASA FIRMS, VIIRS 375 m active fires
- Tree cover: Hansen/UMD/Google/USGS/NASA Global Forest Change, CC BY 4.0
- Boundaries: geoBoundaries GHA ADM2, CC BY 4.0 (source: USAID Ghana HPNO and Ghana Statistical Service)
- Basemap: © OpenStreetMap contributors. Map library: Leaflet (BSD 2-Clause)

## Disclaimer

Tinga Lens is a research and environmental information platform. It does not replace official government warnings
or emergency management information.
## Copyright

© 2026 Frank Anyoka Adekilae. All rights reserved.

The code and text in this repository may be read for reference. Copying, reuse or
redistribution requires written permission. The datasets Tinga Lens draws on belong
to their original providers and are covered by their own licences, listed above.
