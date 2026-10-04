// Tinga Lens - biodiversity: species lists for a district, and the species explorer.
// Everything shown comes from the files in data/bio/, built by scripts/biodiversity.py.
(function () {
  const RL = { CR: "Critically Endangered", EN: "Endangered", VU: "Vulnerable", NT: "Near Threatened", LC: "Least Concern", DD: "Data Deficient", EX: "Extinct", EW: "Extinct in the Wild" };
  const THREAT = ["CR", "EN", "VU"];
  let SP = null, GROUPS = [], PAIRS = null, REG = {}, NAMES = {}, geo = null;
  let cur = null, shown = 50, smap = null, slayer = null;     // district list state, explorer map
  let REGION = "", curSpecies = null, curRows = [];                         // region chosen on the map above; species open in the explorer
  const HINT = "Click a district on the map to list the species recorded there.";
  const F = { key: 0, name: 1, common: 2, group: 3, iucn: 4, records: 5, districts: 6, first: 7, last: 8 };
  const rl = c => c && c !== "LC" && RL[c] ? `<span class="rl ${c}" title="IUCN Red List: ${RL[c]}">${RL[c]}</span>` : (c === "LC" ? "Least Concern" : "–");
  const nm = s => `<i>${esc(s[F.name])}</i>${s[F.common] ? `<small>${esc(s[F.common])}</small>` : ""}`;
  const yr = v => v == null ? "–" : v;

  $("bio").hidden = false;
  Promise.all([getJSON("data/bio/species.json"), getJSON("data/biodiversity.json"), getJSON("data/regions.json").catch(() => ({}))]).then(([sp, layer, reg]) => {
    SP = sp.rows; GROUPS = sp.groups; REG = reg;
    Object.entries(layer.districts).forEach(([id, x]) => NAMES[id] = x.name);
    $("bd-group").innerHTML = `<option value="">All groups</option>` + GROUPS.map((g, i) => `<option value="${i}">${esc(g)}</option>`).join("");
    const c = layer.coverage;
    if (!c.has_iucn) { $("bd-thr-wrap").hidden = true; $("sx-thr").hidden = true; }
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
    getJSON(`data/bio/districts/${id}.json`).then(d => { cur = { id, name, rows: d.rows }; }).catch(() => { cur = { id, name, rows: [] }; }).then(() => { shown = 50; drawDistrict(); });
  });
  document.addEventListener("tl:region", e => {
    REGION = e.detail.region;
    if (curSpecies != null) openSpecies(curSpecies);
    if (!REGION) { cur = null; $("bd").hidden = true; $("bd-hint").textContent = HINT; return; }
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
      shown = 50; drawDistrict();
    });
  });
  function filtered() {
    const q = $("bd-q").value.trim().toLowerCase(), g = $("bd-group").value, thr = $("bd-thr").checked;
    return cur.rows.filter(r => { const s = SP[r[0]];
      return (!g || s[F.group] === +g) && (!thr || THREAT.includes(s[F.iucn])) && (!q || s[F.name].toLowerCase().includes(q) || s[F.common].toLowerCase().includes(q)); });
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
      return `<tr data-s="${r[0]}"><td>${nm(s)}</td><td>${esc(GROUPS[s[F.group]])}</td><td>${rl(s[F.iucn])}</td><td class="num">${r[1].toLocaleString()}</td><td class="num">${r[2]}</td><td class="num">${yr(r[3])}</td><td class="num">${yr(r[4])}</td></tr>`; }).join("");
    $("bd-more").hidden = rows.length <= shown;
  }
  ["bd-q", "bd-group", "bd-thr"].forEach(id => $(id).addEventListener("input", () => { shown = 50; drawDistrict(); }));
  $("bd-more").addEventListener("click", () => { shown += 200; drawDistrict(); });
  $("bd-rows").addEventListener("click", e => { const tr = e.target.closest("tr[data-s]"); if (tr) openSpecies(+tr.dataset.s, true); });
  $("bd-csv").addEventListener("click", () => {
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lines = [[cur.region ? "Region" : "District", "Scientific name", "Common name", "Group", "IUCN Red List (global)", "Records", "Recorded places", "First year", "Latest year", "GBIF species key"].map(q).join(",")];
    filtered().forEach(r => { const s = SP[r[0]]; lines.push([cur.name, s[F.name], s[F.common], GROUPS[s[F.group]], RL[s[F.iucn]] || "", r[1], r[2], r[3], r[4], s[F.key]].map(q).join(",")); });
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
      return `<li data-s="${i}"><span><i>${esc(s[F.name])}</i>${s[F.common] ? ", " + esc(s[F.common]) : ""} ${THREAT.includes(s[F.iucn]) ? rl(s[F.iucn]) : ""}</span><span class="sub" style="margin:0;white-space:nowrap">${s[F.records].toLocaleString()} records</span></li>`; }).join("")
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
  $("sx-thr").addEventListener("click", () => {
    const list = SP.map((s, i) => i).filter(i => THREAT.includes(SP[i][F.iucn]));
    list.sort((a, b) => THREAT.indexOf(SP[a][F.iucn]) - THREAT.indexOf(SP[b][F.iucn]) || SP[b][F.records] - SP[a][F.records]);
    hits(list, "No threatened species among the records.");
  });
  $("sx-hits").addEventListener("click", e => { const li = e.target.closest("li[data-s]"); if (li) openSpecies(+li.dataset.s); });
  $("sx-rows").addEventListener("click", e => { const tr = e.target.closest("tr[data-id]"); if (tr && window.focusOn) { focusOn(tr.dataset.id); $("map").scrollIntoView({ behavior: "smooth", block: "center" }); } });

  $("sx-csv").addEventListener("click", () => {            // one species: a row for every district where it was recorded
    if (curSpecies == null) return;
    const s = SP[curSpecies], q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lines = [["Scientific name", "Common name", "Group", "IUCN Red List (global)", "District", "Region", "Records", "Latest year", "GBIF species key"].map(q).join(",")];
    curRows.forEach(r => lines.push([s[F.name], s[F.common], GROUPS[s[F.group]], RL[s[F.iucn]] || "", NAMES[r.id] || "", REG[r.id] || "", r.n, r.last, s[F.key]].map(q).join(",")));
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
      PAIRS = p; geo = g;
      const every = (p.species[i] || []).map(([d, n, last]) => ({ id: p.districts[d], n, last })).sort((a, b) => b.n - a.n);
      const rows = REGION ? every.filter(r => REG[r.id] === REGION) : every, here = rows.reduce((a, r) => a + r.n, 0);
      curRows = rows;
      $("sx-name").innerHTML = `<i>${esc(s[F.name])}</i>` + (s[F.common] ? ` <span style="font-weight:400;color:var(--muted)">${esc(s[F.common])}</span>` : "");
      $("sx-sub").innerHTML = `${esc(GROUPS[s[F.group]])}. IUCN Red List (global): ${s[F.iucn] ? rl(s[F.iucn]) : "not assessed or not supplied"}`;
      $("sx-facts").innerHTML = (REGION ? [[here.toLocaleString(), `records in ${REGION} Region`], [rows.length, `districts with records in ${REGION} Region`]] : [])
        .concat([[s[F.records].toLocaleString(), "records in Ghana"], [s[F.districts], "districts with records in Ghana"], [yr(s[F.first]), "earliest record in Ghana"], [yr(s[F.last]), "latest record in Ghana"]])
        .map(([v, t]) => `<div><b>${v}</b><span>${t}</span></div>`).join("");
      $("sx-rows").innerHTML = (rows.length ? "" : `<tr style="cursor:default"><td colspan="4">No record of this species in ${esc(REGION)} Region. Choose "All of Ghana" above the map to see where it has been recorded.</td></tr>`) + rows.map(r => `<tr data-id="${esc(r.id)}"><td>${esc(NAMES[r.id] || "")}</td><td>${esc(REG[r.id] || "")}</td><td class="num">${r.n.toLocaleString()}</td><td class="num">${yr(r.last)}</td></tr>`).join("");
      const threatened = THREAT.includes(s[F.iucn]);
      $("sx-links").innerHTML = `Districts are shaded by number of records. No shading means no record, not that the species is absent. `
        + `<a href="https://www.gbif.org/species/${s[F.key]}">Species page on GBIF</a>`
        + (threatened ? ". Record locations of threatened species are not linked from this site." : `, <a href="https://www.gbif.org/occurrence/search?country=GH&taxon_key=${s[F.key]}">individual records on GBIF</a>.`);
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
