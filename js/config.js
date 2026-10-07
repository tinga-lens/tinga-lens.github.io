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
    soilprops: { tab: "Soil nutrients", label: "Nutrient" },
  },
  status: {
    observed: { label: "Observed", text: "What a satellite recorded." },
    index: { label: "Published index", text: "A combined index published by another research group, averaged here by district." },
    condition: { label: "Environmental condition", text: "An observation compared with what is normal for that place and time of year." },
    pubmodel: { label: "Published model", text: "A model result published by another research group, added up here by district. It is not an observation." },
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
    fires: { name: "Active fire detections", tab: "Observed fire", module: "Fire", page: "pages/fire.html", status: "observed", version: "1.1",
             source: "NASA FIRMS, VIIRS (S-NPP) 375 m active fires", type: "Satellite observation",
             resolution: "375 m detections, summed by district", updates: "Weekly", baseline: "2012 onwards" },
    firerisk: { name: "Fire probability", tab: "Fire probability", module: "Fire", page: "pages/fire.html", status: "model", version: "0.2 (experimental)",
                source: "Tinga Lens logistic regression on SMAP, FIRMS, CHIRPS and VIIRS data", type: "Statistical model",
                resolution: "District, five-day periods", updates: "Weekly", baseline: "Fitted to 2015 onwards" },
    vegetation: { name: "Vegetation greenness anomaly", tab: "Vegetation condition", module: "Vegetation & Forest", page: "pages/vegetation.html", status: "condition", version: "1.1",
                  source: "NASA VIIRS vegetation index (VNP13A3), LP DAAC", type: "Satellite observation",
                  resolution: "1 km", updates: "Monthly", baseline: "2012 onwards" },
    forest: { name: "Tree cover loss", tab: "Forest change", module: "Vegetation & Forest", page: "pages/vegetation.html", status: "observed", version: "1.1",
              source: "Global Forest Change (Hansen/UMD/Google/USGS/NASA), Landsat", type: "Derived from satellite images",
              resolution: "30 m, summed by district", updates: "Yearly", baseline: "Tree cover in 2000" },
    floodprone: { name: "Flood-prone land", tab: "Flood-prone land", module: "Flood", page: "pages/flood.html", status: "observed", version: "0.2 (experimental)",
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
    cropland: { name: "Cropland", tab: "Cropland", module: "Agriculture", page: "pages/agriculture.html", status: "observed", version: "0.1",
          source: "ESA WorldCover 10 m v200 (2021)", type: "Derived from satellite images",
          resolution: "10 m, summed by district", updates: "With each new release of the sources", baseline: "Land seen as cropland in 2021" },
    crops: { name: "Main crop in each district", tab: "Main crops", module: "Agriculture", group: "crops", option: "Main crop in each district", page: "pages/agriculture.html", status: "pubmodel", version: "0.1",
             source: "SPAM 2020, International Food Policy Research Institute and partners", type: "Published model, added up by district",
             resolution: "10 km grid, shared between districts by area", updates: "With each new release of the source", baseline: "A typical year around 2020" },
    soiln: { name: "Soil nitrogen", tab: "Nitrogen", module: "Agriculture", group: "soilprops", option: "Nitrogen", page: "pages/agriculture.html", status: "pubmodel", version: "0.1",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland from ESA WorldCover 2021", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilp: { name: "Soil phosphorus", tab: "Phosphorus", module: "Agriculture", group: "soilprops", option: "Phosphorus", page: "pages/agriculture.html", status: "pubmodel", version: "0.1",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland from ESA WorldCover 2021", type: "Published model, averaged by district",
          resolution: "30 m, averaged by district", updates: "With each new release of the sources", baseline: "Ranked among Ghana's districts" },
    soilk: { name: "Soil potassium", tab: "Potassium", module: "Agriculture", group: "soilprops", option: "Potassium", page: "pages/agriculture.html", status: "pubmodel", version: "0.1",
          source: "iSDAsoil Africa v1 (Hengl and others, 2021), cropland from ESA WorldCover 2021", type: "Published model, averaged by district",
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
    biodiversity: { name: "Recorded species", tab: "Recorded species", module: "Biodiversity", page: "pages/biodiversity.html", status: "observed", version: "0.1",
                    source: "GBIF occurrence records (CC0 and CC BY), with IUCN Red List categories", type: "Field observations and museum specimens",
                    resolution: "Individual records, counted by district", updates: "Monthly", baseline: "All years on record" },
  },
  // modules that are planned but have no data yet; the site shows no numbers for them
  planned: {
  },
  disclaimer: "Tinga Lens provides research and environmental information derived from satellite, climate and geospatial datasets. Products may contain measurement, model and classification uncertainties. Tinga Lens should not be used as the sole source for emergency response, evacuation, disaster management or other safety-critical decisions. Consult the relevant Ghanaian authorities for official warnings and emergency information.",
};

// one layer for each main crop (built by scripts/crops.py)
[["maiz", "Maize"], ["cass", "Cassava"], ["yams", "Yam"], ["rice", "Rice"], ["plnt", "Plantain"], ["coco", "Cocoa"], ["sorg", "Sorghum"], ["pmil", "Pearl millet"], ["grou", "Groundnut"]].forEach(([c, n]) => {
  TL.products["crop_" + c] = { name: n + ": estimated crop area", tab: n, module: "Agriculture", group: "crops", option: n, page: "pages/agriculture.html", status: "pubmodel", version: "0.1",
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
