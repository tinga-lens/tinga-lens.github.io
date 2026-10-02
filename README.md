# Tinga Lens

Open, satellite-based environmental monitoring for Ghana, by district.
First layer: rainfall and drought.

## What is here

| File | What it does |
|---|---|
| `index.html` | The website (map, legend, district details) |
| `scripts/drought.py` | Downloads CHIRPS rainfall and builds `data/drought.json` |
| `data/districts.geojson` | Ghana's 260 districts (geoBoundaries, CC BY 4.0, simplified) |
| `data/drought.json` | The numbers the map shows. Ships with DEMO data until the first real run |
| `.github/workflows/update.yml` | Runs the script every Monday and publishes any change |
| `vendor/` | Leaflet map library (BSD 2-Clause) |

## Put it online (GitHub Pages)

1. Create a new **public** repository and upload everything in this folder, keeping the folder structure (including the hidden `.github` folder).
2. **Settings → Pages**: Source = "Deploy from a branch", Branch = `main`, folder = `/ (root)`.
3. **Settings → Actions → General → Workflow permissions**: choose "Read and write permissions".
4. **Actions → Update drought data → Run workflow**. The first run downloads the full rainfall record and takes several minutes. When it finishes, the demo banner disappears and the map shows real data.

## Run it on your own computer

    pip install -r requirements.txt
    python scripts/drought.py          # real data
    python scripts/drought.py --demo   # made-up data, for previewing only
    python -m http.server              # then open http://localhost:8000

## Method

For each district: rainfall total over the latest 3 months, compared with the same
3 months in each year of 1991-2020. Categories come from the rank among those
30 years (driest 10% = very dry, driest 30% = dry, and the reverse for wet).
Where normal 3-month rainfall is below 30 mm the district is marked "dry season"
and not rated. Settings are at the top of `scripts/drought.py`.

## Data and licences

- Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara (public domain). The script uses whichever of CHIRPS v3.0 or v2.0 has the most recent month, for the whole record.
- Boundaries: geoBoundaries GHA ADM2, CC BY 4.0. Source: USAID Ghana HPNO and Ghana Statistical Service. Boundaries are for 2019.
- Basemap: © OpenStreetMap contributors.
