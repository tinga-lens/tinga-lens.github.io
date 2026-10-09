// Tinga Lens - biodiversity: species lists for a district, and the species explorer.
// Everything shown comes from the files in data/bio/, built by scripts/biodiversity.py.
(function () {
  let SP = null, GROUPS = [], PAIRS = null, REG = {}, NAMES = {}, geo = null;
  let cur = null, shown = 50, smap = null, slayer = null;     // district list state, explorer map
  let PTS = null, CEN = {};                                      // recorded places with coordinates (once built); district centres
  getJSON("data/centroids.json").then(c => { CEN = c; }).catch(() => {});
  const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  const slug = t => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const save = (lines, name) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = name; document.body.append(a); a.click(); a.remove();
  };
  const foot = extra => q(extra + "Each row is one recorded place. "
    + (PTS ? `To protect sensitive species, every position is rounded to ${PTS.generalise_deg} degree (about 11 km), so exact sites are not published. ` : "")
    + "A place with no record does not mean the species is absent. " + $("cov-cite").textContent + " Tinga Lens, " + TL.site);
  let REGION = "", curSpecies = null, curRows = [];                         // region chosen on the map above; species open in the explorer
  const HINT = "Click a district on the map to list the species recorded there.";
  const F = { key: 0, name: 1, common: 2, group: 3, records: 4, districts: 5, first: 6, last: 7 };
  const nm = s => `<i>${esc(s[F.name])}</i>${s[F.common] ? `<small>${esc(s[F.common])}</small>` : ""}`;
  const yr = v => v == null ? "–" : v;

  $("bio").hidden = false;
  Promise.all([getJSON("data/bio/species.json"), getJSON("data/biodiversity.json"), getJSON("data/regions.json").catch(() => ({}))]).then(([sp, layer, reg]) => {
    SP = sp.rows; GROUPS = sp.groups; REG = reg; PTS = sp.points || null;
    $("bd-pts").hidden = !PTS;
    Object.entries(layer.districts).forEach(([id, x]) => NAMES[id] = x.name);
    $("bd-group").innerHTML = `<option value="">All groups</option>` + GROUPS.map((g, i) => `<option value="${i}">${esc(g)}</option>`).join("");
    const c = layer.coverage;
    $("cov").innerHTML = [[c.records, "occurrence records used"], [c.species, "recorded species"], [c.datasets, "contributing datasets"],
      [c.districts_with_records + " of 260", "districts with records"], [`${c.first}–${c.last}`, "years covered"], [c.records_in_download - c.records, "records left out"]]
      .map(([v, t]) => `<div><b>${typeof v === "number" ? v.toLocaleString() : esc(v)}</b><span>${t}</span></div>`).join("");
    // records by group, counted from the species file, so the imbalance between groups is plain to see
    const g = GROUPS.map(() => [0, 0]);
    SP.forEach(s => { g[s[F.group]][0]++; g[s[F.group]][1] += s[F.records]; });
    const all = g.reduce((a, x) => a + x[1], 0), share = i => g[i][1] / all * 100;
    $("cov-groups").innerHTML = GROUPS.map((name, i) => [name, ...g[i]]).filter(r => r[1]).sort((a, b) => b[2] - a[2]).map(([name, ns, nr]) =>
      `<tr style="cursor:default"><td>${esc(name)}</td><td class="num">${ns.toLocaleString()}</td><td class="num">${nr.toLocaleString()}</td><td class="num">${(nr / all * 100).toFixed(1)}%</td><td class="num">${(nr / ns).toFixed(0)}</td></tr>`).join("");
    const bi = GROUPS.indexOf("Birds"), mi = GROUPS.indexOf("Mammals");
    $("cov-gap").textContent = `Birds make up ${share(bi).toFixed(0)}% of the records, because birdwatchers log sightings in very large numbers. Mammals make up ${share(mi).toFixed(1)}%, and most of those are bats and rodents from museum collections. Large mammals such as elephant, buffalo, lion and leopard are almost absent, because survey results for them are rarely published to GBIF and many sightings carry a ${c.noncommercial ? "licence that was" : "non-commercial licence that is"} ${c.noncommercial ? "included here" : "left out here"}. Their absence from these lists does not mean they are absent from Ghana.`;
    $("cov-cite").innerHTML = `Records are left out when they name no species, have a vague or flagged position, are fossils or captive animals, or fall outside the district boundaries. Records under a non-commercial licence are not requested. Cite as: ${esc(layer.source)}.`
      + (c.doi ? ` <a href="https://doi.org/${esc(c.doi)}">Open the GBIF download</a>, which lists every contributing dataset.` : "");
    if (location.hash.startsWith("#species=")) openSpecies(SP.findIndex(s => String(s[F.key]) === location.hash.slice(9)));
  }).catch(e => { $("bd-hint").textContent = "Could not load the species files: " + e.message; });

  // ---------- species recorded in the chosen district, or in the whole chosen region ----------
  document.addEventListener("tl:district", e => {
    const { id, name } = e.detail;
    getJSON(`data/bio/districts/${id}.json`).then(d => { cur = { id, name, rows: d.rows }; }).catch(() => { cur = { id, name, rows: [] }; }).then(() => { shown = 50; drawDistrict(); areas(); });
  });
  document.addEventListener("tl:region", e => {
    REGION = e.detail.region;
    if (curSpecies != null) openSpecies(curSpecies);
    if (!REGION) { cur = null; $("bd").hidden = true; $("bd-hint").textContent = HINT; areas(); return; }
    const region = REGION, ids = Object.keys(REG).filter(id => REG[id] === region);
    $("bd-hint").textContent = `Adding up the records for ${region} Region…`;
    Promise.all(ids.map(id => getJSON(`data/bio/districts/${id}.json`).then(d => d.rows).catch(() => []))).then(all => {
      if (REGION !== region) return;                       // the region was changed again while loading
      const m = new Map();                                 // species -> [species, records, places, first, last]
      all.forEach(rows => rows.forEach(([s, n, places, first, last]) => {
        const x = m.get(s);
        if (!x) m.set(s, [s, n, places, first, last]);
        else { x[1] += n; x[2] += places; if (first != null && (x[3] == null || first < x[3])) x[3] = first; if (last != null && (x[4] == null || last > x[4])) x[4] = last; }
      }));
      cur = { id: null, region, name: `${region} Region`, rows: [...m.values()].sort((a, b) => b[1] - a[1]) };
      shown = 50; drawDistrict(); areas();
    });
  });
  function filtered() {
    const q = $("bd-q").value.trim().toLowerCase(), g = $("bd-group").value;
    return cur.rows.filter(r => { const s = SP[r[0]];
      return (!g || s[F.group] === +g) && (!q || s[F.name].toLowerCase().includes(q) || s[F.common].toLowerCase().includes(q)); });
  }
  function drawDistrict() {
    if (!cur || !SP) return;
    $("bd").hidden = false;
    $("bd-hint").textContent = cur.region ? `${cur.name}: every species recorded in any of its districts. Click a district on the map for that district alone.`
      : `${cur.name}${REG[cur.id] ? ", " + REG[cur.id] + " Region" : ""}`;
    const rows = filtered();
    $("bd-count").textContent = cur.rows.length ? `${rows.length.toLocaleString()} of ${cur.rows.length.toLocaleString()} recorded species shown, most recorded first. Click a species to see where else it has been recorded.`
      : `No usable records in GBIF for this ${cur.region ? "region" : "district"}. That reflects surveying, not an absence of wildlife.`;
    $("bd-rows").innerHTML = rows.slice(0, shown).map(r => { const s = SP[r[0]];
      return `<tr data-s="${r[0]}"><td>${nm(s)}</td><td>${esc(GROUPS[s[F.group]])}</td><td class="num">${r[1].toLocaleString()}</td><td class="num">${r[2]}</td><td class="num">${yr(r[3])}</td><td class="num">${yr(r[4])}</td></tr>`; }).join("");
    $("bd-more").hidden = rows.length <= shown;
  }
  ["bd-q", "bd-group"].forEach(id => $(id).addEventListener("input", () => { shown = 50; drawDistrict(); }));
  $("bd-more").addEventListener("click", () => { shown += 200; drawDistrict(); });
  $("bd-rows").addEventListener("click", e => { const tr = e.target.closest("tr[data-s]"); if (tr) openSpecies(+tr.dataset.s, true); });
  // every recorded place in the chosen district, or in every district of the chosen region
  $("bd-pts").addEventListener("click", () => {
    if (!cur || !PTS) return;
    const ids = cur.region ? Object.keys(REG).filter(id => REG[id] === cur.region) : [cur.id], btn = $("bd-pts"), label = btn.textContent;
    btn.disabled = true; btn.textContent = "Preparing…";
    Promise.all(ids.map(id => getJSON(`data/bio/dpoints/${id}.json`).then(d => d.rows.map(r => [id, r])).catch(() => []))).then(all => {
      const lines = [["District", "Region", "Scientific name", "Common name", "Group", "Latitude", "Longitude", "Records at this place", "First year", "Latest year", "GBIF species key"].map(q).join(",")];
      all.flat().sort((a, b) => SP[a[1][0]][F.name].localeCompare(SP[b[1][0]][F.name])).forEach(([id, [si, lat, lon, n, first, last]]) => {
        const s = SP[si];
        lines.push([NAMES[id] || "", REG[id] || "", s[F.name], s[F.common], GROUPS[s[F.group]], lat, lon, n, first, last, s[F.key]].map(q).join(","));
      });
      lines.push("", foot(`${cur.name}. `));
      save(lines, `tinga-lens-records-${slug(cur.name)}.csv`);
    }).finally(() => { btn.disabled = false; btn.textContent = label; });
  });
  // one species: every recorded place in the whole country, the chosen region, or the chosen district
  $("sx-pts").addEventListener("click", () => {
    if (curSpecies == null || !PTS || !PAIRS) return;
    const i = curSpecies, s = SP[i], area = $("sx-area").value, btn = $("sx-pts");
    btn.disabled = true;
    getJSON(`data/bio/points/${i % PTS.buckets}.json`).then(f => {
      const keep = id => area === "country" || (area === "region" ? REG[id] === REGION : cur && id === cur.id);
      const rows = (f.species[i] || []).map(([lat, lon, d, n, first, last]) => ({ id: PAIRS.districts[d], lat, lon, n, first, last })).filter(r => keep(r.id));
      const where = area === "country" ? "Ghana" : area === "region" ? `${REGION} Region` : cur.name;
      if (!rows.length) { $("sx-pts-note").textContent = `No record of this species in ${where}.`; return; }
      $("sx-pts-note").textContent = "";
      const lines = [["Scientific name", "Common name", "Group", "District", "Region", "Latitude", "Longitude", "Records at this place", "First year", "Latest year", "GBIF species key"].map(q).join(",")];
      rows.sort((a, b) => (NAMES[a.id] || "").localeCompare(NAMES[b.id] || "")).forEach(r =>
        lines.push([s[F.name], s[F.common], GROUPS[s[F.group]], NAMES[r.id] || "", REG[r.id] || "", r.lat, r.lon, r.n, r.first, r.last, s[F.key]].map(q).join(",")));
      lines.push("", foot(`${where}. `));
      save(lines, `tinga-lens-${slug(s[F.name])}-records-${slug(where)}.csv`);
    }).catch(() => { $("sx-pts-note").textContent = "The records could not be loaded. Please try again."; }).finally(() => { btn.disabled = false; });
  });
  const areas = () => {                      // the choices offered follow what is selected on the map
    if (!PTS) return;
    const keep = $("sx-area").value;
    $("sx-area").innerHTML = `<option value="country">all of Ghana</option>` + (REGION ? `<option value="region">${esc(REGION)} Region</option>` : "")
      + (cur && !cur.region ? `<option value="district">${esc(cur.name)}</option>` : "");
    $("sx-area").value = [...$("sx-area").options].some(o => o.value === keep) ? keep : (cur && !cur.region ? "district" : REGION ? "region" : "country");
    $("sx-pts-wrap").hidden = false; $("sx-pts-note").textContent = "";
  };

  $("bd-csv").addEventListener("click", () => {
    const c = cur.region ? [] : (CEN[cur.id] || ["", ""]);
    const lines = [[cur.region ? "Region" : "District"].concat(cur.region ? [] : ["District centre latitude", "District centre longitude"], ["Scientific name", "Common name", "Group", "Records", "Recorded places", "First year", "Latest year", "GBIF species key"]).map(q).join(",")];
    filtered().forEach(r => { const s = SP[r[0]]; lines.push([cur.name].concat(c, [s[F.name], s[F.common], GROUPS[s[F.group]], r[1], r[2], r[3], r[4], s[F.key]]).map(q).join(",")); });
    lines.push("", q($("cov-cite").textContent + " Tinga Lens, " + TL.site));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = `tinga-lens-species-${cur.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.csv`;
    document.body.append(a); a.click(); a.remove();
  });

  // ---------- species explorer ----------
  function hits(list, note) {
    $("sx-hits").hidden = false;
    $("sx-hits").innerHTML = list.map(i => { const s = SP[i];
      return `<li data-s="${i}"><span><i>${esc(s[F.name])}</i>${s[F.common] ? ", " + esc(s[F.common]) : ""}</span><span class="sub" style="margin:0;white-space:nowrap">${s[F.records].toLocaleString()} records</span></li>`; }).join("")
      || `<li style="cursor:default">${note}</li>`;
  }
  $("sx-q").addEventListener("input", () => {
    const q = $("sx-q").value.trim().toLowerCase();
    if (!SP || q.length < 2) { $("sx-hits").hidden = true; return; }
    const list = [];
    SP.forEach((s, i) => { if (s[F.name].toLowerCase().includes(q) || s[F.common].toLowerCase().includes(q)) list.push(i); });
    list.sort((a, b) => SP[b][F.records] - SP[a][F.records]);
    hits(list.slice(0, 12), "No recorded species matches that name. Try the scientific name.");
  });
  $("sx-hits").addEventListener("click", e => { const li = e.target.closest("li[data-s]"); if (li) openSpecies(+li.dataset.s); });
  $("sx-rows").addEventListener("click", e => { const tr = e.target.closest("tr[data-id]"); if (tr && window.focusOn) { focusOn(tr.dataset.id); $("map").scrollIntoView({ behavior: "smooth", block: "center" }); } });

  $("sx-csv").addEventListener("click", () => {            // one species: a row for every district where it was recorded
    if (curSpecies == null) return;
    const s = SP[curSpecies], q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lines = [["Scientific name", "Common name", "Group", "District", "Region", "Records", "Latest year", "GBIF species key"].map(q).join(",")];
    curRows.forEach(r => lines.push([s[F.name], s[F.common], GROUPS[s[F.group]], NAMES[r.id] || "", REG[r.id] || "", r.n, r.last, s[F.key]].map(q).join(",")));
    lines.push("", q((REGION ? `${REGION} Region only. ` : "All of Ghana. ") + "Districts not listed have no record; that does not mean the species is absent. " + $("cov-cite").textContent + " Tinga Lens, " + TL.site));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = `tinga-lens-${s[F.name].toLowerCase().replace(/[^a-z0-9]+/g, "-")}${REGION ? "-" + REGION.toLowerCase().replace(/ /g, "-") : ""}-by-district.csv`;
    document.body.append(a); a.click(); a.remove();
  });

  function openSpecies(i, scroll) {
    if (i == null || i < 0 || !SP[i]) return;
    const s = SP[i]; curSpecies = i;
    $("sx-hits").hidden = true; $("sx").hidden = false;
    history.replaceState(null, "", "#species=" + s[F.key]);
    Promise.all([PAIRS || getJSON("data/bio/pairs.json"), geo || getJSON("data/districts.geojson")]).then(([p, g]) => {
      PAIRS = p; geo = g; areas();
      const every = (p.species[i] || []).map(([d, n, last]) => ({ id: p.districts[d], n, last })).sort((a, b) => b.n - a.n);
      const rows = REGION ? every.filter(r => REG[r.id] === REGION) : every, here = rows.reduce((a, r) => a + r.n, 0);
      curRows = rows;
      $("sx-name").innerHTML = `<i>${esc(s[F.name])}</i>` + (s[F.common] ? ` <span style="font-weight:400;color:var(--muted)">${esc(s[F.common])}</span>` : "");
      $("sx-sub").innerHTML = esc(GROUPS[s[F.group]]);
      $("sx-facts").innerHTML = (REGION ? [[here.toLocaleString(), `records in ${REGION} Region`], [rows.length, `districts with records in ${REGION} Region`]] : [])
        .concat([[s[F.records].toLocaleString(), "records in Ghana"], [s[F.districts], "districts with records in Ghana"], [yr(s[F.first]), "earliest record in Ghana"], [yr(s[F.last]), "latest record in Ghana"]])
        .map(([v, t]) => `<div><b>${v}</b><span>${t}</span></div>`).join("");
      $("sx-rows").innerHTML = (rows.length ? "" : `<tr style="cursor:default"><td colspan="4">No record of this species in ${esc(REGION)} Region. Choose "All of Ghana" above the map to see where it has been recorded.</td></tr>`) + rows.map(r => `<tr data-id="${esc(r.id)}"><td>${esc(NAMES[r.id] || "")}</td><td>${esc(REG[r.id] || "")}</td><td class="num">${r.n.toLocaleString()}</td><td class="num">${yr(r.last)}</td></tr>`).join("");
      $("sx-links").innerHTML = `Districts are shaded by number of records. No shading means no record, not that the species is absent. `
        + `<a href="https://www.gbif.org/species/${s[F.key]}">Species page on GBIF</a>`
        + `. Positions in downloads from this site are rounded to about 11 km.`;
      // map: districts shaded by number of records
      const by = Object.fromEntries(rows.map(r => [r.id, r.n])), max = rows.length ? rows[0].n : 1;
      const cuts = max <= 3 ? [1, 2, 3] : [1, Math.ceil(max ** (1 / 3)), Math.ceil(max ** (2 / 3))], cols = ["#c7e9c0", "#74c476", "#238b45", "#00441b"];
      const shade = n => !n ? "#ffffff" : cols[n >= cuts[2] && max > 3 ? 3 : n >= cuts[1] ? 2 : n > cuts[0] ? 1 : 0];
      if (!smap) { smap = L.map("sp-map", { zoomSnap: 0.25, attributionControl: false, scrollWheelZoom: false }); }
      if (slayer) smap.removeLayer(slayer);
      const inReg = f => !REGION || REG[f.properties.shapeID] === REGION;
      slayer = L.geoJSON(g, {
        style: f => inReg(f) ? { fillColor: shade(by[f.properties.shapeID]), fillOpacity: by[f.properties.shapeID] ? 0.95 : 0.6, color: "#7d8a84", weight: 0.4 }
          : { fillColor: "#999", fillOpacity: 0.08, color: "#7d8a84", weight: 0.2 },
        onEachFeature: (f, l) => l.bindTooltip(`${f.properties.shapeName}: ${by[f.properties.shapeID] ? by[f.properties.shapeID].toLocaleString() + " records" : "no record"}`, { sticky: true }),
      }).addTo(smap);
      let b = null;
      slayer.eachLayer(l => { if (inReg(l.feature)) b = b ? b.extend(l.getBounds()) : L.latLngBounds(l.getBounds().getSouthWest(), l.getBounds().getNorthEast()); });
      smap.invalidateSize(); smap.fitBounds(b || slayer.getBounds(), { padding: [6, 6] });
      $("sx-legend").textContent = (REGION ? `Showing ${REGION} Region only. ` : "") + `Darker green: more records (up to ${max.toLocaleString()} in one district). White: no record.`;
      if (scroll) $("explorer").scrollIntoView({ behavior: "smooth" });
    });
  }
})();
