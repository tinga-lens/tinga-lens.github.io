// Tinga Lens - the map application. Used on the home page (all layers) and on each module page (its own layers).
// A page chooses its layers with <html data-layers="drought,soil">; with no list, every layer is shown.
document.getElementById("app").innerHTML = `<nav class="mods" aria-label="Modules" id="mods" hidden></nav>
  <nav class="tabs" aria-label="Layers" id="tabs"></nav>
  <div class="grp" id="grpwrap" hidden><label for="grp" id="grplab"></label><select class="big" id="grp"></select></div>
  <div id="demo"><strong>Demo data.</strong> These numbers are made up to preview the site. They are replaced with real data the first time the update runs.</div>

  <div class="grid">
    <div class="mapcol">
      <div id="map" role="application" aria-label="Map of Ghana districts"></div>
      <section class="notes">
        <h2>How to read this map</h2>
        <p id="how"></p>
        <h2>Limits</h2>
        <ul id="limits"></ul>
        <div id="tables"></div>
      </section>
    </div>
    <aside>
      <div class="card">
        <div id="status" style="margin-bottom:4px"></div>
        <h2 id="title">Loading…</h2>
        <p class="sub" id="subtitle"></p>
        <div class="ctl">
          <label>Region <select id="region"><option value="">All of Ghana</option></select></label>
        </div>
        <div id="time" hidden>
          <div class="ctl">
            <label>Year <select id="yr"></select></label>
            <label id="mo-wrap">Month <select id="mo"></select></label>
            <label id="dy-wrap" hidden>Day <select id="dy"></select></label>
            <button class="btn" id="latest" type="button">Latest</button>
          </div>
          <div class="seg" id="mapmode" role="group" aria-label="What the map shows" hidden>
            <button type="button" id="mm-est" aria-pressed="true">Estimated chance</button><button type="button" id="mm-hap" aria-pressed="false">What happened</button>
          </div>
          <p class="sub" id="time-note"></p>
        </div>
        <div id="points-ctl" hidden>
          <div class="seg" role="group" aria-label="Individual fire detections">
            <button type="button" data-days="0" aria-pressed="true">Districts only</button><button type="button" data-days="1" aria-pressed="false">Latest day</button><button type="button" data-days="3" aria-pressed="false">3 days</button><button type="button" data-days="7" aria-pressed="false">7 days</button>
          </div>
          <p class="sub" id="points-note"></p>
        </div>
        <div class="bar" id="bar"></div>
        <ul class="legend" id="legend"></ul>
        <div class="btns">
          <button class="btn" id="download-img" type="button">Download map image (PNG)</button>
          <button class="btn" id="download" type="button">Download this map (CSV)</button>
          <button class="btn" id="download-all" type="button" hidden>Download full record (CSV)</button>
        </div>
        <p class="sub" style="margin:12px 0 4px"><strong>Cite this map</strong></p>
        <p class="sub cite" id="cite"></p>
        <button class="btn" id="cite-copy" type="button">Copy citation</button>
      </div>
      <div class="card">
        <input type="search" id="search" name="tl-district" autocomplete="off" autocorrect="off" spellcheck="false" list="names" placeholder="Find a district…" aria-label="Find a district">
        <datalist id="names"></datalist>
        <div id="detail"></div>
      </div>
      <div class="card">
        <h2>Ranking</h2>
        <p class="sub" style="margin-bottom:8px">Districts by their main figure on this map. Unrated districts are left out.</p>
        <div class="seg" role="group" aria-label="Ranking order">
          <button type="button" id="rk-hi" aria-pressed="true">Highest 10</button><button type="button" id="rk-lo" aria-pressed="false">Lowest 10</button>
        </div>
        <ol class="rank" id="rank"></ol>
      </div>
    </aside>
  </div>`;

const EMPTY = '<p class="sub" style="margin:0">Click a district on the map, or search for one, to see its numbers.</p>';

