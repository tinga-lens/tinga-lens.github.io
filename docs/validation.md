# Validation

## Fire probability

The model is tested by leaving out one fire year (July to June) at a time, fitting on the others, and predicting the left-out year.
The full results are regenerated on every update and published in `data/firerisk_report.json`, and shown on the Data & Methods page:

- ROC-AUC and Brier score for each model variant (season only; plus surface soil moisture; plus root-zone soil moisture; plus rainfall and greenness)
- scores for each calendar month, compared with the seasonal pattern alone
- a calibration table (estimated chance against observed frequency)
- model coefficients

The variant with the lowest error on left-out years is the one shown on the map.

Not yet reported: precision, recall, F1 and PR-AUC (these need a decision threshold, which has not been set).

## Other products

Rainfall, soil moisture, vegetation, fire detections, tree cover loss, flooding, built-up area, human modification and species records come from published datasets validated by their producers.
Tinga Lens has not yet compared them systematically with ground measurements in Ghana.

A simple log of ground checks should be kept here as they are made:

| Date | District | Product | What the map showed | What was reported on the ground | Source of report |
|---|---|---|---|---|---|
| 2026-10-04 | Lower Volta districts | Observed flooding, Sep to Nov 2023 | Flooding in 11 districts, peaking 16 to 23 October; largest in Ada East (12.8 km²), Ada West (7.7), South Tongu (4.2), Anloga (3.9), Keta (3.4), North Tongu (3.1); about 40 km² in total | The Volta River Authority named nine districts: Asuogyaman, Shai Osudoku, North, Central and South Tongu, Anloga, Keta, Ketu South and Ada East, with the three Tongu districts worst hit and about 39,000 people displaced. UNOSAT mapped flooding in North Tongu, South Tongu and Ada East from images of 15 to 18 October. The map shows 8 of the 9 districts and the right dates. It misses Asuogyaman, ranks the Tongu districts low (flooded towns are invisible to radar), and shows Ada West, Ningo/Prampram and Upper Manya, which were not reported; water there may be lagoon or rain water. No official figure for flooded area was found. | Graphic Online, 31 Oct 2023; UNITAR-UNOSAT preliminary assessment, Oct 2023 |
| 2026-10-04 | All districts | Human modification, 2020 | Accra and Kumasi highest (0.85 to 0.90); West Gonja (Mole National Park), Banda and Bole lowest (0.07 to 0.08); largest increases on the edges of Kumasi and Accra | Consistent with general knowledge of the country; no formal check | Tinga Lens review |
| 2026-10-04 | Northern districts | Observed flooding, Aug to Oct 2020 | About 790 km² flooded in total, peaking 8 to 13 September; largest in West Mamprusi (130 km²), Karaga (107), Savelugu (103), Saboba (94), Kumbungu (86), Chereponi (49), Mamprugu Moagduri (47) | News reports of 5 to 9 September 2020: deaths and submerged farmland in the North East Region (West Mamprusi, East Mamprusi, Mamprugu Moagduri, Bunkpurugu) after the Bagre dam spillage and heavy rain; flooding at the White Volta bridge in Bawku West. The place and dates agree. No official list of districts or flooded area was found. | Citi Newsroom, 5 and 9 Sep 2020 |
| 2026-10-04 | Northern districts | Flood-prone land (Tinga Lens) against Observed flooding 2020 (Copernicus GFM) | Worst year 2020 in West Mamprusi (52 km²), Saboba (47), Chereponi (35), Savelugu (33), Kumbungu (27) | The Copernicus map of the same flood shows the same districts at the top, with two to three times the area (130, 94, 49, 103, 86 km²). Tinga Lens requires two images to agree and uses stricter thresholds, so a smaller area is expected. | Comparison of two products; not a ground check |
| 2026-10-04 | Lower Volta districts | River flood hazard (JRC model) | 73 to 78% of Ada East, Anloga and South Tongu inside the 1-in-100-year zone, and almost as much in the 1-in-10-year zone | Flooding on that scale has not happened every ten years since the Akosombo dam was built; the model appears not to represent the dam. The page says so. | Tinga Lens review |

## How the flood-prone setting was chosen

Six settings were run on 13 districts (4 October 2026) and compared with the 2023 lower Volta flood as mapped by Copernicus GFM. Flooded area, 15 September to 15 November 2023, in km²:

| District | A | B | D | E (chosen) | F | Copernicus GFM |
|---|---|---|---|---|---|---|
| Ada East | 12.8 | 11.1 | 5.6 | 9.5 | 4.4 | 12.8 |
| Ada West | 7.7 | 6.3 | 3.6 | 5.2 | 3.1 | 7.7 |
| South Tongu | 7.8 | 6.1 | 2.7 | 4.4 | 1.8 | 4.2 |
| Keta Municipal | 10.1 | 8.2 | 3.9 | 6.9 | 3.4 | 3.4 |
| North Tongu | 16.7 | 12.2 | 7.8 | 9.1 | 6.4 | 3.1 |
| Central Tongu | 4.2 | 3.6 | 2.3 | 2.8 | 1.7 | 0.9 |
| Asuogyaman | 4.2 | 3.8 | 2.8 | 3.4 | 2.5 | 0.0 |

Setting A (April to November, one image enough) flagged 150 to 330 km² a year in northern districts such as Bawku West and Builsa South, far more than is plausible, mostly dry bare soil at the start and end of the season. Restricting to June to October and requiring two images a year removed most of it. Setting E (VV below −18 dB, VH below −25 dB, 3 dB darker than usual, two images a year) is the middle of the settings that remain close to the Copernicus figures. It finds more flooding than Copernicus in the three Tongu districts and in Asuogyaman, which is the direction the official reports point. Settings D and F find less than half the Copernicus area in Ada East and South Tongu. Setting C is the same as B with two images a year; its event figures equal B's.

Years 2016 and 2017 are left out. With setting E the national flooded area was 122 km² (2016) and 95 km² (2017), against 280 to 500 km² in every later year. The number of usable images does not explain it: 2017 had 213, about the same as 2022 to 2024 (about 195 each), which show 330 to 400 km². The likely cause is a change in how Sentinel-1 images were processed in early 2018, but this has not been confirmed.

This is a comparison with one event and one other satellite product. It is not a ground check.

## Expert feedback

| Date | Who | Product | Comment | What was done |
|---|---|---|---|---|
| 2026-10-03 | A senior official of the Forestry Commission of Ghana (reported verbally to the founder; not yet in writing) | Recorded species | Mammals are under-represented; plants and birds dominate | Confirmed from the data: birds 76% of records, mammals under 1%. Records under a non-commercial licence were added, raising mammal records from 7,491 to 10,596. A table of records by group and a plain statement of the gap were added to the page. Large mammals remain almost absent because survey data are not published to GBIF |
