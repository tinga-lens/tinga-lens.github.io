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
| 2026-10-03 | Lower Volta districts | Observed flooding, Sep to Nov 2023 | Flooding along the river and estuary, peaking 16 to 23 October; largest in Ada East, Ada West, South Tongu, Anloga, Keta, North Tongu; about 40 km² in total | NOT YET CHECKED against a NADMO or UN situation report. The area is probably too small because radar misses flooded settlements | To do |
| 2026-10-04 | All districts | Human modification, 2020 | Accra and Kumasi highest (0.85 to 0.90); West Gonja (Mole National Park), Banda and Bole lowest (0.07 to 0.08); largest increases on the edges of Kumasi and Accra | Consistent with general knowledge of the country; no formal check | Tinga Lens review |

## Expert feedback

| Date | Who | Product | Comment | What was done |
|---|---|---|---|---|
| 2026-10-03 | A senior official of the Forestry Commission of Ghana (reported verbally to the founder; not yet in writing) | Recorded species | Mammals are under-represented; plants and birds dominate | Confirmed from the data: birds 76% of records, mammals under 1%. Records under a non-commercial licence were added, raising mammal records from 7,491 to 10,596. A table of records by group and a plain statement of the gap were added to the page. Large mammals remain almost absent because survey data are not published to GBIF |