const map = L.map("map", { zoomSnap: 0.25, attributionControl: false });
const street = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 17, maxNativeZoom: 17, opacity: 0.35 }).addTo(map);
// satellite picture: Esri World Imagery (detailed enough to see streets and fields), with place names on top
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/";
const sat = L.layerGroup([
  L.tileLayer(ESRI + "World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 17, maxNativeZoom: 17 }),
  L.tileLayer(ESRI + "Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 17, maxNativeZoom: 17, pane: "shadowPane" }),
]);
let SAT = false, FILL = 1;             // FILL: how solid the district colours are
const view = L.control({ position: "topright" });
view.onAdd = () => {
  const box = L.DomUtil.create("div", "mapctl");
  box.innerHTML = `<div class="seg" style="margin:0"><button type="button" id="bm-map" aria-pressed="true">Map</button><button type="button" id="bm-sat" aria-pressed="false">Satellite</button></div>
    <label id="fill-wrap" hidden>Colours <input type="range" id="fill" min="0" max="100" value="25" aria-label="How solid the district colours are"></label>
    <div class="satnote" id="sat-note" hidden>Imagery and place names: Esri, Maxar, Earthstar Geographics and the GIS User Community. Zoom in to see towns and forest.</div>`;
  L.DomEvent.disableClickPropagation(box); L.DomEvent.disableScrollPropagation(box);
  return box;
};
view.addTo(map);
function basemap(on) {
  SAT = on;
  if (on) { map.removeLayer(street); sat.addTo(map); } else { map.removeLayer(sat); street.addTo(map); }
  $("bm-map").setAttribute("aria-pressed", !on); $("bm-sat").setAttribute("aria-pressed", on);
  $("fill-wrap").hidden = $("sat-note").hidden = !on;
  FILL = on ? $("fill").value / 100 : 1;
  if (FULL) render(FULL.key, FULL);
}
$("bm-map").addEventListener("click", () => basemap(false));
$("bm-sat").addEventListener("click", () => basemap(true));
$("fill").addEventListener("input", () => basemap(true));
const dots = L.layerGroup().addTo(map);      // dots on districts where a fire was detected

let geoLayer, shapes = {}, selected = null, D = null, color = {}, label = {}, cache = {}, rankHigh = true;
// BASE = the latest map as published; REC = the layer's full record (if it has one); VIEW = period shown ("" = latest map)
let BASE = null, REC = null, DAYS = null, VIEW = "", recCache = {}, daysCache = {};
let POINTS = null, pointDays = 0;            // individual fire detections (last few days), if published
const pts = L.layerGroup().addTo(map), canvas = L.canvas({ padding: 0.5 });
let MODE = "estimate";                       // fire risk map: "estimate" or "happened"
let REGION = "", REGIONS = {}, FULL = null;  // chosen region, district -> region, and the whole-country view being shown
const inRegion = id => !REGION || REGIONS[id] === REGION;
function regionBounds() {
  if (!REGION) return geoLayer.getBounds();
  let b = null;
  Object.entries(shapes).forEach(([id, l]) => { if (inRegion(id)) b = b ? b.extend(l.getBounds()) : L.latLngBounds(l.getBounds().getSouthWest(), l.getBounds().getNorthEast()); });
  return b || geoLayer.getBounds();
}

let CEN = {};       // district centre points, [latitude, longitude], added to every CSV
getJSON("data/centroids.json").then(c => { CEN = c; }).catch(() => {});
const LL = ["District centre latitude", "District centre longitude"], ll = id => CEN[id] || ["", ""];
Promise.all([getJSON("data/districts.geojson"), getJSON("data/layers.json")]).then(([geo, man]) => {
  geoLayer = L.geoJSON(geo, {
    style: { fillColor: "#999", fillOpacity: 0.9, color: "#55605c", weight: 0.6 },
    onEachFeature: (f, l) => {
      shapes[f.properties.shapeID] = l;
      l.bindTooltip(() => tip(f.properties), { sticky: true });
      l.on("click", () => select(f.properties.shapeID));
    },
  }).addTo(map);
  map.fitBounds(geoLayer.getBounds(), { padding: [8, 8] });
  getJSON("data/regions.json").then(r => {
    REGIONS = r;
    $("region").innerHTML += [...new Set(Object.values(r))].sort().map(n => `<option>${esc(n)}</option>`).join("");
  }).catch(() => { $("region").closest(".ctl").hidden = true; });
  $("region").addEventListener("change", e => {
    REGION = e.target.value; selected = null;
    document.dispatchEvent(new CustomEvent("tl:region", { detail: { region: REGION } }));
    map.fitBounds(regionBounds(), { padding: [12, 12] });
    if (FULL) render(FULL.key, FULL);
  });
  map.setMaxBounds(geoLayer.getBounds().pad(0.6));
  map.setMinZoom(map.getZoom() - 0.5);

  const only = (document.documentElement.dataset.layers || "").split(",").filter(Boolean);
  if (only.length) man = { layers: only.map(k => man.layers.find(l => l.key === k)).filter(Boolean), planned: [] };
  if (!man.layers.length) { $("title").textContent = "No data for this page yet"; return; }
  const tabName = l => only.length && TL.products[l.key] ? TL.products[l.key].tab : l.label;
  // On the home page the layers are grouped: pick a module, then one of its layers.
  const grouped = !only.length, modOf = k => (TL.products[k] || {}).module || "Other";
  const order = Object.keys(TL.products), rank = k => (order.indexOf(k) + 1) || 99;       // modules and layers in the order of the product register
  if (grouped) man.layers.sort((a, b) => rank(a.key) - rank(b.key));
  const mods = [...new Set(man.layers.map(l => modOf(l.key)))];
  const grp = k => (TL.products[k] || {}).group || null, lastIn = {};
  const drawTabs = key => {
    const list = grouped ? man.layers.filter(l => modOf(l.key) === modOf(key)) : man.layers;
    const seen = new Set(), items = [];       // layers that share a group become one tab with a list under it
    list.forEach(l => {
      const g = grp(l.key);
      if (!g) return items.push({ key: l.key, text: grouped && TL.products[l.key] ? TL.products[l.key].tab : tabName(l) });
      if (seen.has(g)) return;
      seen.add(g);
      const keep = lastIn[g] && list.some(x => x.key === lastIn[g]) ? lastIn[g] : l.key;
      items.push({ key: keep, group: g, text: TL.groups[g].tab });
    });
    $("tabs").innerHTML = items.map(i => `<button data-key="${esc(i.key)}"${i.group ? ` data-group="${esc(i.group)}"` : ""}>${esc(i.text)}</button>`).join("");
    $("tabs").hidden = items.length < 2;
    const g = grp(key);
    $("grpwrap").hidden = !g;
    if (g) {
      lastIn[g] = key;
      $("grplab").textContent = TL.groups[g].label;
      $("grp").innerHTML = list.filter(l => grp(l.key) === g).map(l => `<option value="${esc(l.key)}">${esc(TL.products[l.key].option || TL.products[l.key].tab)}</option>`).join("");
      $("grp").value = key;
    }
    if (grouped) { $("mods").hidden = false; $("mods").innerHTML = mods.map(m => `<button data-mod="${esc(m)}" aria-current="${m === modOf(key)}">${esc(m)}</button>`).join(""); }
  };
  $("grp").addEventListener("change", e => show(e.target.value));
  $("tabs").addEventListener("click", e => { const k = e.target.closest("button")?.dataset.key; if (k) show(k); });
  $("mods").addEventListener("click", e => { const m = e.target.closest("button")?.dataset.mod; if (m) show(man.layers.find(l => modOf(l.key) === m).key); });
  const show = key => {
    const l = man.layers.find(x => x.key === key) || man.layers[0];
    drawTabs(l.key);
    document.dispatchEvent(new CustomEvent("tl:layer", { detail: { key: l.key } }));
    (cache[l.key] ? Promise.resolve(cache[l.key]) : getJSON(l.file).then(d => cache[l.key] = d)).then(d => {
      BASE = d; REC = null; VIEW = ""; DAYS = daysCache[l.key] || null;
      const yearly = d.yearly || (d.key === "forest" ? { base_label: "Latest average", breaks: [0.5, 1, 2, 3] } : null);
      if (yearly && d.chart && d.chart.kind === "bars") { REC = { kind: "yearly", years: d.chart.x, ...yearly }; return go(latestKey()); }
      if (!d.history) return render(l.key, d);
      (recCache[l.key] ? Promise.resolve(recCache[l.key]) : getJSON(d.history).then(h => recCache[l.key] = h))
        .then(h => { REC = { kind: "anomaly", ...h }; go(latestKey()); })
        .catch(() => { REC = null; render(l.key, d); });      // no record available: show the latest map only
    });
  };
  $("search").addEventListener("change", e => {
    const q = e.target.value.trim().toLowerCase();
    const id = Object.keys(D.districts).find(k => D.districts[k].name.toLowerCase() === q);
    if (id) focusOn(id);
  });
  $("rk-hi").addEventListener("click", () => { rankHigh = true; ranking(); });
  $("rk-lo").addEventListener("click", () => { rankHigh = false; ranking(); });
  $("rank").addEventListener("click", e => { const id = e.target.closest("li")?.dataset.id; if (id) focusOn(id); });
  $("download").addEventListener("click", download);
  $("download-img").addEventListener("click", downloadImage);
  $("cite-copy").addEventListener("click", () => {
    const done = () => { $("cite-copy").textContent = "Copied"; setTimeout(() => $("cite-copy").textContent = "Copy citation", 1500); };
    (navigator.clipboard ? navigator.clipboard.writeText($("cite").textContent) : Promise.reject()).then(done).catch(() => {
      const r = document.createRange(); r.selectNodeContents($("cite")); const s = getSelection(); s.removeAllRanges(); s.addRange(r);   // select it so it can be copied by hand
    });
  });
  $("download-all").addEventListener("click", downloadAll);
  $("points-ctl").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { pointDays = +b.dataset.days; drawPoints(); } });
  getJSON("data/fire_points.json").then(x => { POINTS = x; if (D) drawPoints(); }).catch(() => {});
  $("yr").addEventListener("change", pick);
  $("mo").addEventListener("change", pick);
  $("dy").addEventListener("change", pick);
  $("latest").addEventListener("click", () => go(latestKey()));
  $("mm-est").addEventListener("click", () => { MODE = "estimate"; go(VIEW); });
  $("mm-hap").addEventListener("click", () => { MODE = "happened"; go(VIEW); });
  show(location.hash.slice(1));
}).catch(e => { $("title").textContent = "Could not load the data files"; $("subtitle").textContent = e.message; });

