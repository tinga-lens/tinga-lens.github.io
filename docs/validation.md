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

Rainfall, soil moisture, vegetation, fire detections and tree cover loss come from published datasets validated by their producers.
Tinga Lens has not yet compared them systematically with ground measurements in Ghana.

A simple log of ground checks should be kept here as they are made:

| Date | District | Product | What the map showed | What was reported on the ground | Source of report |
|---|---|---|---|---|---|
| | | | | | |
