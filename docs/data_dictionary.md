# Data dictionary

All published results are JSON files in `data/`. The website reads them directly, and they can be used by anyone.

## `data/layers.json`

The list of published layers: `key`, `label`, `file`.

## Layer files: `data/<key>.json`

Keys: `drought`, `soil`, `vegetation`, `fires`, `firerisk`, `forest`.

| Field | Meaning |
|---|---|
| `key`, `label`, `title` | Identity of the layer |
| `subtitle` | The period the latest map covers |
| `updated` | Date the file was produced (UTC) |
| `source` | Data source and version |
| `categories` | Legend: `key`, `label`, `note`, `color` |
| `counts` | Number of districts in each category |
| `how`, `limits` | Method summary and limitations, as shown on the site |
| `history` | Path of the full record for this layer, if there is one |
| `districts` | One entry per district, keyed by `shapeID` (matches `data/districts.geojson`) |

Each district entry has: `name`, `cat` (category key), `big` (main figure), `big_note` (what the figure means),
`rows` (label and value pairs), and `v` / `c` (values and categories for the small chart).

## Full records

| File | Contents |
|---|---|
| `drought_history.json` | Three-month rainfall totals (mm) for every month since 1981, per district |
| `soil_history.json` | Monthly root-zone and surface soil moisture (m³/m³) since April 2015 |
| `soil_days.json` | The same, for each sampled day (every five days) |
| `vegetation_history.json` | Monthly NDVI since 2012; empty where too cloudy |
| `fires_history.json` | Fire detections per month since 2012 |
| `fire_points.json` | Each fire detection in the last 7 days: latitude, longitude, date, time (UTC), confidence, fire radiative power (MW), day or night, district |
| `firerisk_history.json` | For each five-day period since April 2015: estimated chance (%), usual chance (%), and whether a fire was detected |
| `firerisk_report.json` | Test results for the fire probability model |

## Other files

- `districts.geojson`: district boundaries (geoBoundaries GHA ADM2, CC BY 4.0, simplified). `shapeID` is the district identifier; `shapeName` is its name.
- `site.json`: site settings (founder line, contact, sign-up link).