// individual satellite fire detections, drawn over the district map of the fires layer
function drawPoints() {
  pts.clearLayers();
  const on = !!POINTS && D && D.key === "fires" && !VIEW;
  $("points-ctl").hidden = !on;
  if (!on) return;
  document.querySelectorAll("#points-ctl button").forEach(b => b.setAttribute("aria-pressed", +b.dataset.days === pointDays));
  const F = Object.fromEntries(POINTS.fields.map((f, i) => [f, i]));
  const last = new Date(POINTS.through + "T00:00:00Z"), first = new Date(last.getTime() - (pointDays - 1) * 864e5).toISOString().slice(0, 10);
  const show = pointDays ? POINTS.points.filter(r => r[F.date] >= first) : [];
  const conf = { h: "High", n: "Nominal", l: "Low" };
  show.forEach(r => {
    L.circleMarker([r[F.lat], r[F.lon]], { renderer: canvas, radius: 3, color: "#7a0c0c", weight: 0.6, fillColor: "#ff5a1f", fillOpacity: 0.85 })
      .bindPopup(() => `<b>Satellite fire detection</b><br>Date: ${esc(r[F.date])}` + (r[F.time] ? `<br>Time: ${esc(r[F.time])} UTC` : "")
        + `<br>Latitude: ${r[F.lat]}<br>Longitude: ${r[F.lon]}<br>District: ${esc(r[F.district] || "–")}`
        + `<br>Confidence: ${esc(conf[String(r[F.confidence]).toLowerCase()[0]] || r[F.confidence] || "–")}`
        + (r[F.frp] !== "" && r[F.frp] != null ? `<br>Fire radiative power: ${r[F.frp]} MW` : "")
        + (r[F.daynight] ? `<br>${r[F.daynight] === "D" ? "Daytime" : "Night-time"} overpass` : "")).addTo(pts);
  });
  $("points-note").textContent = pointDays
    ? `${show.length.toLocaleString()} detection${show.length === 1 ? "" : "s"} in the ${pointDays === 1 ? "latest day" : "last " + pointDays + " days"} to ${POINTS.through}. Click a point for details.` + (POINTS.capped ? " Only the strongest detections are shown." : "")
    : `Show each satellite detection up to ${POINTS.through}.`;
}

function focusOn(id) { select(id); map.fitBounds(shapes[id].getBounds().pad(1.5)); }

function tip(p) {
  const x = D && D.districts[p.shapeID];
  return esc(p.shapeName) + (x ? "<br><b>" + esc(TL.rel(x.tip)) + "</b>" : "");
}

// =====================================================================
// Looking back: every layer with a record can show any past period.
// Record kinds:  anomaly (rainfall, soil moisture, vegetation)  count (fires)
//                yearly (forest loss)                            probability (fire risk)
// =====================================================================
const axisOf = () => REC.kind === "yearly" ? REC.years : REC.kind === "probability" ? REC.days : REC.months;
const latestKey = () => REC.base_label ? "" : axisOf()[axisOf().length - 1];

function pick() {                       // the user changed Year, Month or Day
  const y = $("yr").value;
  if (!y) return go("");
  if (REC.kind === "yearly") return go(y);
  const m = $("mo").value, d = $("dy").value;
  if (REC.kind === "probability") {
    const want = `${y}-${m}-${d}`, inMonth = REC.days.filter(k => k.startsWith(`${y}-${m}`)), inYear = REC.days.filter(k => k.startsWith(y));
    return go(REC.days.includes(want) ? want : inMonth.length ? inMonth[0] : inYear[inYear.length - 1]);
  }
  let key = `${y}-${m}`;
  if (!REC.months.includes(key)) key = REC.months.filter(k => k.startsWith(y)).pop();     // that month is missing: the year's last month
  go(key + (d && REC.days_file ? "-" + d : ""));
}

function go(key) {                      // show one period ("" = the latest map as published)
  const daily = REC.kind === "anomaly" && key.length > 7;
  if (daily && !DAYS) {
    $("time-note").textContent = "Loading the day-by-day record…";
    return getJSON(REC.days_file).then(x => { DAYS = daysCache[BASE.key] = x; go(key); }).catch(() => go(key.slice(0, 7)));
  }
  if (daily && !DAYS.days.includes(key)) key = key.slice(0, 7);          // that day was not sampled
  VIEW = key;
  fillSelects();
  let v = BASE, note = REC.note || "";
  if (key && REC.kind === "yearly") v = yearlyView(BASE, REC, key);
  else if (key && REC.kind === "count") v = countView(BASE, REC, REC.months.indexOf(key));
  else if (REC.kind === "probability") {
    const t = REC.days.indexOf(key);
    v = probView(BASE, REC, t);
    note = scorecard(v, t);
    if (MODE === "happened") v = happenedView(v, t);
  } else if (key) {
    const axis = daily ? DAYS.days : REC.months;
    v = anomalyView(BASE, REC, axis, daily ? DAYS.values : REC.values, axis.indexOf(key));
  }
  $("time-note").textContent = note;
  render(BASE.key, v);
}

function fillSelects() {
  const key = VIEW, y = key.slice(0, 4), m = key.slice(5, 7), dd = key.slice(8), axis = axisOf();
  const years = [...new Set(axis.map(k => k.slice(0, 4)))];
  $("yr").innerHTML = (REC.base_label ? `<option value=""${key ? "" : " selected"}>${esc(REC.base_label)}</option>` : "")
    + years.map(v => `<option${v === y ? " selected" : ""}>${v}</option>`).join("");
  const showMonth = REC.kind !== "yearly" && !!key;
  $("mo-wrap").hidden = !showMonth;
  if (showMonth) $("mo").innerHTML = [...new Set(axis.filter(k => k.startsWith(y)).map(k => k.slice(5, 7)))]
    .map(v => `<option value="${v}"${v === m ? " selected" : ""}>${MONS[+v - 1]}</option>`).join("");
  const prob = REC.kind === "probability", showDay = !!key && (prob || (REC.kind === "anomaly" && !!REC.days_file));
  $("dy-wrap").hidden = !showDay;
  if (showDay && prob) $("dy").innerHTML = REC.days.filter(k => k.startsWith(`${y}-${m}`)).map(k => k.slice(8))
    .map(v => `<option value="${v}"${v === dd ? " selected" : ""}>from the ${+v}</option>`).join("");
  else if (showDay) {
    const days = DAYS ? DAYS.days.filter(k => k.startsWith(`${y}-${m}`)).map(k => k.slice(8)) : (REC.sample_days || []).map(v => String(v).padStart(2, "0"));
    $("dy").innerHTML = `<option value="">Whole month</option>` + days.map(v => `<option value="${v}"${v === dd ? " selected" : ""}>${+v}</option>`).join("");
  }
  $("latest").disabled = key === latestKey();
  $("mapmode").hidden = !prob;
  $("mm-est").setAttribute("aria-pressed", MODE === "estimate");
  $("mm-hap").setAttribute("aria-pressed", MODE === "happened");
}

