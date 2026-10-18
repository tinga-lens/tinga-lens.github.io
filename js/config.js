// Tinga Lens - site settings: navigation, modules and the product register.
// Every product is one of three kinds, and the site labels each one:
//   observed  = what a satellite recorded
//   condition = an observation compared with what is normal for the place and season
//   model     = a statistical estimate made by Tinga Lens
const TL = {
  name: "Tinga Lens",
  tagline: "See Ghana's environment changing.",
  site: "https://tingalens.org",
  author: "Adekilae, F. A.",            // how the author appears in citations
  repo: "https://github.com/tinga-lens/tinga-lens.github.io",
  nav: [
    ["Home", ""], ["About", "pages/about.html"], ["Maps", null],      // "Maps" opens the list of topics below
    ["Districts", "pages/districts.html"], ["Data & Methods", "pages/methods.html"], ["Contact us", "pages/contact.html"],
  ],
  // the map pages; shown as a second row on those pages so a reader can move between topics
  topics: [
    ["Drought", "pages/drought.html"], ["Fire", "pages/fire.html"],
    ["Vegetation & Forest", "pages/vegetation.html"], ["Flood", "pages/flood.html"], ["Agriculture", "pages/agriculture.html"],
    ["Human Pressure", "pages/pressure.html"], ["Biodiversity", "pages/biodiversity.html"],
  ],
  // layers that share one tab and are chosen from a list under it (the list label and the tab name)
  groups: {
    crops: { tab: "Crops", label: "Crop" },
    soilprops: { tab: "Soil", label: "Soil property" },
  },
  status: {
    observed: { label: "Observed", text: "What a satellite recorded." },
    index: { label: "Published index", text: "A combined index published by another research group, averaged here by district." },
    condition: { label: "Environmental condition", text: "An observation compared with what is normal for that place and time of year." },
    pubmodel: { label: "Published model", text: "A model result published by another research group, added up here by district. It is not an observation." },
    derived: { label: "Derived by Tinga Lens", text: "Worked out by Tinga Lens from satellite images using its own rules. It is the site's own reading, not something a satellite recorded directly, and it has only been checked in part." },
    experimental: { label: "Experimental", text: "Worked out by Tinga Lens from rainfall data using candidate rules that have not yet been checked against rain-gauge records. Treat it as a first look, not a finding." },
    model: { label: "Modeled risk", text: "A statistical estimate made by Tinga Lens. It is tested, but it is not an observation." },
  },
  // one entry per layer file in data/; `tab` is the name shown on module pages
  products: {
    drought: { name: "Rainfall anomaly", tab: "Rainfall", module: "Drought", page: "pages/drought.html", status: "condition", version: "1.1",
               source: "CHIRPS rainfall, Climate Hazards Center, UC Santa Barbara", type: "Satellite and rain-gauge blend",
               resolution: "about 5 km", updates: "Monthly", baseline: "1991–2020" },
    soil: { name: "Soil moisture anomaly", tab: "Soil moisture", module: "Drought", page: "pages/drought.html", status: "condition", version: "1.1",
            source: "NASA SMAP Level-4 (SPL4SMGP), NSIDC DAAC", type: "Satellite observations merged into a land model",
            resolution: "9 km", updates: "Every 5 days", baseline: "2015 onwards" },
    mismatch: { name: "Rain and soil moisture compared", tab: "Rain and soil (experimental)", module: "Drought", page: "pages/drought.html", status: "experimental", version: "0.1 (experimental)",
                source: "CHIRPS rainfall and NASA SMAP L4 soil moisture, compared by Tinga Lens", type: "Derived by Tinga Lens from two published datasets",
                resolution: "about 5 km rainfall and 9 km soil moisture, averaged by district", updates: "Monthly", baseline: "2015 to last year (both measures)" },
    rainseason: { name: "Start of the rainy season", tab: "Rainy season (experimental)", module: "Drought", page: "pages/drought.html", status: "experimental", version: "0.2 (experimental)",
                  source: "CHIRPS daily rainfall, Climate Hazards Center, UC Santa Barbara; start dates worked out by Tinga Lens", type: "Derived by Tinga Lens from satellite and rain-gauge rainfall using candidate rules",
                  resolution: "about 5 km, averaged by district", updates: "Weekly during the season", baseline: "1991–2020" },
    dryspell: { name: "Longest dry spell", tab: "Dry spells (experimental)", module: "Drought", page: "pages/drought.html", status: "experimental", version: "0.1 (experimental)",
                source: "CHIRPS daily rainfall, Climate Hazards Center, UC Santa Barbara; dry spells counted by Tinga Lens", type: "Derived by Tinga Lens from satellite and rain-gauge rainfall",
                resolution: "about 5 km, averaged by district", updates: "Weekly during the season", baseline: "1991–2020" },
    fires: { name: "Active fire detections", tab: "Observed fire", module: "Fire", page: "pages/fire.html", status: "observed", version: "1.1",
             source: "NASA FIRMS, VIIRS (S-NPP) 375 m active fires", type: "Satellite observation",
             resolution: "375 m detections, summed by district", updates: "Weekly", baseline: "2012 onwards" },
    firerisk: { name: "Fire probability", tab: "Fire probability", module: "Fire", page: "pages/fire.html", status: "model", version: "0.2 (experimental)",
                source: "Tinga Lens logistic regression on SMAP, FIRMS, CHIRPS and VIIRS data", type: "Statistical model",
                resolution: "District, five-day periods", updates: "Weekly", baseline: "Fitted to 2015 onwards" },
    vegetation: { name: "Vegetation greenness anomaly", tab: "Vegetation condition", module: "Vegetation & Forest", page: "pages/vegetation.html", status: "condition", version: "1.1",
                  source: "NASA VIIRS vegetation index (VNP13A3), LP DAAC", type: "Satellite observation",
                  resolution: "1 km", updates: "Monthly", baseline: "2012 onwards" },
    forest: { name: "Tree cover loss rate", tab: "Forest change", module: "Vegetation & Forest", page: "pages/vegetation.html", status: "observed", version: "1.1",
              source: "Global Forest Change (Hansen/UMD/Google/USGS/NASA), Landsat", type: "Derived from satellite images",
              resolution: "30 m, summed by district", updates: "Yearly", baseline: "Tree cover in 2000" },
    floodprone: { name: "Flood-prone land", tab: "Flood-prone land", module: "Flood", page: "pages/flood.html", status: "derived", version: "0.2 (experimental)",
                  source: "Copernicus Sentinel-1 radar, processed by Tinga Lens in Google Earth Engine", type: "Derived from satellite radar images",
                  resolution: "40 m, summed by district", updates: "Yearly", baseline: "Each place's usual radar picture, 2019 to 2021" },
    floodhazard: { name: "River flood hazard", tab: "River flood hazard", module: "Flood", page: "pages/flood.html", status: "pubmodel", version: "1.0",
                   source: "JRC global river flood hazard maps v2.1 (Copernicus Emergency Management Service); people and built-up area from GHSL 2020", type: "Published model, added up by district",
                   resolution: "90 m, summed by district", updates: "With each new release of the source", baseline: "Floods expected once in 10 to 500 years" },
    water: { name: "Surface water change", tab: "Surface water change", module: "Flood", page: "pages/flood.html", status: "observed", version: "1.0",
             source: "JRC Global Surface Water v1.4 (Landsat)", type: "Derived from satellite images",
             resolution: "30 m, summed by district", updates: "With each new release of the source", baseline: "First year each place was seen, 1984 onward" },
    flood: { name: "Observed flooding: lower Volta, 2023", tab: "Flood 2023: lower Volta", module: "Flood", page: "pages/flood.html", status: "observed", version: "0.2",
             source: "Copernicus Global Flood Monitoring (GFM), Sentinel-1 radar", type: "Derived from satellite radar images",
             resolution: "20 m, summed by district", updates: "Per flood event", baseline: "Reference water map" },
    flood2020: { name: "Observed flooding: northern Ghana, 2020", tab: "Flood 2020: northern Ghana", module: "Flood", page: "pages/flood.html", status: "observed", version: "0.2",
                 source: "Copernicus Global Flood Monitoring (GFM), Sentinel-1 radar", type: "Derived from satellite radar images",
                 resolution: "20 m, summed by district", updates: "Per flood event", baseline: "Reference water map" },
    cropland: { name: "Open-field cropland", tab: "Cropland", module: "Agriculture", page: "pages/agriculture.html", status: "observed", version: "0.1 (experimental)",
          source: "ESA WorldCover 10 m v200 (2021)", type: "Derived from satellite images",
          resolution: "10 m, summed by district", updates: "With each new release of the sources", baseline: "Land seen as cropland in 2021" },
    crops: { name: "Main crop in each district", tab: "Main crops", module: "Agriculture", group: "crops", option: "Main crop in each district", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
             source: "SPAM 2020, International Food Policy Research Institute and partners", type: "Published model, added up by district",
             resolution: "10 km grid, shared between districts by area", updates: "With each new release of the source", baseline: "A typical year around 2020" },
    soiln: { name: "Soil nitrogen", tab: "Nitrogen", module: "Agriculture", group: "soilprops", option: "Nitrogen", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland values from ESA WorldCover 2021", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilp: { name: "Soil phosphorus", tab: "Phosphorus", module: "Agriculture", group: "soilprops", option: "Phosphorus", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland values from ESA WorldCover 2021", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilk: { name: "Soil potassium", tab: "Potassium", module: "Agriculture", group: "soilprops", option: "Potassium", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland values from ESA WorldCover 2021", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilph: { name: "Soil pH", tab: "pH", module: "Agriculture", group: "soilprops", option: "pH", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021)", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilom: { name: "Soil organic matter", tab: "Organic matter", module: "Agriculture", group: "soilprops", option: "Organic matter", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021)", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilclay: { name: "Soil clay content", tab: "Clay", module: "Agriculture", group: "soilprops", option: "Clay", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021)", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilsand: { name: "Soil sand content", tab: "Sand", module: "Agriculture", group: "soilprops", option: "Sand", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021)", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilbd: { name: "Soil bulk density", tab: "Bulk density", module: "Agriculture", group: "soilprops", option: "Bulk density", page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021)", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    pressure: { name: "Human modification of the land", tab: "Human modification", module: "Human Pressure", page: "pages/pressure.html", status: "index", version: "1.0",
                source: "Global Human Modification v3, Theobald and others (2025), The Nature Conservancy", type: "Combined index from many datasets",
                resolution: "300 m, averaged by district", updates: "With each new release", baseline: "Ranked among Ghana's districts" },
    pressurechange: { name: "Change in human modification", tab: "Change since 1990", module: "Human Pressure", page: "pages/pressure.html", status: "index", version: "1.0",
                      source: "Global Human Modification v3, Theobald and others (2025), The Nature Conservancy", type: "Combined index from many datasets",
                      resolution: "300 m, averaged by district", updates: "With each new release", baseline: "1990" },
    urban: { name: "Built-up area growth", tab: "Built-up area", module: "Human Pressure", page: "pages/pressure.html", status: "observed", version: "1.0",
             source: "Global Human Settlement Layer GHS-BUILT-S R2023A, European Commission JRC", type: "Derived from satellite images",
             resolution: "1 km, summed by district", updates: "With each new release", baseline: "Built-up area in 2000" },
    biodiversity: { name: "Recorded species", tab: "Recorded species", module: "Biodiversity", page: "pages/biodiversity.html", status: "observed", version: "0.1 (experimental)",
                    source: "GBIF occurrence records (CC0 and CC BY only)", type: "Field observations and museum specimens",
                    resolution: "Individual records, counted by district", updates: "Monthly", baseline: "All years on record" },
  },
  // modules that are planned but have no data yet; the site shows no numbers for them
  planned: {
  },
  disclaimer: "Tinga Lens provides research and environmental information derived from satellite, climate and geospatial datasets. Products may contain measurement, model and classification uncertainties. Tinga Lens should not be used as the sole source for emergency response, evacuation, disaster management or other safety-critical decisions. Consult the relevant Ghanaian authorities for official warnings and emergency information.",
};

// one layer for each main crop (built by scripts/crops.py)
[["maiz", "Maize"], ["cass", "Cassava"], ["yams", "Yam"], ["rice", "Rice"], ["plnt", "Plantain"], ["coco", "Cocoa"], ["sorg", "Sorghum"], ["pmil", "Pearl millet"], ["grou", "Groundnut"]].forEach(([c, n]) => {
  TL.products["crop_" + c] = { name: n + ": estimated crop area", tab: n, module: "Agriculture", group: "crops", option: n, page: "pages/agriculture.html", status: "pubmodel", version: "0.1 (experimental)",
    source: "SPAM 2020, International Food Policy Research Institute and partners", type: "Published model, added up by district",
    resolution: "10 km grid, shared between districts by area", updates: "With each new release of the source", baseline: "A typical year around 2020" };
});

// "94% of normal" is easier to read as "6% below normal". Used wherever a figure is shown.
TL.dl = rows => rows.map(r => r[1] === "" ? `<dt class="hd">${TL.esc(r[0])}</dt><dd class="hd"></dd>` : r[0] === "" ? `<dd class="full">${TL.esc(r[1])}</dd>` : `<dt>${TL.esc(r[0])}</dt><dd>${TL.esc(TL.rel(r[1]))}</dd>`).join("");
TL.esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
TL.table = t => !t ? "" : `<table class="mv"><caption>${TL.esc(t.caption)}</caption><thead><tr>${t.head.map(c => `<th>${TL.esc(c)}</th>`).join("")}</tr></thead>
  <tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${TL.esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>${t.note ? `<p class="sub">${TL.esc(t.note)}</p>` : ""}`;
TL.rel = t => String(t ?? "").replace(/(\d+)% of normal/g, (m, n) => { const p = +n - 100; return p === 0 ? "equal to normal" : `${Math.abs(p)}% ${p > 0 ? "above" : "below"} normal`; });
TL.relBig = (big, note) => {
  const m = /^(\d+)%$/.exec(big || "");
  if (!m || !/^of normal/.test(note || "")) return [big, TL.rel(note)];
  const p = +m[1] - 100, rest = note.replace(/^of /, "");
  return p === 0 ? ["Normal", rest.replace(/^normal /, "")] : [`${Math.abs(p)}% ${p > 0 ? "above" : "below"}`, rest];
};

/* =====================================================================================================
   Display fixes, added after the October 2026 expert review.
   They run on a layer's data each time it is drawn, so they work on the files already published and do
   not have to wait for the next data update. Rules that change the numbers themselves live in scripts/.
     TL.pre[key]      runs once when a layer is loaded (it may fetch another file)
     TL.post[key]     runs every time the map is drawn
     TL.measures[key] lets the reader colour and rank the same layer by a second figure
   ===================================================================================================== */
TL.clean = s => String(s ?? "").replace(/\s+/g, " ").trim();
TL.n = s => { const m = /[+\-−]?\d[\d,]*\.?\d*/.exec(String(s ?? "")); return m ? parseFloat(m[0].replace(/,/g, "").replace("−", "-")) : null; };
TL.n0 = s => /^\s*none/i.test(String(s ?? "")) ? 0 : TL.n(s);
TL.row = (x, re) => { const r = ((x && x.rows) || []).find(q => re.test(q[0])); return r ? r[1] : null; };
TL.fmt = (v, dec = 0) => Number(v).toLocaleString("en", { minimumFractionDigits: dec, maximumFractionDigits: dec });

// wording that overlapped or was unclear in the legends
TL.noteFix = {
  "driest 30% of years": "driest 10 to 30% of years", "wettest 30% of years": "wettest 10 to 30% of years",
  "lowest 30% of years": "lowest 10 to 30% of years", "highest 30% of years": "highest 10 to 30% of years",
};
TL.labelFix = { "Far fewer fires": "Far fewer detections", "Far more fires": "Far more detections" };
TL.colorFix = {
  fires: { quiet: "#e4e4e4" },                                               // pale grey for "quiet": darker grey is kept for "no data"
};
TL.soilRamp = { n0: "#f1ece3", n1: "#d8c9b4", n2: "#bda389", n3: "#8f6e56", n4: "#5d3f2d" };   // neutral: the top fifth is not "better"
TL.hideEmpty = new Set(["not_yet", "dry_season", "cloud", "few", "low", "unknown", "mnone", "small", "s0", "none"]);   // classes left out of the legend when no district is in them
TL.titleFix = { forest: "Tree cover loss rate", cropland: "Open-field cropland" };
TL.minForestHa = 100;                       // under this much tree cover in 2000 a percentage is not meaningful
TL.minDetections = 10;                      // fires: under this many detections now and normally a district is "quiet"

// names for the two ranking buttons
TL.rankname = {
  fires: ["Most detections", "Fewest detections"], biodiversity: ["Most species recorded", "Fewest recorded"],
  forest: ["Fastest loss", "Slowest loss"], urban: ["Fastest growth", "Slowest growth"], dryspell: ["Longest spell", "Shortest spell"],
  mismatch: ["Soil wetter than rain suggests", "Soil drier than rain suggests"],
};

// one line under the ranking that says what it is ranked by
TL.ranknote = {
  drought: "Ranked by percent of normal rainfall. The colours show where this period ranks among the 30 baseline years, so two districts with the same percentage can have different colours. Open a district for “x of 30 years drier”.",
  mismatch: "Ranked by the gap between soil moisture and rainfall, after taking away the national pattern for the month. A positive gap means soil is wetter than the rainfall suggests. Open a district for both ranks.",
  dryspell: "Ranked by the length of the longest dry spell, in days; equal lengths are marked =. The colours compare each district with its own history, so a longer spell can have a milder colour where long spells are normal.",
  soil: "Ranked by percent of normal. Districts in the same 9 km grid cell have identical values, so they tie; tied values are marked =.",
  vegetation: "Ranked by percent of the district's own average greenness. Tied classes are marked =.",
  fires: "Ranked by number of detections, not by change from normal, so large districts rank high even when they are coloured blue.",
  firerisk: "Ranked by the estimated chance. Tied whole-percent values are marked =. Use “Compared with usual” to rank by how far above the usual chance a district is.",
  forest: "Ranked by the share of year-2000 tree cover lost. Small districts can rank high on small areas: choose “Hectares lost a year” to rank by area.",
  floodprone: "Ranked by flooded area (km²), which favours large districts. Choose “Share of the district's land” to rank by share.",
  floodhazard: "† Volta delta districts are modelled as if the Akosombo dam did not control the river (see Limits).",
  water: "Ranked by net change in km². Choose “Percent of earlier water” to see the change relative to each district's water at the start.",
  cropland: "Ranked by share of land. Choose “Area (km²)” to rank by size.",
  pressure: "Ranked to two decimals. Differences of 0.01 are far smaller than the source's error (about 0.18 for one cell); tied values are marked =.",
  pressurechange: "Differences of a few hundredths are within the source's uncertainty; tied values are marked =.",
  urban: "Ranked by percent growth, which favours districts that started small. Choose “Square kilometres added” to rank by size.",
  biodiversity: "Ranked by number of species recorded, which follows how much a district has been surveyed. Districts with under 100 records are left out of the ranking.",
};

// short warnings shown under the legend and printed on the PNG, so they travel with the map
TL.caveats = {
  drought: ["Colours show where this period's rainfall ranks among the 30 baseline years; the ranking uses percent of normal."],
  soil: ["Modelled soil moisture (NASA SMAP L4), not a measurement. Normal rests on about a dozen years, and districts in one 9 km grid cell share a value."],
  rainseason: ["Experimental: checked against rain gauges and typically about three weeks out. A rough guide only."],
  mismatch: ["Experimental: not checked against field soil moisture. SMAP is a model driven partly by its own rainfall, so some gaps are two rainfall estimates differing. A flag is a lead, not proof of drought."],
  dryspell: ["Experimental: dry-spell lengths have not been checked against rain gauges. Rain is averaged over each district, so one farm can have a longer spell than shown."],
  vegetation: ["Districts are not rated when clouds hide the ground or fewer than five other years exist for the month."],
  fires: ["A detection is one satellite overpass, so one fire can be counted more than once. The latest days are rapid-release data that NASA later revises."],
  firerisk: ["Experimental estimate of the chance of at least one satellite fire detection in the district in five days. Not a fire warning."],
  forest: ["Tree cover loss includes logging, farming, fire and harvested plantations. Rates on small tree-cover bases exaggerate small areas."],
  floodprone: ["Tinga Lens's own radar reading, not ground-checked. Radar misses flooding under forest and in towns, so “none detected” is not “no flooding”. Detection depends on how often a place is imaged."],
  floodhazard: ["Model result for larger rivers only. Sea flooding and street flooding (for example in Accra) are not included. † Volta delta districts are modelled without the Akosombo dam's control."],
  water: ["Dark blue mixes new reservoirs, the recovery of Lake Volta and water-filled mining pits. The record ends in 2021."],
  flood: ["One flood event only, from Copernicus radar mapping. Not a live flood map."],
  flood2020: ["One flood event only, from Copernicus radar mapping. Not a live flood map."],
  cropland: ["Open-field cropland only. Tree crops such as cocoa and farms under trees are mostly not captured, so forest-zone districts read as having little farmland."],
  crops: ["Model estimate. The district pattern comes from the model, not from district records. Pale colours mean the main crop is a weak majority."],
  pressure: ["An index built from many datasets, not a measurement. The source's error is about 0.18 for one cell."],
  pressurechange: ["An index built from many datasets. Small changes are within the source's uncertainty."],
  urban: ["Percent growth is large where there was little to begin with. Buildings only; a 1 km grid can miss new building inside already built-up cells."],
  biodiversity: ["The map shows where species were recorded as much as where they live. Districts with few records are shown separately."],
};
["soiln", "soilp", "soilk", "soilph", "soilom", "soilclay", "soilsand", "soilbd"].forEach(k => {
  TL.caveats[k] = ["Model prediction, not a measurement; the forest belt is least reliable. Shading compares districts and does not mean better land. The cropland-only value exists only where enough cropland was mapped."];
  TL.ranknote[k] = "Ranked by the all-land average. A higher value is not a better soil.";
});
["maiz", "cass", "yams", "rice", "plnt", "coco", "sorg", "pmil", "grou"].forEach(c => { TL.caveats["crop_" + c] = TL.caveats.crops; });

// extra sentences added to a layer's Limits list
TL.extralimits = {
  drought: ["The ranking and the colours use different measures. The ranking sorts by percent of normal rainfall; the colours show where this period ranks among the 30 baseline years. In the pop-up, “x of 30 years drier” is the figure the colours use.",
            "The map has not been reviewed for December to February. In those months many northern districts have too little normal rainfall to rate and may be grey."],
  soil: ["With only about a dozen earlier years, “driest 10% of years” means at most one earlier year was drier. The pop-up gives the exact count.",
         "Districts that fall in the same 9 km grid cell have identical values (six Accra districts, for example), so they move together and tie in the ranking."],
  vegetation: ["A district is rated only when enough pixels are usable and at least five other years exist for that month. Districts that fail only the second test are shown as “Not enough years”, not “Too cloudy”.",
               "The share of districts not rated is much higher in the rainy months, especially in the southern forest and cocoa belt. The pop-up shows how many years each normal rests on."],
  firerisk: ["Most of the pattern on this map is the usual seasonal pattern, and the model adds only a small improvement on it. Use “Compared with usual” to see where the estimate is above or below a district's normal chance for the date.",
             "“Usual chance” is the district's usual chance of at least one detection on these dates, estimated from other years. Dots mark districts where a detection did occur, not fire locations.",
             "Periods start on the 3rd, 8th, 13th, 18th, 23rd and 28th and last five days, so the 2nd of a 31-day month falls in no period and the last February period overlaps the first of March. The latest period runs to the day of the update, so what happened in it is partly unknown."],
  forest: ["The ranking by percent favours districts with little forest: choose “Hectares lost a year” to see where the largest areas are being lost.",
           "Percentages are not shown for districts with under 100 ha of tree cover in 2000, because a few hectares make a large percentage.",
           "The map shows a three-year average. National loss has been higher in some earlier years, and detection improved over time, so compare years with care."],
  floodprone: ["How often a place is imaged changes how much flooding is found: a place imaged twice as often has twice the chances to be caught flooded. The panel shows the radar images read a year for each district. Sentinel-1B stopped working in December 2021, so image frequency changed during the record.",
               "“None detected” does not mean there was no flooding. Radar cannot see flooding under forest or between buildings, so districts in the southern forest belt and Greater Accra show “none detected” whatever happens on the ground.",
               "Districts with lake-shore land set apart (dashed outline) can have more flooding than the colour shows, because that land is not counted in it. The panel gives the lake-shore area."],
  floodhazard: ["Districts marked † (dashed outline) are on the Volta delta below the Akosombo dam. The model has the river flooding most of that land even in a 1-in-10-year flood, so their high shares show what the river could do without the dam, not what usually happens."],
  water: ["The dark blue class mixes new reservoirs (such as Bui), the recovery of Lake Volta from its 1983 low, and water-filled mining pits. Look at the percent view to see change relative to each district's water at the start.",
          "The “first years” are the first clear images of each place, which differ from place to place and are often much later than 1984."],
  cropland: ["The map shows open-field cropland only. Tree crops (cocoa, oil palm, cashew), mixed farming under trees and fallow land are mostly not captured, so forest-zone districts can read as having almost no farmland. Districts with much tree cover and little mapped cropland have a dashed outline.",
             "Compare this tab with Main crops and Human modification: in many forest-zone districts those tabs show farming as the main use of the land."],
  crops: ["The main crop is usually a weak plurality: in most districts it is under 40% of the crop area. Pale colours mark districts where the main crop has under 30% of the area, strong colours where it has half or more. Open a district to see the crop mix.",
          "29 districts are smaller than one 10 km grid cell. Their crops are those of the surrounding cells, and districts with under 100 ha of mapped crops are shown as “negligible”."],
  pressure: ["In many forest-zone districts agriculture is the largest human pressure here even though the Cropland tab shows very little cropland there, because tree crops and mixed farming are not captured as cropland."],
  pressurechange: ["The change is strongly related to the 2020 level (change is largest where modification was already high), so this map partly repeats the level map. The relative change view removes some of that."],
  urban: ["In fully built-up districts such as central Accra a 1 km grid cannot show new building inside cells that were already built, so growth can read as zero even where human modification rose.",
          "The darkest percent class mixes villages that grew from a few buildings with cities that added many square kilometres. Choose “Square kilometres added” to see where most building happened."],
  biodiversity: ["The map follows recording effort: districts with many records show many species. Districts with under 100 records are shown separately as “too few records to judge”.",
                 "Most species in most districts were recorded once or twice, so counts are a rough picture of what is there. Red List counts also depend on effort, and the categories are global, not Ghana's."],
};
TL.extralimits.flood = TL.extralimits.flood2020 = [];

// ---- a second figure to colour and rank by -----------------------------------------------------
// entry 0 is the map as published; the others have a value for each district (from the pop-up rows), class breaks and colours
const _ramp = { red: ["#fff3c4", "#fdc777", "#f58b3f", "#d6402b", "#8e0f26"], purple: ["#f1eee6", "#bfd3e6", "#8c96c6", "#88419d", "#4d004b"],
                blue: ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"], brown: ["#f4efe1", "#e5d6a0", "#c9b15a", "#97832d", "#5e5114"],
                orange: ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"], div: ["#8c510a", "#d8b365", "#f1eee6", "#9ecae1", "#084594"] };
const _cl = (labels, colors) => labels.map((label, i) => ({ label, color: colors[i] }));
TL.measures = {
  forest: [{ label: "Rate (share of year-2000 cover lost a year)" },
    { label: "Hectares lost a year", breaks: [50, 200, 500, 1500], classes: _cl(["Under 50 ha", "50 to 200 ha", "200 to 500 ha", "500 to 1,500 ha", "Over 1,500 ha"], _ramp.red),
      val: x => { const r = (x.rows || [])[1]; if (!r) return null; const v = TL.n(r[1]); return /^Lost \d{4}.\d{4}$/.test(r[0]) ? v / 3 : v; },
      fmt: v => TL.fmt(v) + " ha", note: "hectares of tree cover lost a year (average over the period shown)", unit: "ha" }],
  urban: [{ label: "Percent growth" },
    { label: "Square kilometres added", breaks: [0.5, 2, 5, 10], classes: _cl(["Under 0.5 km²", "0.5 to 2 km²", "2 to 5 km²", "5 to 10 km²", "Over 10 km²"], _ramp.red),
      val: x => TL.n(TL.row(x, /^Added/)), fmt: v => TL.fmt(v, 1) + " km²", note: "of built-up area added", none: "No value" },
    { label: "Share of the district built on (latest date)", breaks: [1, 5, 15, 35], classes: _cl(["Under 1%", "1 to 5%", "5 to 15%", "15 to 35%", "Over 35%"], _ramp.red),
      val: x => TL.n(TL.row(x, /^Share of district built/)), fmt: v => TL.fmt(v, 1) + "%", note: "of the district's land is built on at the latest date" }],
  floodprone: [{ label: "Flooded area (km²)" },
    { label: "Share of the district's land", breaks: [0.1, 0.5, 1, 3], classes: _cl(["Under 0.1%", "0.1 to 0.5%", "0.5 to 1%", "1 to 3%", "Over 3%"], _ramp.purple),
      val: x => TL.n(TL.row(x, /^Share of the district/)), fmt: v => TL.fmt(v, 1) + "%", note: "of the district's land seen flooded in at least 2 of the years", none: "Not assessed" }],
  floodhazard: [{ label: "Share of the district's land" },
    { label: "Land inside the flood zone (km²)", breaks: [1, 10, 50, 200], classes: _cl(["Under 1 km²", "1 to 10 km²", "10 to 50 km²", "50 to 200 km²", "Over 200 km²"], _ramp.orange),
      val: x => TL.n0(TL.row(x, /^Land inside that flood zone/)), fmt: v => TL.fmt(v, 1) + " km²", note: "of land inside the modelled flood zone" },
    { label: "People inside the flood zone (2020 estimate)", breaks: [1000, 10000, 50000, 100000], classes: _cl(["Under 1,000", "1,000 to 10,000", "10,000 to 50,000", "50,000 to 100,000", "Over 100,000"], _ramp.orange),
      val: x => { const t = TL.row(x, /^People living inside/); return t == null ? null : /fewer than/.test(t) ? 0 : TL.n(t); }, fmt: v => TL.fmt(v), note: "people living inside the modelled flood zone (rounded estimate)", none: "Not reported" }],
  water: [{ label: "Net change (km²)" },
    { label: "Percent of earlier water", breaks: [-25, -5, 5, 25], classes: _cl(["Lost over 25%", "Lost 5 to 25%", "Little change (within 5%)", "Gained 5 to 25%", "Gained over 25%"], _ramp.div),
      val: x => { const a = TL.n(TL.row(x, /first years/)), b = TL.n(TL.row(x, /^Permanent water, \d{4}$/)); return a >= 1 ? (b - a) / a * 100 : null; },
      fmt: v => (v > 0 ? "+" : "") + TL.fmt(v, 0) + "%", note: "change in permanent water, as a share of the water there at the start", none: "Under 1 km² of water at the start" }],
  cropland: [{ label: "Share of the district's land" },
    { label: "Area (km²)", breaks: [10, 50, 200, 500], classes: _cl(["Under 10 km²", "10 to 50 km²", "50 to 200 km²", "200 to 500 km²", "Over 500 km²"], _ramp.brown),
      val: x => TL.n(TL.row(x, /^Cropland \(2021\)/)), fmt: v => TL.fmt(v, 1) + " km²", note: "of open-field cropland (2021)" }],
  pressurechange: [{ label: "Change (index points)" },
    { label: "Relative change (% of the 1990 value)", breaks: [2, 5, 10, 20], classes: _cl(["Under 2%", "2 to 5%", "5 to 10%", "10 to 20%", "Over 20%"], ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"]),
      val: x => { const r = TL.row(x, /^Change since/); const c = TL.n(r), f = /from\s+([\d.]+)/.exec(r || ""); return f && +f[1] > 0 ? c / +f[1] * 100 : null; },
      fmt: v => (v > 0 ? "+" : "") + TL.fmt(v, 0) + "%", note: "change in the index since the first date, relative to its starting value" }],
  biodiversity: [{ label: "Species recorded" },
    { label: "Recording effort (records)", breaks: [100, 500, 2000, 10000], classes: _cl(["Under 100", "100 to 500", "500 to 2,000", "2,000 to 10,000", "Over 10,000"], _ramp.orange),
      val: x => x.records != null ? x.records : TL.n(TL.row(x, /^Occurrence records/)), fmt: v => TL.fmt(v), note: "records in GBIF: a measure of how much the district has been surveyed" },
    { label: "Records per species (confidence)", breaks: [1.5, 2.5, 4, 8], classes: _cl(["Under 1.5", "1.5 to 2.5", "2.5 to 4", "4 to 8", "Over 8"], _ramp.blue),
      val: x => TL.n(TL.row(x, /^Records per species/)), fmt: v => TL.fmt(v, 1), note: "records per species: low values mean most species were seen only once or twice" }],
};

// ---- put districts into fifths of a value, using the value as displayed so equal numbers share a class ----
TL.refifths = (d, keys, val, unit, dec) => {
  const E = Object.entries(d.districts).map(([id, x]) => [id, val(x)]).filter(([, v]) => v != null && isFinite(v));
  if (E.length < 50) return d;
  const sorted = E.map(e => e[1]).sort((a, b) => a - b);
  const q = p => { const i = (sorted.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i); return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo); };
  const cuts = [0.2, 0.4, 0.6, 0.8].map(q), cls = v => cuts.filter(c => v >= c).length;
  const districts = { ...d.districts }, lo = [], hi = [];
  E.forEach(([id, v]) => { const k = cls(v); districts[id] = { ...districts[id], cat: keys[k] }; lo[k] = lo[k] === undefined ? v : Math.min(lo[k], v); hi[k] = hi[k] === undefined ? v : Math.max(hi[k], v); });
  const f = v => TL.fmt(v, dec), counts = {};
  Object.values(districts).forEach(x => counts[x.cat] = (counts[x.cat] || 0) + 1);
  const categories = d.categories.map(c => { const k = keys.indexOf(c.key); return k < 0 || lo[k] === undefined ? c : { ...c, note: (lo[k] === hi[k] ? f(lo[k]) : `${f(lo[k])} to ${f(hi[k])}`) + (unit ? " " + unit : "") }; });
  return { ...d, districts, counts, categories };
};

// ---- per-layer changes made every time the map is drawn ----------------------------------------
TL.post = {
  forest: d => {                          // no percentage where there is hardly any forest to lose it from
    const districts = {};
    for (const [id, x] of Object.entries(d.districts)) {
      const tc = x.tc ?? TL.n(TL.row(x, /^Tree cover in 2000/));
      if (x.cat !== "low" && tc != null && tc < TL.minForestHa) {
        districts[id] = { ...x, cat: "low", big: "–", tip: "Under 100 ha of tree cover",
          big_note: `Under ${TL.minForestHa} ha of tree cover in 2000, so a percentage is not meaningful.`,
          rows: (x.rows || []).map(r => [r[0], String(r[1]).replace(/\s*\(\d+%\)$/, "")]) };
      } else districts[id] = x;
    }
    const counts = {}; Object.values(districts).forEach(x => counts[x.cat] = (counts[x.cat] || 0) + 1);
    return { ...d, districts, counts, categories: d.categories.map(c => c.key === "low" ? { ...c, label: "Not rated", note: "under 5% cover, or under 100 ha" } : c) };
  },
  floodprone: d => {
    const n = (d.chart && d.chart.x ? d.chart.x.length : 0) || 9, districts = {};
    for (const [id, x] of Object.entries(d.districts)) {
      if (x.cat === "out") { districts[id] = x; continue; }
      const imgs = TL.n(TL.row(x, /^Radar images read/)), shore = TL.n0(TL.row(x, /^Along Lake Volta/));
      const rows = (x.rows || []).map(r => /^Largest flooded area in one year/.test(r[0]) && r[1] === "–" ? [r[0], "None detected"] : r);
      if (imgs) rows.push(["Radar images a year (average)", TL.fmt(imgs / n)]);
      const none = x.cat === "p0";
      districts[id] = { ...x, rows, ol: shore >= 1 ? 1 : 0, big: x.big === "None" ? "None detected" : x.big,
        big_note: none ? "of land seen flooded. “None detected” is not “no flooding”: radar misses flooding under forest and between buildings." : x.big_note };
    }
    return { ...d, districts, outline_label: "Dashed outline: 1 km² or more of lake-shore land is set apart and not counted in the colours" };
  },
  floodhazard: d => {
    const districts = {}, counts = {};
    const built = d.categories.some(c => c.key === "h0" && /^Under 0\.1%/.test(c.label));          // newer data files already carry the "Under 0.1%" class
    for (const [id, x] of Object.entries(d.districts)) {
      const area = TL.n0(TL.row(x, /^Land inside that flood zone/)), r10 = TL.n0(TL.row(x, /^In a 1-in-10-year/)), pct = TL.n(x.big);
      let cat = x.cat, flag = "";
      if (!built && x.cat === "h0" && area > 0) cat = "small";                                         // a little land is inside the zone: not "None"
      if (pct >= 20 && area > 0 && r10 >= 0.85 * area) flag = "†";                           // the Volta delta: the zone is as large in a 1-in-10 flood as in a 1-in-100 flood
      districts[id] = { ...x, cat, flag, ol: flag ? 1 : 0, rows: flag ? (x.rows || []).concat([["Dam caveat", "Modelled without the Akosombo dam's control"]]) : x.rows };
      counts[cat] = (counts[cat] || 0) + 1;
    }
    const cats = d.categories.slice();
    if (counts.small) cats.splice(1, 0, { key: "small", label: "Under 0.1%", note: "of the land", color: "#f9ecd0" });
    return { ...d, districts, counts, categories: cats, flag_note: "† Volta delta below the Akosombo dam: modelled as if the dam did not control the river, so the 1-in-10-year zone is nearly as large as the 1-in-100-year zone.",
             outline_label: "Dashed outline: Volta delta districts, modelled without the Akosombo dam's control" };
  },
  cropland: d => {                         // districts with much tree cover and little mapped cropland get a dashed outline (see TL.pre)
    return d.forestzone ? { ...d, districts: Object.fromEntries(Object.entries(d.districts).map(([id, x]) => [id, d.forestzone[id] ? { ...x, ol: 1 } : x])),
      outline_label: "Dashed outline: much tree cover and little mapped cropland. Tree crops and mixed farming are mostly not captured here" } : d;
  },
  pressure: d => TL.refifths(d, ["q1", "q2", "q3", "q4", "q5"], x => TL.n(x.big), "", 2),
  pressurechange: d => {                   // fixed classes instead of fifths: most districts changed very little
    const cl = [["Under 0.05", "#f2f0f7", v => v < 0.05], ["0.05 to under 0.10", "#cbc9e2", v => v < 0.10], ["0.10 to under 0.20", "#9e9ac8", v => v < 0.20], ["0.20 or more", "#54278f", () => true]];
    const districts = {}, counts = {};
    for (const [id, x] of Object.entries(d.districts)) {
      const v = TL.n(x.big), k = v == null ? -1 : cl.findIndex(c => c[2](v)), cat = "f" + k;
      districts[id] = { ...x, cat: v == null ? x.cat : cat }; counts[districts[id].cat] = (counts[districts[id].cat] || 0) + 1;
    }
    return { ...d, districts, counts, categories: cl.map((c, i) => ({ key: "f" + i, label: c[0], note: i === 0 ? "within the source's error" : "", color: c[1] })) };
  },
  urban: d => d,
  biodiversity: d => {                     // too few records to say anything about richness
    const few = {}, districts = {};
    for (const [id, x] of Object.entries(d.districts)) {
      const rec = x.records != null ? x.records : TL.n(TL.row(x, /^Occurrence records/));
      if (rec != null && rec < 100) { districts[id] = { ...x, cat: "few", tip: x.tip + " (under 100 records)" }; few[id] = 1; } else districts[id] = x;
    }
    const counts = {}; Object.values(districts).forEach(x => counts[x.cat] = (counts[x.cat] || 0) + 1);
    return counts.few ? { ...d, districts, counts, categories: d.categories.concat([{ key: "few", label: "Too few records to judge", note: "under 100 records", color: "#d9d9d9" }]) } : d;
  },
  crops: d => {
    // merge minor classes into "Other", give the rest colours that are easy to tell apart, and shade by how strong the main crop is
    const pal = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442"], keep = [];
    d.categories.forEach(c => { if (/^k_(?!other)/.test(c.key) && (d.counts[c.key] || 0) >= 10 && keep.length < pal.length) keep.push(c.key); });
    const districts = {}, counts = {};
    for (const [id, x] of Object.entries(d.districts)) {
      let cat = x.cat;
      const total = TL.n(TL.row(x, /^All mapped crops/)), share = x.table && x.table.rows[0] ? TL.n(x.table.rows[0][2]) : null;
      if (/^k_/.test(cat) && !keep.includes(cat)) cat = "k_other";
      if (/^k_/.test(cat) && total != null && total < 100) cat = "small";
      districts[id] = { ...x, cat, op: share == null || cat === "small" ? 1 : share >= 50 ? 1 : share >= 30 ? 0.7 : 0.45,
        rows: (x.rows || []).concat(total != null && total < 100 ? [["Note", "Under 100 ha of crops mapped: not a meaningful main crop"]] : []) };
      counts[cat] = (counts[cat] || 0) + 1;
    }
    const cats = keep.map((k, i) => ({ ...d.categories.find(c => c.key === k), color: pal[i] }));
    if (counts.k_other) cats.push({ key: "k_other", label: "Other crops", note: "each leads in under 10 districts", color: "#7f7f7f" });
    if (counts.small) cats.push({ key: "small", label: "Negligible crop area", note: "under 100 ha mapped", color: "#e1e1e1" });
    cats.push(d.categories.find(c => c.key === "none") || { key: "none", label: "No estimate", note: "", color: "#bdbdbd" });
    return { ...d, districts, counts, categories: cats,
             legend_notes: ["Strong colour: the main crop has half or more of the district's crop area. Medium: 30 to 50%. Pale: under 30%."] };
  },
};
["soiln", "soilp", "soilk", "soilph", "soilom", "soilclay", "soilsand", "soilbd"].forEach(k => {
  TL.post[k] = d => {
    const keys = ["n0", "n1", "n2", "n3", "n4"], dec = (/\.(\d+)/.exec(String((Object.values(d.districts).find(x => /\d/.test(x.big)) || {}).big)) || [, ""])[1].length;
    const r = TL.refifths(d, keys, x => x.v && x.v[0] != null ? +(+x.v[0]).toFixed(dec) : null, (d.chart && d.chart.unit) || "", dec);
    return { ...r, categories: r.categories.map(c => TL.soilRamp[c.key] ? { ...c, color: TL.soilRamp[c.key] } : c) };
  };
});

// ---- run once when a layer is loaded ----------------------------------------------------------
TL.pre = {
  cropland: d => getJSON("data/forest.json").then(f => {
    const zone = {};
    for (const [id, x] of Object.entries(d.districts)) {
      const fx = f.districts && f.districts[id], pct = TL.n(x.big);
      const tc = fx ? (fx.tc ?? TL.n(TL.row(fx, /^Tree cover in 2000/))) : null;
      if (tc != null && tc >= 20000 && pct != null && pct < 1) zone[id] = 1;
    }
    return { ...d, forestzone: zone };
  }).catch(() => d),
};
