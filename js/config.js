// Tinga Lens - site settings: navigation, modules and the product register.
// Every product is one of three kinds, and the site labels each one:
//   observed  = what a satellite recorded
//   condition = an observation compared with what is normal for the place and season
//   model     = a statistical estimate made by Tinga Lens
const TL = {
  name: "Tinga Lens",
  tagline: "See Ghana's environment changing.",
  site: "https://tinga-lens.github.io",
  repo: "https://github.com/tinga-lens/tinga-lens.github.io",
  nav: [
    ["Home", ""], ["Drought", "pages/drought.html"], ["Fire", "pages/fire.html"],
    ["Vegetation & Forest", "pages/vegetation.html"], ["Flood", "pages/flood.html"],
    ["Urban Exposure", "pages/urban.html"], ["Districts", "pages/districts.html"],
    ["Data & Methods", "pages/methods.html"], ["About", "pages/about.html"],
  ],
  status: {
    observed: { label: "Observed", text: "What a satellite recorded." },
    condition: { label: "Environmental condition", text: "An observation compared with what is normal for that place and time of year." },
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
  },
  // modules that are planned but have no data yet; the site shows no numbers for them
  planned: {
    flood: { name: "Flood", page: "pages/flood.html" },
    urban: { name: "Urban Exposure", page: "pages/urban.html" },
  },
  disclaimer: "Tinga Lens provides research and environmental information derived from satellite, climate and geospatial datasets. Products may contain measurement, model and classification uncertainties. Tinga Lens should not be used as the sole source for emergency response, evacuation, disaster management or other safety-critical decisions. Consult the relevant Ghanaian authorities for official warnings and emergency information.",
};