const spanLabel = (y, m, win) => {      // "Jun to Aug 2026" for a 3-month window ending in Aug 2026
  const i = y * 12 + (m - 1) - (win - 1), sy = Math.floor(i / 12), sm = i % 12;
  return sy === y ? `${MONS[sm]} to ${MONS[m - 1]} ${y}` : `${MONS[sm]} ${sy} to ${MONS[m - 1]} ${y}`;
};

// ---- rainfall, soil moisture, vegetation: a value compared with the same time of year in other years ----
function anomalyView(d, h, axis, vals, t) {
  const key = axis[t], daily = key.length > 7, y = key.slice(0, 4), mi = +key.slice(5, 7), mon = MONS[mi - 1];
  const P = h.series[0], S = h.series[1], win = h.window || 1, need = h.min_years || 5;
  const fmt = (s, v) => v.toFixed(s.decimals ?? 2) + (s.unit ? " " + s.unit : "");
  const lessWord = (h.words && h.words.less) || "drier";
  const un = { key: "none", label: "Not rated", text: "", ...(h.unrated || {}) };
  const base = Array.isArray(h.ref) ? h.ref : null;                    // fixed baseline years, or null = every other year
  const when = daily ? `${+key.slice(8)} ${mon} ${y}` : win > 1 ? spanLabel(+y, mi, win) : `${mon} ${y}`;
  const short = k => daily ? `${+k.slice(8)} ${MONS[+k.slice(5, 7) - 1]}` : MONS[+k.slice(5, 7) - 1];
  const lab = Object.fromEntries(d.categories.map(c => [c.key, c.label]));
  const bySeason = {};
  axis.forEach((k, i) => (bySeason[k.slice(5)] = bySeason[k.slice(5)] || []).push(i));
  const stat = (arr, i) => {
    const cur = arr[i]; if (cur == null) return null;
    const refs = [];
    bySeason[axis[i].slice(5)].forEach(j => {
      if (arr[j] == null) return;
      const yy = +axis[j].slice(0, 4);
      if (base ? (yy >= base[0] && yy <= base[1]) : j !== i) refs.push(arr[j]);
    });
    if (refs.length < need) return { cur, n: refs.length };
    const mean = refs.reduce((a, b) => a + b, 0) / refs.length;
    if (h.floor && mean < h.floor.below) return { cur, n: refs.length, mean, floor: true };
    const less = refs.filter(v => v < cur).length + 0.5 * refs.filter(v => v === cur).length;
    const p = less / refs.length * 100;
    return { cur, n: refs.length, mean, pct: mean > 0 ? cur / mean * 100 : 0, less: Math.round(less),
             cat: p <= 10 ? "very_dry" : p <= 30 ? "dry" : p < 70 ? "normal" : p < 90 ? "wet" : "very_wet" };
  };
  const catOf = q => q && q.cat ? q.cat : q && q.floor ? h.floor.key : un.key;
  const inYear = [], inTable = [];
  axis.forEach((k, i) => { if (k.startsWith(y)) { inYear.push(i); if (!daily || k.startsWith(key.slice(0, 7))) inTable.push(i); } });
  const districts = {}, counts = {};
  let others = 0;
  for (const [id, x] of Object.entries(d.districts)) {
    const a = vals[P.key][id]; if (!a) continue;
    const b = S ? vals[S.key][id] : null;
    const s = stat(a, t), ss = b ? stat(b, t) : null, rated = !!(s && s.cat), cat = catOf(s);
    if (s) others = Math.max(others, s.n);
    const yr = inYear.map(i => stat(a, i));
    counts[cat] = (counts[cat] || 0) + 1;
    const rows = [];
    if (s) rows.push([P.label, fmt(P, s.cur)]);
    if (s && s.mean != null) rows.push([base ? `Normal (${base[0]}–${base[1]})` : `Normal for ${daily ? "this date" : mon}`, fmt(P, s.mean)]);
    if (ss) rows.push([S.label, fmt(S, ss.cur) + (ss.cat ? ` (${Math.round(ss.pct)}% of normal)` : "")]);
    if (rated) rows.push([`${base ? "Baseline" : "Other"} years that were ${lessWord}`, s.less + " of " + s.n]);
    districts[id] = {
      name: x.name, cat,
      big: rated ? Math.round(s.pct) + "%" : "–",
      big_note: rated ? `of normal ${P.noun}, ${when}` : s && s.floor ? h.floor.text : s ? `Too few other years to rate ${when}.` : (un.text || `No value for ${when}.`),
      tip: rated ? `${lab[cat]} · ${Math.round(s.pct)}% of normal` : (lab[cat] || un.label),
      rows,
      v: yr.map(q => q && q.cat ? Math.round((q.pct - 100) * 10) / 10 : null),
      c: yr.map(catOf),
      table: { caption: daily ? `Sampled days, ${mon} ${y}` : win > 1 ? `${win}-month totals ending in each month of ${y}` : `Monthly values, ${y}`,
               head: [daily ? "Date" : "Month", P.short + (P.unit ? ` (${P.unit})` : ""), "% of normal"],
               rows: inTable.map(i => { const q = yr[inYear.indexOf(i)]; return [short(axis[i]), q ? q.cur.toFixed(P.decimals ?? 2) : "–", q && q.cat ? Math.round(q.pct) + "%" : "–"]; }) },
    };
  }
  const categories = counts[un.key] && !lab[un.key] ? d.categories.concat([{ key: un.key, label: un.label, note: "", color: "#bdbdbd" }]) : d.categories;
  return { ...d, districts, counts, categories,
    subtitle: base ? `${when}, against ${base[0]}–${base[1]}` : `${when}, against the same ${daily ? "date" : "month"} in ${others} other years`,
    chart: { ...d.chart, x: inYear.map(i => short(axis[i])),
             caption: daily ? `Each sampled day of ${y}` : win > 1 ? `${win}-month periods ending in each month of ${y}` : `Each month of ${y}` } };
}

