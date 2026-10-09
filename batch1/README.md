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
| Biodiversity | Recorded species by district and region, species explorer (GBIF occurrence records) | Published; habitat suitability in development |

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

Processing runs in GitHub Actions with Python. Most products use only downloaded datasets. Selected products (flood-prone land, river flood hazard, surface water change, cropland and soil) use Google Earth Engine for geospatial processing. The sources and methods are documented for each product.

## Running the update

Repository secrets needed (Settings → Secrets and variables → Actions):

- `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`: a free NASA Earthdata login (soil moisture, vegetation)
- `FIRMS_MAP_KEY`: a free NASA FIRMS key (fires)
- `GBIF_USER`, `GBIF_PWD`, `GBIF_EMAIL`: a free GBIF account (biodiversity)
- `EE_SERVICE_ACCOUNT_KEY`: the JSON key of a Google Earth Engine service account. It is needed for the products that use Earth Engine: cropland, the soil properties (nitrogen, phosphorus, potassium, pH, organic matter, clay, sand, bulk density), flood-prone land, river flood hazard and surface water change. Every other layer runs without it. Never put this key in the repository; store it only as a repository secret.

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
- Species records: GBIF occurrence download (the DOI is shown on the Biodiversity page). Only records published under CC0 or CC BY are used; records under non-commercial licences are left out. Credit GBIF and the download DOI
- Conservation status: not published. Tinga Lens does not redistribute IUCN Red List categories; see https://www.iucnredlist.org
- Region names: geoBoundaries GHA ADM1 (OpenStreetMap)
- Satellite background: Esri World Imagery, under Esri's terms
- Cropland: ESA WorldCover 2021 v200, CC BY 4.0, read through Google Earth Engine
- Soil properties: iSDAsoil Africa v1 (Hengl and others, 2021), CC BY 4.0, read through Google Earth Engine
- Crops: SPAM 2020 v2r2, International Food Policy Research Institute (IFPRI), CC BY 4.0 with IFPRI's attribution statement
- Boundaries: geoBoundaries GHA ADM2, CC BY 4.0 (source: USAID Ghana HPNO and Ghana Statistical Service)
- Basemap: © OpenStreetMap contributors. Map library: Leaflet (BSD 2-Clause)

## Disclaimer

Tinga Lens is a research and environmental information platform. It does not replace official government warnings
or emergency management information.
## Licence

Tinga Lens uses separate licences for software and for original content:

- **Software**: MIT licence, see `LICENSE`.
- **Original documentation, text and data produced by Tinga Lens**: CC BY-NC 4.0 (non-commercial use), see `LICENSE-DATA.md`.
- **Third-party materials**: subject to their original licences and terms of use (listed above).
- **Tinga Lens name and logo**: rights reserved, see `NOTICE.md` and `TRADEMARKS.md`.

These licences apply only to materials and rights that the project owner is authorised to license. `NOTICE.md` explains the scope in detail.

© 2026 Frank Anyoka Adekilae.

## How to cite

Adekilae, F. A. (2026). *Tinga Lens: Environmental monitoring for Ghana*. https://tingalens.org

A DOI will be added here once the first release is archived.
