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
| Flood | Observed flooding for two documented events (Copernicus Global Flood Monitoring, Sentinel-1) ; flood-prone land from Sentinel-1 radar (experimental); river flood hazard and exposure (JRC global flood model, GHSL); surface water change (JRC Global Surface Water) | Published |
| Human Pressure | Human modification index and its change since 1990 (Global Human Modification v3), built-up area growth (GHSL) | Published; exposure to flood-prone land in development |
| Biodiversity | Recorded species by district and region, species explorer (GBIF occurrence records, IUCN Red List categories) | Published; habitat suitability in development |

The site also has district profiles, a region filter, downloads (CSV and map images) and a recommended citation for every map.

## Data philosophy

Tinga Lens distinguishes between:

1. **Observed**: what a satellite recorded
2. **Environmental condition**: an observation compared with what is normal for the place and season
3. **Published index**: a combined index published by another research group, averaged here by district
4. **Modeled risk**: a statistical estimate made by Tinga Lens

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
- `GBIF_USER`, `GBIF_PWD`, `GBIF_EMAIL`: a free GBIF account (biodiversity)
- `EE_SERVICE_ACCOUNT_KEY`: the JSON key of a Google Earth Engine service account (flood-prone land, river flood hazard and surface water change; every other layer runs without it)

Then: Actions → Update data → Run workflow. Tick "Rebuild forest loss" once a year. Biodiversity rebuilds once a month,
or when "Rebuild biodiversity now" is ticked. Flooding, built-up area and human pressure are built once.

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
- Flooding: Copernicus Emergency Management Service, Global Flood Monitoring (Sentinel-1)
- Flood-prone land: Copernicus Sentinel-1 GRD, JRC Global Surface Water and NASA SRTM, read through Google Earth Engine
- River flood hazard: JRC global river flood hazard maps v2.1 (Baugh et al. 2024) and GHSL R2023A, read through Google Earth Engine
- Built-up area: Global Human Settlement Layer GHS-BUILT-S R2023A, European Commission JRC, CC BY 4.0
- Human modification: Theobald and others (2025), Global Human Modification v3, The Nature Conservancy, CC BY 4.0
- Species records: GBIF occurrence download (the DOI is shown on the Biodiversity page). Includes records under CC0, CC BY and CC BY-NC, so the biodiversity layer may not be used commercially
- Conservation status: IUCN Red List of Threatened Species, via GBIF
- Region names: geoBoundaries GHA ADM1 (OpenStreetMap)
- Satellite background: Esri World Imagery, under Esri's terms
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