// ---- fires: detections in one month compared with the same month in other years ----
function countView(d, h, t) {
  const key = h.months[t], y = key.slice(0, 4), mon = MONS[+key.slice(5, 7) - 1], need = h.min_years || 5;
  const lab = Object.fromEntries(d.categories.map(c => [c.key, c.label]));
  const same = [], inYear = [];
  h.months.forEach((k, i) => { if (k.slice(5) === key.slice(5) && i !== t) same.push(i); if (k.startsWith(y)) inYear.push(i); });
  const stat = (a, i, refsIdx) => {
    const refs = refsIdx.map(j => a[j]), n = refs.length, mean = n ? refs.reduce((p, q) => p + q, 0) / n : 0, c = a[i];
    const quiet = n < need || (c < h.quiet && mean < h.quiet), pct = mean > 0 ? c / mean * 100 : Infinity;
    const k = h.breaks.findIndex(b => pct < b);
    return { c, n, mean, pct, quiet, more: refs.filter(v => v > c).length, cat: quiet ? "quiet" : d.categories[k < 0 ? h.breaks.length : k].key };
  };
  const refsFor = i => { const mm = h.months[i].slice(5); return h.months.map((k, j) => k.slice(5) === mm && j !== i ? j : -1).filter(j => j >= 0); };
  const yearRefs = inYear.map(refsFor);
  const districts = {}, counts = {};
  for (const [id, x] of Object.entries(d.districts)) {
    const a = h.counts[id]; if (!a) continue;
    const s = stat(a, t, same), share = s.quiet || !isFinite(s.pct) ? "" : ` (${Math.round(s.pct)}% of normal)`;
    counts[s.cat] = (counts[s.cat] || 0) + 1;
    const yr = inYear.map((i, j) => stat(a, i, yearRefs[j]));
    districts[id] = {
      name: x.name, cat: s.cat, big: s.c.toLocaleString(),
      big_note: `fire detections, ${mon} ${y}${share}`,
      tip: `${s.c.toLocaleString()} detections` + (share ? ` · ${Math.round(s.pct)}% of normal` : ""),
      rows: [[`Normal for ${mon}`, Math.round(s.mean).toLocaleString()], ["Other years with more fires", `${s.more} of ${s.n}`],
             [`All of ${y}`, inYear.reduce((p, i) => p + a[i], 0).toLocaleString()]],
      v: inYear.map(i => a[i]), c: inYear.map(() => s.cat),
      table: { caption: `Detections in each month of ${y}`, head: ["Month", "Detections", "% of normal"],
               rows: inYear.map((i, j) => [MONS[+h.months[i].slice(5) - 1], a[i].toLocaleString(), yr[j].quiet || !isFinite(yr[j].pct) ? "–" : Math.round(yr[j].pct) + "%"]) },
    };
  }
  return { ...d, districts, counts, subtitle: `${mon} ${y}, against ${mon} in ${same.length} other years`,
    chart: { ...d.chart, x: inYear.map(i => MONS[+h.months[i].slice(5) - 1]), caption: `Detections in each month of ${y}` } };
}

// ---- forest loss: one year's loss as a share of tree cover in 2000 ----
function yearlyView(d, h, y) {
  const yi = h.years.indexOf(y), districts = {}, counts = {};
  for (const [id, x] of Object.entries(d.districts)) {
    const tc = x.tc ?? num(x.rows[0][1]) ?? 0, loss = x.v[yi] || 0, low = x.cat === "low";
    const rate = tc > 0 ? loss / tc * 100 : 0, k = h.breaks.findIndex(b => rate < b);
    const cat = low ? "low" : d.categories[k < 0 ? h.breaks.length : k].key;
    const cum = x.v.slice(0, yi + 1).reduce((p, q) => p + q, 0);
    counts[cat] = (counts[cat] || 0) + 1;
    districts[id] = {
      name: x.name, cat, tc, big: low ? "–" : rate.toFixed(1) + "%",
      big_note: low ? x.big_note : `of its 2000 tree cover lost in ${y}`,
      tip: low ? x.tip : `${rate.toFixed(1)}% in ${y}`,
      rows: [x.rows[0], [`Lost in ${y}`, Math.round(loss).toLocaleString() + " ha"],
             [`Lost ${h.years[0]}–${y}`, Math.round(cum).toLocaleString() + " ha" + (tc > 0 ? ` (${Math.round(cum / tc * 100)}%)` : "")]],
      v: x.v, c: x.c, bc: h.years.map(k2 => k2 === y ? "#b2182b" : "#8a9a95"),
    };
  }
  return { ...d, districts, counts, subtitle: `Tree cover lost in ${y}, as a share of tree cover in 2000`,
    chart: { ...d.chart, caption: `Tree cover lost each year (hectares). Red bar: ${y}.` } };
}

// ---- fire risk: the estimate for a five-day period, and what then happened ----
function probView(d, h, t) {
  const key = h.days[t], y = key.slice(0, 4), mon = MONS[+key.slice(5, 7) - 1];
  const start = new Date(key + "T00:00:00Z"), end = new Date(start.getTime() + (h.horizon - 1) * 864e5);
  const dm = x => `${x.getUTCDate()} ${MONS[x.getUTCMonth()]}`;
  const period = `${dm(start)} to ${dm(end)} ${end.getUTCFullYear()}`;
  const short = k => `${+k.slice(8)} ${MONS[+k.slice(5, 7) - 1]}`;
  const lab = Object.fromEntries(d.categories.map(c => [c.key, c.label]));
  const catOf = p => { const i = h.breaks.findIndex(b => p < b); return d.categories[i < 0 ? h.breaks.length : i].key; };
  const what = o => o == null ? "Not known yet" : o ? "Fire detected" : "No fire detected";
  const inYear = [], inMonth = [];
  h.days.forEach((k, i) => { if (k.startsWith(y)) { inYear.push(i); if (k.startsWith(key.slice(0, 7))) inMonth.push(i); } });
  const districts = {}, counts = {};
  for (const [id, base] of Object.entries(d.districts)) {
    const p = h.p[id], o = h.o[id], u = h.u[id]; if (!p || p[t] == null) continue;
    const cat = catOf(p[t]);
    counts[cat] = (counts[cat] || 0) + 1;
    districts[id] = {
      name: base.name, cat, big: p[t] + "%",
      big_note: `estimated chance of at least one fire detection, ${period}`,
      tip: `${lab[cat]} · ${p[t]}%` + (o[t] == null ? "" : o[t] ? " · fire detected" : " · no fire detected"),
      rows: [["What happened", what(o[t])], ["Usual chance for these dates", u[t] == null ? "–" : u[t] + "%"]],
      v: inYear.map(i => p[i] ?? 0), c: inYear.map(() => cat),
      bc: inYear.map(i => o[i] ? "#b2182b" : o[i] === 0 ? "#8a9a95" : "#d0d0d0"),
      bt: inYear.map(i => what(o[i]).toLowerCase()),
      table: { caption: `Sampled days, ${mon} ${y}`, head: ["Five days from", "Estimated chance", "What happened"],
               rows: inMonth.map(i => [short(h.days[i]), p[i] == null ? "–" : p[i] + "%", what(o[i])]) },
    };
  }
  const marks = Object.keys(districts).filter(id => h.o[id][t] === 1);
  return { ...d, districts, counts, subtitle: period, marks,
    chart: { ...d.chart, max: 100, x: inYear.map(i => short(h.days[i])), caption: `Estimated chance on each sampled day of ${y} (%). Red bars: a fire was detected.` } };
}

