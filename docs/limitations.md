# Limitations

Tinga Lens publishes estimates derived from satellite, climate and model data. It does not replace official warnings.

## All products

- Results are district averages. They do not describe individual farms, villages or streets.
- District boundaries are the 260 districts of 2019. Newer districts are not yet shown.
- No product has yet been systematically compared with ground measurements in Ghana by Tinga Lens.
- Region names were assigned by matching the 2019 districts to the 16 current regions; three districts on a regional border were placed by where most of their land falls.
- "Normal" depends on the length of the record: 1991–2020 for rainfall, 2015 onwards for soil moisture, 2012 onwards for vegetation and fires.

## By product

- **Rainfall anomaly**: a rainfall indicator only. It does not measure crop damage, river levels or groundwater. Not rated where normal rainfall is under 30 mm for the period.
- **Soil moisture anomaly**: NASA's SMAP Level-4 product merges satellite observations into a land model. It is an estimate, not a measurement at depth. Under dense forest the satellite signal is weak.
- **Vegetation greenness anomaly**: clouds hide the ground, mainly in the south during the rains, so districts are often not rated. Low greenness has many causes.
- **Active fire detections**: satellites pass a few times a day and miss short or small fires and fires under cloud. Detections are not burned area.
- **Fire probability (experimental)**: most of its skill is the seasonal pattern. It has no temperature, humidity or wind inputs. It is not a fire warning.
- **Tree cover loss**: not the same as deforestation. It includes plantation harvests and counts cocoa, rubber and oil palm as tree cover. Regrowth is not subtracted.

- **Observed flooding**: two past events only (lower Volta 2023, northern Ghana 2020). The area figure does not rank how badly districts were hit. Satellites pass every few days, and radar misses water under trees and between buildings, so the figures are a lower bound. Not a live flood map or a warning.
- **Flood-prone land**: experimental and not checked on the ground. It is Tinga Lens's own reading of radar images for June to October. Lake and reservoir edges, irrigated rice, salt pans and seasonal wetlands can be counted as flooded; flooding in towns, under trees, or lasting only a day or two is missed. It shows where water has been seen repeatedly, not where it will flood next.
- **River flood hazard**: a model of large rivers only, on a 90 m grid. It leaves out small streams, city drainage and the sea, and its documentation does not say that dams or flood defences are represented. It shows where water could reach, not where it has flooded. The people and built-up figures are estimates from a 2020 population grid.
- **Surface water change**: compares the first and last years in which Landsat saw each place, which differ from place to place; the record ends in 2021. New water includes reservoirs, dugouts and mining pits. Water narrower than 30 m or under trees is missed.
- **Built-up area growth**: buildings only, in 1 km cells; the latest date is 2020. Percent growth is large where there was little to begin with.
- **Human modification**: an index created by other researchers from many datasets, not a measurement. The source reports a typical error of about 0.18 for a single cell. Classes are fifths of Ghana's districts, not fixed levels.
- **Recorded species**: reflects where recording has happened. Birds make up about three quarters of the records; large mammals are almost absent. No record does not mean a species is absent. Includes non-commercial records.

### Cropland and soil nutrients

- Cropland is a satellite classification for 2021. Small farms mixed with trees, tree crops such as cocoa and resting fields are hard to separate, so cropland is likely to be under-counted, most of all in the forest zone. Individual fields are not mapped.
- Soil nitrogen, phosphorus and potassium come from iSDAsoil, a machine-learning prediction at 30 m made from soil samples and satellite data of about 2001 to 2017. They are predictions, not measurements, and are not a substitute for a soil test.
- The shading compares districts with each other. It is not a sufficiency rating and it is not fertiliser advice.
- Total nitrogen is not plant-available nitrogen. Phosphorus and potassium are "extractable", and the result depends on the laboratory method.
- Averages are over cropland as seen at 30 m. Districts with under 1 km² of cropland are not rated. The soil model is less reliable in dense forest.

### Crops

- Crop areas are a model estimate (SPAM 2020), not a record of what each farmer planted. National and regional statistics are shared out over a 10 km grid using satellite cropland maps and the suitability of the land for each crop.
- Grid cells are about 85 km², similar to many districts, and each cell is shared between districts by overlapping area. Differences between neighbouring districts can be an artefact of the grid.
- The estimates show a typical year around 2020, not the current season or a trend. Crop area is physical area, not counting repeat harvests, and rainfed and irrigated land are added together.
- Crop groups such as "other roots and tubers" hide individual crops. District crop statistics from the Ministry of Food and Agriculture are not published as open data, so the model could not be checked district by district.

## Not yet published

Habitat suitability is in development. The site shows no numbers for them.
