# Changelog

Every change to a method or product is recorded here. Product versions are shown on each map and in every download.

## 2026-10-08

- Visit and download counts with GoatCounter (no cookies, no personal data). Each download is recorded by what was taken and as a total; the home page shows the total once there is a real number. A line in the footer says what is counted.

## 2026-10-07

- New Agriculture module (version 0.1): cropland (ESA WorldCover 2021) and the average soil nitrogen, phosphorus and potassium on each district's cropland (iSDAsoil Africa, 30 m). Districts are shaded in fifths among Ghana's districts; there are no agronomic thresholds. Both sources are read through Google Earth Engine by `scripts/agriculture.py`, which has a trial mode that publishes nothing.
- Agriculture: main crop in each district and one map for each of nine main crops (maize, cassava, yam, rice, plantain, cocoa, sorghum, pearl millet, groundnut), from SPAM 2020 (a published model, not an observation). Built by `scripts/crops.py` from a free download; no Earth Engine is used. It has a trial mode that publishes nothing.
- Agriculture: district crop profile (main crop, other major crops, estimated area and share) on the map and the Districts page.
- Agriculture: soil maps now cover every district on one basis (average over all land). New soil layers: pH, organic matter (estimated from organic carbon), clay, sand and bulk density. The cropland-only value and the deeper soil are in the panel. A table of all values can be downloaded (data/soil-by-district.csv).
- The purpose of Tinga Lens was added to the Home and About pages.
- The photograph of the founder was added to the About page.

## 2026-10-06

- Every district download (CSV) now carries the latitude and longitude of the district's centre point.
- Biodiversity: recorded places can be downloaded with their coordinates, for one species across Ghana, a region or a district, and for every species in a district or region. Positions of globally threatened species (IUCN Critically Endangered, Endangered, Vulnerable) are rounded to 0.1 degree, about 11 km, so that exact sites are not published.
- "This month in Ghana": a brief written automatically from the published figures. District pages can produce a one-image summary card.

## 2026-10-04

- Flood-prone land 0.1 (experimental): land seen under water by Sentinel-1 radar in at least 2 of the years 2016 to 2025, worked out by Tinga Lens in Google Earth Engine. This is the first product that uses Earth Engine.
- Flood-prone land 0.2: land along Lake Volta and other large reservoirs is reported separately, because the first version's ranking was led by lake-shore districts where the lake had risen over its banks. Early years with too few radar images are dropped automatically, because 2016 and 2017 showed far less flooding than later years. New colours.
- Flood-prone land: 2017 shows far less flooding than later years with the same method, for reasons unrelated to the number of images. The script now starts the record at 2018; the published map still covers 2017 to 2025 until the next rebuild, which waits for Earth Engine allowance (one rebuild uses about a third of the free monthly quota).
- River flood hazard 1.0: share of each district inside the modelled 1-in-100-year river flood zone (JRC global river flood hazard maps v2.1), with the people and built-up area inside it (GHSL 2020). A new product type, "Published model". Read through Earth Engine.
- Observed flooding 0.2: a second event, northern Ghana in August to October 2020. The 2023 lower Volta map was renamed so that it no longer attributes all the water to the dam spillage, and now carries the result of its comparison with official reports, with notes on the districts where the two disagree.
- Surface water change 1.0: permanent water gained and lost in each district, 1984 to 2021 (JRC Global Surface Water v1.4). Read through Earth Engine.
- Top menu reduced to Home, Districts, Data & Methods, About and Contact us; a Contact us page; the map pages carry a row of topic links.
- The percentage-of-normal figures on maps and district pages now read as "6% below normal" in place of "94% of normal".
- Human modification 1.0 and Change in human modification 1.0: district averages of the Global Human Modification v3 index, 1990 to 2020, ranked among Ghana's districts. A new product type, "Published index", marks indices created by other research groups.
- The Urban Exposure module became Human Pressure and now also holds built-up area growth.
- Biodiversity: the species list and the species explorer follow the chosen region; one species can be downloaded by district.
- The region filter now appears on every layer.

## 2026-10-03: new modules and the tingalens.org domain

- Recorded species 0.1 (GBIF): species counts by district, species lists, a species explorer, threatened species (IUCN Red List categories), and data coverage. Records under a non-commercial licence were added after an expert noted that mammals were under-represented; a table of records by group was added.
- Observed flooding 0.1 (Copernicus Global Flood Monitoring): one event, the lower Volta flooding of September to November 2023.
- Built-up area growth 1.0 (Global Human Settlement Layer), 2000 to 2020.
- Region filter for the 16 regions; satellite background; map image downloads carrying the Tinga Lens name; a recommended citation for every map.
- Redesign: map first on the home page, new typefaces and colours.
- The site moved to https://tingalens.org.
- Active fire detections: the update no longer stalls when the data provider is unreachable; it publishes up to the last complete day.

## 2026-10-03: site version 2.0

- Restructured the site into modules: Drought, Fire, Vegetation & Forest, Flood (in development), Urban Exposure (in development).
- Added district profiles, a Data & Methods page with validation results, and a disclaimer on every page.
- Every product is now labelled as Observed, Environmental condition or Modeled risk.
- Active fire detections 1.1: individual detections from the last 7 days can be shown as points.

## 2026-10-02

- Fire probability 0.2 (experimental): logistic regression tested on left-out fire years; month-by-month scores; past estimates and outcomes can be browsed on the map.
- Rainfall anomaly 1.1, Soil moisture anomaly 1.1, Vegetation greenness anomaly 1.1, Tree cover loss 1.1: any past period can be shown on the map and downloaded.
- Fire probability 0.1: first version.

## 2026-10-01 to 2026-10-02: versions 1.0

- Rainfall anomaly 1.0 (CHIRPS), Soil moisture anomaly 1.0 (NASA SMAP Level-4), Tree cover loss 1.0 (Global Forest Change),
  Vegetation greenness anomaly 1.0 (NASA VIIRS), Active fire detections 1.0 (NASA FIRMS).