function scorecard(v, t) {               // how the estimates for this period compare with what happened
  const groups = v.categories.map(c => ({ c, n: 0, fires: 0 }));
  let known = 0;
  for (const id of Object.keys(v.districts)) {
    const o = REC.o[id][t], g = groups.find(x => x.c.key === v.districts[id].cat);
    g.n++; if (o != null) { known++; g.fires += o; }
  }
  return known ? "What happened: " + groups.filter(g => g.n).map(g => `${g.c.label}: fire in ${g.fires} of ${g.n} districts`).join("; ") + ". " + (REC.note || "")
               : "What happened in this period is not known yet.";
}

function happenedView(v, t) {            // the same period, coloured by what was observed
  const cats = [{ key: "fire", label: "Fire detected", note: "", color: "#b2182b" },
                { key: "nofire", label: "No fire detected", note: "", color: "#f3efe4" },
                { key: "unknown", label: "Not known yet", note: "", color: "#bdbdbd" }];
  const districts = {}, counts = {};
  for (const [id, x] of Object.entries(v.districts)) {
    const o = REC.o[id][t], cat = o == null ? "unknown" : o ? "fire" : "nofire";
    counts[cat] = (counts[cat] || 0) + 1;
    districts[id] = { ...x, cat };
  }
  return { ...v, districts, counts, categories: cats.filter(c => counts[c.key]), marks: null };
}

// ---------- drawing ----------
function render(key, d) {
  D = d;
  $("time").hidden = !REC;
  $("download-all").hidden = !REC;
  history.replaceState(null, "", "#" + key);
  document.querySelectorAll("#tabs button[data-key]").forEach(b => b.setAttribute("aria-current", b.dataset.group ? b.dataset.group === (TL.products[key] || {}).group : b.dataset.key === key));
  $("demo").style.display = d.demo ? "block" : "none";
  color = Object.fromEntries(d.categories.map(c => [c.key, c.color]));
  label = Object.fromEntries(d.categories.map(c => [c.key, c.label]));
  FULL = d;
  if (REGION) {                         // keep only the chosen region; the legend, ranking and downloads follow
    const districts = Object.fromEntries(Object.entries(d.districts).filter(([id]) => inRegion(id))), counts = {};
    Object.values(districts).forEach(x => counts[x.cat] = (counts[x.cat] || 0) + 1);
    d = { ...d, districts, counts, marks: d.marks && d.marks.filter(inRegion), region: REGION };
    D = d;
  }
  geoLayer.eachLayer(l => {
    const x = d.districts[l.feature.properties.shapeID];
    if (!x && REGION) return l.setStyle({ fillColor: "#999", fillOpacity: 0.08, color: SAT ? "#ffffff" : "#55605c", weight: 0.3 });
    l.setStyle({ fillOpacity: 0.9 * FILL });
    l.setStyle({ fillColor: x ? color[x.cat] : "#999", color: SAT ? "#ffffff" : "#55605c", weight: 0.6 });
  });
  dots.clearLayers();
  (d.marks || []).forEach(id => {
    if (shapes[id]) L.circleMarker(shapes[id].getCenter(), { radius: 3.2, color: "#fff", weight: 1, fillColor: "#111", fillOpacity: 1, interactive: false }).addTo(dots);
  });
  const total = Object.keys(d.districts).length;
  const prod = TL.products[key];
  $("status").innerHTML = prod ? `${badge(prod.status)} <span class="sub">${esc(prod.name)}, version ${esc(prod.version)}</span>` : "";
  $("title").textContent = d.title;
  $("subtitle").textContent = d.subtitle + ". " + total + " districts" + (REGION ? ` in ${REGION} Region` : "");
  $("bar").innerHTML = d.categories.map(c => {
    const n = d.counts[c.key] || 0;
    return n ? `<div title="${esc(c.label)}: ${n} districts" style="width:${n / total * 100}%;background:${c.color}"></div>` : "";
  }).join("");
  $("legend").innerHTML = d.categories.map(c =>
    `<li><span class="sw" style="background:${c.color}"></span>${esc(c.label)} <span class="n">${esc(c.note || "")}</span><b>${d.counts[c.key] || 0}</b></li>`).join("")
    + (d.marks ? `<li><span class="sw" style="background:#111;border-radius:50%;width:9px;height:9px;margin:0 2.5px;border:1px solid #fff;outline:1px solid #111"></span>Dot: a fire was detected <b>${d.marks.length}</b></li>` : "");
  $("names").innerHTML = Object.values(d.districts).map(x => x.name).sort().map(n => `<option value="${esc(n)}">`).join("");
  $("how").textContent = d.how;
  $("limits").innerHTML = d.limits.concat(["District boundaries are the 260 districts of 2019. Newer districts are not yet shown."]).map(t => `<li>${esc(t)}</li>`).join("");
  $("tables").innerHTML = (d.tables || []).map(t => `<h2>${esc(t.caption)}</h2><div class="card" style="max-width:640px;overflow-x:auto">
    <table class="mv" style="margin:0"><thead><tr>${t.head.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    ${t.note ? `<p class="sub" style="max-width:75ch">${esc(t.note)}</p>` : ""}`).join("");
  const today = new Date(), day = `${today.getDate()} ${["January","February","March","April","May","June","July","August","September","October","November","December"][today.getMonth()]} ${today.getFullYear()}`;
  $("cite").textContent = `${TL.author} (${d.updated.slice(0, 4)}). ${d.title}: ${d.subtitle}${REGION ? ", " + REGION + " Region" : ""}. Tinga Lens`
    + (prod ? `, product version ${prod.version}` : "") + `. ${TL.site}/${prod ? prod.page : ""}#${key}. Accessed ${day}. Source data: ${d.source}.`;
  $("foot-layer").innerHTML = `Map shown: updated ${esc(d.updated)}. Source: ${esc(d.source)}. `
    + d.credits.map(c => `<a href="${esc(c.url)}">${esc(c.text)}</a>. `).join("");
  drawPoints();
  ranking();
  if (selected && d.districts[selected]) select(selected); else { selected = null; $("detail").innerHTML = EMPTY; }
}

function ranking() {
  $("rk-hi").setAttribute("aria-pressed", rankHigh);
  $("rk-lo").setAttribute("aria-pressed", !rankHigh);
  const rows = Object.entries(D.districts).map(([id, x]) => ({ id, x, v: num(x.big) })).filter(r => r.v !== null);
  rows.sort((a, b) => (rankHigh ? b.v - a.v : a.v - b.v) || a.x.name.localeCompare(b.x.name));
  $("rank").innerHTML = rows.slice(0, 10).map((r, i) =>
    `<li data-id="${esc(r.id)}"><span class="i">${i + 1}</span><span class="sw" style="background:${color[r.x.cat]}"></span><span class="nm">${esc(r.x.name)}</span><b>${esc(TL.relBig(r.x.big, r.x.big_note)[0])}</b></li>`).join("")
    || '<li style="cursor:default;color:var(--muted)">No rated districts on this map.</li>';
}

// ---------- downloads ----------
const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
const credit = () => q("Source: " + BASE.source + ". Updated " + BASE.updated + ". Product version " + ((TL.products[BASE.key] || {}).version || "-") + ". Tinga Lens, " + TL.site);
const byName = () => Object.entries(BASE.districts).sort((a, b) => a[1].name.localeCompare(b[1].name));

function saveCSV(lines, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// The map as a picture. It is drawn fresh here (not copied from the screen), with the Tinga Lens
// name printed across it, so the name is part of the picture itself.
function downloadImage() {
  const W = 1600, rb = regionBounds(), aspect = (rb.getNorth() - rb.getSouth()) / ((rb.getEast() - rb.getWest()) * Math.cos((rb.getNorth() + rb.getSouth()) / 2 * Math.PI / 180));
  const H = Math.round(260 + Math.max(Math.min(1060 * aspect, 1390), 80 + D.categories.length * 68) + 250);   // tall for Ghana, shorter for a wide region
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d"), SERIF = '"Source Serif 4", Georgia, serif', SANS = '"Source Sans 3", Arial, sans-serif';
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, W, H);
  const wrap = (text, x, y, maxW, lh) => {            // returns the y after the last line
    let line = "";
    for (const w of String(text).split(" ")) {
      if (g.measureText(line + w).width > maxW && line) { g.fillText(line.trim(), x, y); y += lh; line = ""; }
      line += w + " ";
    }
    g.fillText(line.trim(), x, y); return y + lh;
  };
  g.fillStyle = "#1B2B24"; g.textBaseline = "top";
  g.font = `600 54px ${SERIF}`; let y = wrap(D.title, 70, 60, W - 140, 62);
  g.font = `400 30px ${SANS}`; g.fillStyle = "#56655C"; y = wrap(D.subtitle + (REGION ? `. ${REGION} Region` : ""), 70, y + 6, W - 140, 38);

  // map area
  const top = y + 24, bottom = H - 250, left = 70, right = W - 470;
  const b = regionBounds(), k = Math.cos((b.getNorth() + b.getSouth()) / 2 * Math.PI / 180);
  const s = Math.min((right - left) / ((b.getEast() - b.getWest()) * k), (bottom - top) / (b.getNorth() - b.getSouth()));
  const ox = left + ((right - left) - (b.getEast() - b.getWest()) * k * s) / 2;
  const X = lon => ox + (lon - b.getWest()) * k * s, Y = lat => top + (b.getNorth() - lat) * s;
  geoLayer.eachLayer(l => {
    const f = l.feature, x = D.districts[f.properties.shapeID];
    if (!x && REGION) return;
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    g.beginPath();
    polys.forEach(p => p.forEach(ring => { ring.forEach(([lon, lat], i) => i ? g.lineTo(X(lon), Y(lat)) : g.moveTo(X(lon), Y(lat))); g.closePath(); }));
    g.fillStyle = x ? color[x.cat] : "#999"; g.fill("evenodd");
    g.strokeStyle = "#55605c"; g.lineWidth = 1; g.stroke();
  });

  // the name, repeated across the map so cropping does not remove it
  g.save(); g.beginPath(); g.rect(left - 30, top - 10, right - left + 60, bottom - top + 20); g.clip();
  g.translate(W / 2, H / 2); g.rotate(-Math.PI / 6);
  g.font = `700 44px ${SANS}`; g.fillStyle = "rgba(27,43,36,0.13)"; g.textBaseline = "middle";
  for (let yy = -H; yy < H; yy += 190) for (let xx = -W; xx < W; xx += 520) g.fillText("Tinga Lens", xx + ((yy / 190) % 2 ? 260 : 0), yy);
  g.restore();

  // legend
  let ly = top + 10; const lx = W - 430;
  g.textBaseline = "top"; g.fillStyle = "#1B2B24"; g.font = `600 28px ${SANS}`; g.fillText("Districts", lx, ly); ly += 46;
  D.categories.forEach(cat => {
    g.fillStyle = cat.color; g.fillRect(lx, ly, 34, 34); g.strokeStyle = "#8a948e"; g.lineWidth = 1; g.strokeRect(lx + .5, ly + .5, 33, 33);
    g.fillStyle = "#1B2B24"; g.font = `400 26px ${SANS}`; g.fillText(cat.label, lx + 48, ly + 2);
    g.textAlign = "right"; g.font = `600 26px ${SANS}`; g.fillText(String(D.counts[cat.key] || 0), W - 70, ly + 2); g.textAlign = "left";
    ly += 44;
    if (cat.note) { g.fillStyle = "#56655C"; g.font = `400 21px ${SANS}`; g.fillText(cat.note, lx + 48, ly - 8); ly += 22; }
  });

  // footer: brand, source and terms
  const fy = H - 215;
  g.strokeStyle = "#D5DBCF"; g.lineWidth = 2; g.beginPath(); g.moveTo(70, fy); g.lineTo(W - 70, fy); g.stroke();
  g.save(); g.translate(70, fy + 26); g.scale(0.6, 0.6); g.lineCap = "round"; g.lineWidth = 10;
  g.strokeStyle = "#17252A"; g.beginPath(); g.arc(60, 60, 52, -Math.PI / 2, Math.PI, false); g.stroke();
  g.strokeStyle = "#2D6A4F"; g.beginPath(); g.arc(60, 60, 30, -Math.PI / 2, Math.PI, false); g.stroke();
  g.fillStyle = "#A98467"; g.beginPath(); g.arc(60, 60, 11, 0, 7); g.fill();
  g.fillStyle = "#277DA1"; g.beginPath(); g.arc(23, 23, 7, 0, 7); g.fill(); g.restore();
  g.textBaseline = "top"; g.fillStyle = "#1B2B24"; g.font = `700 40px ${SANS}`; g.fillText("Tinga Lens", 160, fy + 30);
  g.font = `400 24px ${SANS}`; g.fillStyle = "#56655C"; g.fillText(TL.site.replace("https://", ""), 160, fy + 76);
  g.font = `400 23px ${SANS}`;
  const version = (TL.products[BASE.key] || {}).version || "-";
  let ty = wrap(`Source: ${BASE.source}. Updated ${BASE.updated}. Product version ${version}. Boundaries: geoBoundaries (CC BY 4.0).`, 470, fy + 28, W - 540, 30);
  wrap("© Tinga Lens. You may share this image unchanged with credit. To use it without the Tinga Lens name, or in a product or publication, ask first: see the About page.", 470, ty + 4, W - 540, 30);

  c.toBlob(blob => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tinga-lens-${BASE.key}${REGION ? "-" + REGION.toLowerCase().replace(/ /g, "-") : ""}${VIEW ? "-" + VIEW : ""}.png`;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }, "image/png");
}

function download() {                  // the map as shown
  const cols = [];
  Object.values(D.districts).forEach(x => x.rows.forEach(r => { if (r[0] && r[1] !== "" && !cols.includes(r[0])) cols.push(r[0]); }));
  const lines = [["District"].concat(LL, ["Rating", "Main figure", "What the figure means"], cols).map(q).join(",")];
  Object.entries(D.districts).sort((a, b) => a[1].name.localeCompare(b[1].name)).forEach(([id, x]) => {
    const m = Object.fromEntries(x.rows);
    lines.push([x.name].concat(ll(id), [label[x.cat], x.big, x.big_note], cols.map(c => m[c] ?? "")).map(q).join(","));
  });
  lines.push("", credit());
  saveCSV(lines, `tinga-lens-${D.key}${REGION ? "-" + REGION.toLowerCase().replace(/ /g, "-") : ""}-${REC && VIEW ? VIEW : D.updated}.csv`);
}

function downloadAll() {               // every district and every period on record
  const name = extra => `tinga-lens-${BASE.key}-full-record${extra || ""}-${BASE.updated}.csv`;
  let lines;
  if (REC.kind === "probability") {
    lines = [["District"].concat(LL, ["Five days from", "Estimated chance (%)", "Usual chance for these dates (%)", "Fire detected (1 = yes, 0 = no)"]).map(q).join(",")];
    byName().forEach(([id, x]) => REC.days.forEach((k, i) => lines.push([x.name].concat(ll(id), [k, REC.p[id][i] ?? "", REC.u[id][i] ?? "", REC.o[id][i] ?? ""]).map(q).join(","))));
  } else if (REC.kind === "count") {
    lines = [["District"].concat(LL, ["Month", "Fire detections"]).map(q).join(",")];
    byName().forEach(([id, x]) => REC.months.forEach((k, i) => lines.push([x.name].concat(ll(id), [k, REC.counts[id][i]]).map(q).join(","))));
  } else if (REC.kind === "yearly") {
    lines = [["District"].concat(LL, ["Year", "Tree cover lost (ha)", "Tree cover in 2000 (ha)"]).map(q).join(",")];
    byName().forEach(([id, x]) => REC.years.forEach((k, i) => lines.push([x.name].concat(ll(id), [k, x.v[i], x.tc ?? num(x.rows[0][1]) ?? ""]).map(q).join(","))));
  } else {
    const run = () => {
      const src = DAYS || REC, axis = DAYS ? DAYS.days : REC.months;
      const out = [["District"].concat(LL, [DAYS ? "Date" : "Month"], REC.series.map(s => s.label + (s.unit ? ` (${s.unit})` : ""))).map(q).join(",")];
      byName().forEach(([id, x]) => axis.forEach((k, i) =>
        out.push([x.name].concat(ll(id), [k], REC.series.map(s => { const v = (src.values[s.key][id] || [])[i]; return v == null ? "" : v; })).map(q).join(","))));
      out.push("", credit());
      saveCSV(out, name(DAYS ? "-by-day" : "-by-month"));
    };
    return REC.days_file && !DAYS ? getJSON(REC.days_file).then(x => { DAYS = daysCache[BASE.key] = x; run(); }).catch(run) : run();
  }
  lines.push("", credit());
  saveCSV(lines, name());
}

// ---------- district panel ----------
function chart(ch, x) {
  const W = 300, H = 140, n = x.v.length, bw = W / n, pad = n > 40 ? 0.4 : n > 16 ? 1 : 3, every = Math.ceil(n / (n > 40 ? 4.5 : 6));
  const labels = ch.x.map((t, i) => (n - 1 - i) % every ? "" : `<text x="${i * bw + bw / 2}" y="${H - 2}" text-anchor="${i > n - 3 && n > 16 ? "end" : "middle"}">${esc(t)}</text>`).join("");
  let bars, base;
  if (ch.kind === "diverging") {
    base = 70;
    bars = x.v.map((v, i) => {
      if (v == null) return `<rect x="${i * bw + pad}" y="${base - 2}" width="${bw - 2 * pad}" height="4" fill="#bdbdbd"><title>${esc(ch.x[i])}: not rated</title></rect>`;
      const c = Math.max(-ch.cap, Math.min(ch.cap, v)), h = Math.max(2, Math.abs(c) / ch.cap * 48);
      return `<rect x="${i * bw + pad}" y="${c >= 0 ? base - h : base}" width="${bw - 2 * pad}" height="${h}" rx="${n > 40 ? 0 : 2}" fill="${color[x.c[i]]}" stroke="rgba(0,0,0,.3)" stroke-width="${n > 40 ? 0.2 : 0.5}"><title>${esc(ch.x[i])}: ${v > 0 ? "+" : ""}${v}${esc(ch.unit)} (${esc(label[x.c[i]])})</title></rect>`;
    }).join("");
  } else {
    base = H - 16;
    const max = ch.max || Math.max(...x.v.map(v => v || 0), 1e-9);
    bars = x.v.map((v, i) => {
      if (v == null) return `<rect x="${i * bw + pad}" y="${base - 2}" width="${bw - 2 * pad}" height="2" fill="#bdbdbd"><title>${esc(ch.x[i])}: no value</title></rect>`;
      const h = Math.max(v > 0 ? 1.5 : 0, v / max * (base - 14));
      return `<rect x="${i * bw + pad}" y="${base - h}" width="${bw - 2 * pad}" height="${h}" rx="${n > 40 ? 0 : 1.5}" fill="${x.bc ? x.bc[i] : "var(--accent)"}"><title>${esc(ch.x[i])}: ${v.toLocaleString()} ${esc(ch.unit)}${x.bt ? " · " + esc(x.bt[i]) : ""}</title></rect>`;
    }).join("") + `<text x="0" y="9">${ch.max ? "top of chart = " : "max "}${Math.round(max).toLocaleString()} ${esc(ch.unit)}</text>`;
  }
  return `<p class="sub" style="margin-bottom:2px">${esc(ch.caption)}</p>
    <svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(ch.caption)}">
    <line x1="0" x2="${W}" y1="${base}" y2="${base}" stroke="var(--muted)" stroke-width="1"/>
    ${ch.top ? `<text x="0" y="9">${esc(ch.top)}</text>` : ""}${ch.bottom ? `<text x="0" y="${H - 17}">${esc(ch.bottom)}</text>` : ""}${bars}${labels}</svg>`;
}

function select(id) {
  const x = D.districts[id]; if (!x) return;
  if (selected && shapes[selected]) shapes[selected].setStyle({ weight: 0.6, color: "#55605c" });
  selected = id;
  shapes[id].setStyle({ weight: 3, color: "#111" }).bringToFront();
  document.dispatchEvent(new CustomEvent("tl:district", { detail: { id, name: x.name, layer: BASE.key } }));
  $("search").value = x.name;
  const t = x.table;
  $("detail").innerHTML = `
    <h2>${esc(x.name)}</h2>
    <div><span class="big">${esc(TL.relBig(x.big, x.big_note)[0])}</span>
      <span class="pill" style="background:${color[x.cat]};color:${ink(color[x.cat])}">${esc(label[x.cat])}</span></div>
    <p class="sub">${esc(TL.relBig(x.big, x.big_note)[1])}</p>
    <dl>${TL.dl(x.rows)}</dl>
    ${chart(D.chart, x)}
    ${t ? `<table class="mv"><caption>${esc(t.caption)}</caption><thead><tr>${t.head.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : ""}`;
}
