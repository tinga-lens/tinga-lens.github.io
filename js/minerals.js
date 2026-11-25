// TingaLens - minerals and energy: documented mines, deposits, exploration projects and oil and gas fields.
// Everything shown comes from data/minerals.json, built by scripts/process_minerals.py from the USGS compilation.
(function () {
  const COLOR = { gold: "#C79A1B", oil_gas: "#3B3B3B", bauxite: "#B5532B", manganese: "#7A4FA3", diamond: "#2A8FBF",
                  iron: "#8C6A5A", lithium: "#2E9D6B", limestone: "#8E9A9E", salt: "#D96BA0", other: "#6B7B73" };
  const KIND = { facility: "Mine, plant or field", deposit: "Documented deposit", exploration: "Exploration project" };
  let DOC = null, PTS = [], LAB = {}, on = new Set(), geo = null, map, dLayer, mLayer, mk = {}, shapes = {};
  let sel = { res: null, kind: "", region: "", q: "", district: null }, shown = 40, rows = [];
  const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  const mgr = new Intl.NumberFormat("en");
  const lab = k => LAB[k] || k;
  const dot = c => `<i style="background:${c}"></i>`;

  function style(p) {         // facility: solid dot; deposit: ring; exploration: small, see-through
    const c = COLOR[p.res] || COLOR.other;
    if (p.kind === "facility") return { radius: 7, fillColor: c, color: "#fff", weight: 1.5, fillOpacity: 0.95 };
    if (p.kind === "deposit") return { radius: 7, fillColor: "#fff", color: c, weight: 3, fillOpacity: 0.9 };
    return { radius: 4.5, fillColor: c, color: c, weight: 1, fillOpacity: 0.45 };
  }

  function match(p) {
    if (!on.has(p.res) && !p.tags.some(t => on.has(t))) return false;
    if (sel.kind && p.kind !== sel.kind) return false;
    if (sel.region && p.region !== sel.region) return false;
    if (sel.district && p.d !== sel.district) return false;
    if (sel.q) {
      const t = sel.q.toLowerCase();
      if (![p.name, p.who, p.dn, p.commodity].some(s => String(s || "").toLowerCase().includes(t))) return false;
    }
    return true;
  }

  function redraw() {
    rows = PTS.filter(match);
    const keep = new Set(rows.map(p => p.id));
    Object.entries(mk).forEach(([id, m]) => { if (keep.has(id)) { if (!mLayer.hasLayer(m)) m.addTo(mLayer); } else mLayer.removeLayer(m); });
    shown = 40; drawList();
    Object.entries(shapes).forEach(([id, l]) => l.setStyle(dStyle(id)));
  }

  function drawList() {
    const sorted = rows.slice().sort((a, b) => a.name.localeCompare(b.name));
    const where = sel.district ? ` in ${esc((geo.features.find(f => f.properties.shapeID === sel.district) || { properties: {} }).properties.shapeName || "this district")}` : "";
    $("mn-count").innerHTML = `${mgr.format(rows.length)} of ${mgr.format(PTS.length)} records shown${where}. ` + (sel.district ? `<button class="btn" id="mn-clear" type="button">Show all of Ghana</button>` : "");
    const c = $("mn-clear"); if (c) c.onclick = () => { sel.district = null; redraw(); side(null); };
    $("mn-rows").innerHTML = sorted.slice(0, shown).map(p => `<tr data-id="${esc(p.id)}"><td><b>${esc(p.name)}</b></td><td>${dot(COLOR[p.res] || COLOR.other)} ${esc(p.commodity || lab(p.res))}</td><td>${esc(KIND[p.kind])}</td><td>${esc(p.status)}</td><td>${esc(p.dn || "Offshore")}</td><td>${esc(p.region || "")}</td></tr>`).join("")
      || `<tr style="cursor:default"><td colspan="6">No record matches these choices.</td></tr>`;
    $("mn-more").hidden = shown >= rows.length;
    $("mn-rows").querySelectorAll("tr[data-id]").forEach(tr => tr.onclick = () => open(tr.dataset.id, true));
  }

  function side(html) {
    $("mn-side").innerHTML = html || `<p class="sub" style="margin:0">Click a point on the map, or a row below, to see its details here. Click a district to see everything recorded in it.</p>`;
  }

  function open(id, pan) {
    const p = PTS.find(x => x.id === id); if (!p) return;
    const m = mk[id];
    if (pan && m) { map.setView(m.getLatLng(), Math.max(map.getZoom(), 9)); m.openTooltip(); }
    const rowsHtml = [["Resource", p.commodity || lab(p.res)], ["Record type", KIND[p.kind] + (p.type && p.type !== KIND[p.kind] ? ` (${p.type})` : "")],
      ["Status", p.status], [p.kind === "exploration" ? "Company" : "Operator", p.who], ["District", p.dn || "Offshore, outside every district"], ["Region", p.region],
      ["Notes", p.detail], ["Position", `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`], ["USGS record", p.id]].filter(r => r[1])
      .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
    side(`<div class="mn-detail"><h3>${esc(p.name)}</h3><span class="badge record">Published record</span><dl>${rowsHtml}</dl>
      <p class="sub" style="margin-top:10px">Source: USGS${p.src ? `, ${esc(p.src)}` : ""}. Released ${esc(DOC.release)}. This is a documented site, not a licence or boundary.</p></div>`);
  }

  function districtSide(id, name) {
    const here = PTS.filter(p => p.d === id);
    const by = {};
    here.forEach(p => { (by[p.res] = by[p.res] || { facility: 0, deposit: 0, exploration: 0 })[p.kind]++; });
    const body = Object.keys(by).length
      ? `<table class="sp"><thead><tr><th>Resource</th><th class="num">Mines, plants, fields</th><th class="num">Deposits</th><th class="num">Exploration</th></tr></thead><tbody>${
        Object.entries(by).map(([r, v]) => `<tr style="cursor:default"><td>${dot(COLOR[r])} ${esc(lab(r))}</td><td class="num">${v.facility}</td><td class="num">${v.deposit}</td><td class="num">${v.exploration}</td></tr>`).join("")}</tbody></table>`
      : `<p>No site is recorded in this district in the USGS compilation. That does not mean it has no minerals.</p>`;
    side(`<div class="mn-detail"><h3>${esc(name)}</h3><p class="sub" style="margin:0">${here.length} record${here.length === 1 ? "" : "s"} in this district</p>${body}
      <p class="sub" style="margin-top:10px">The three kinds of record overlap, so the columns are not added together.</p></div>`);
  }

  const dStyle = id => ({ fillColor: sel.district === id ? "#CFE3D6" : "#DDE3DD", fillOpacity: 0.55, color: "#7d8a84", weight: sel.district === id ? 2 : 0.6 });

  function csv() {
    const head = ["Site", "Resource", "Commodity", "Record type", "Status", "Operator or company", "District", "Region", "Latitude", "Longitude", "Notes", "USGS record id"];
    const lines = [head.map(q).join(",")].concat(rows.map(p => [p.name, lab(p.res), p.commodity, KIND[p.kind], p.status, p.who, p.dn || "Offshore", p.region, p.lat, p.lon, p.detail, p.id].map(q).join(",")));
    lines.push(q(`Source: ${DOC.source} ${DOC.doi} Released ${DOC.release}. Public domain. A documented record, not a complete inventory, licence or boundary. TingaLens, ${TL.site}`));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = "tingalens-minerals-and-energy.csv"; document.body.append(a); a.click(); a.remove();
  }


  // The map as a picture, drawn fresh (not copied from the screen) with the TingaLens name printed across it.
  function image() {
    const W = 1600, SERIF = '"Source Serif 4", Georgia, serif', SANS = '"Source Sans 3", Arial, sans-serif';
    let w = 180, e = -180, s = 90, n = -90;
    const ext = (lon, lat) => { w = Math.min(w, lon); e = Math.max(e, lon); s = Math.min(s, lat); n = Math.max(n, lat); };
    geo.features.forEach(f => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates).forEach(p => p[0].forEach(([lo, la]) => ext(lo, la))));
    PTS.forEach(p => ext(p.lon, p.lat));                         // keeps the offshore fields in the picture
    const k = Math.cos((n + s) / 2 * Math.PI / 180), aspect = (n - s) / ((e - w) * k);
    const shownRes = [...on].filter(r => rows.some(p => p.res === r || p.tags.includes(r)));
    const notes = ["A record of documented sites, not a complete inventory. A district or place with no point has no record here; it does not mean there are no minerals. Locations are those published by USGS and are not a licence, boundary or survey.",
                   "The three kinds of record overlap and are never added together. Offshore fields lie outside every district."];
    const NH = 30 * notes.reduce((a, t) => a + Math.ceil(t.length / 105), 0) + 30;
    const H = Math.round(260 + Math.max(Math.min(1060 * aspect, 1390), 80 + (shownRes.length + 4) * 60) + 250 + NH);
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const g = c.getContext("2d");
    g.fillStyle = "#ffffff"; g.fillRect(0, 0, W, H);
    const wrap = (text, x, y, maxW, lh) => {
      let line = "";
      for (const t of String(text).split(" ")) {
        if (g.measureText(line + t).width > maxW && line) { g.fillText(line.trim(), x, y); y += lh; line = ""; }
        line += t + " ";
      }
      g.fillText(line.trim(), x, y); return y + lh;
    };
    g.fillStyle = "#1B2B24"; g.textBaseline = "top";
    g.font = `600 54px ${SERIF}`; let y = wrap("Documented mineral and energy sites", 70, 60, W - 140, 62);
    const sub = `Records in the USGS compilation, ${DOC.release.slice(0, 4)} release` + (sel.region ? `. ${sel.region} Region` : "") + `. ${rows.length} of ${PTS.length} records shown`;
    g.font = `400 30px ${SANS}`; g.fillStyle = "#56655C"; y = wrap(sub, 70, y + 6, W - 140, 38);

    const top = y + 24, bottom = H - 250 - NH, left = 70, right = W - 470;
    const sc = Math.min((right - left) / ((e - w) * k), (bottom - top) / (n - s));
    const ox = left + ((right - left) - (e - w) * k * sc) / 2;
    const X = lon => ox + (lon - w) * k * sc, Y = lat => top + (n - lat) * sc;
    geo.features.forEach(f => {
      g.beginPath();
      (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates).forEach(p => p.forEach(ring => { ring.forEach(([lo, la], i) => i ? g.lineTo(X(lo), Y(la)) : g.moveTo(X(lo), Y(la))); g.closePath(); }));
      g.fillStyle = "#e9ece8"; g.fill("evenodd"); g.strokeStyle = "#8a948e"; g.lineWidth = 1; g.stroke();
    });
    const dotAt = (p, r, scale) => {
      const col = COLOR[p.res] || COLOR.other, x = X(p.lon), yy = Y(p.lat);
      g.beginPath(); g.arc(x, yy, r * scale, 0, 7);
      if (p.kind === "facility") { g.fillStyle = col; g.fill(); g.strokeStyle = "#fff"; g.lineWidth = 2; g.stroke(); }
      else if (p.kind === "deposit") { g.fillStyle = "#fff"; g.fill(); g.strokeStyle = col; g.lineWidth = 4; g.stroke(); }
      else { g.globalAlpha = 0.5; g.fillStyle = col; g.fill(); g.globalAlpha = 1; g.strokeStyle = col; g.lineWidth = 1.5; g.stroke(); }
    };
    ["exploration", "deposit", "facility"].forEach(kd => rows.filter(p => p.kind === kd).forEach(p => dotAt(p, kd === "exploration" ? 6 : 9, 1)));

    // the name, repeated across the map so cropping does not remove it
    g.save(); g.beginPath(); g.rect(left - 30, top - 10, right - left + 60, bottom - top + 20); g.clip();
    g.translate(W / 2, H / 2); g.rotate(-Math.PI / 6);
    g.font = `700 44px ${SANS}`; g.fillStyle = "rgba(27,43,36,0.13)"; g.textBaseline = "middle";
    for (let yy = -H; yy < H; yy += 190) for (let xx = -W; xx < W; xx += 520) g.fillText("TingaLens", xx + ((yy / 190) % 2 ? 260 : 0), yy);
    g.restore();

    // legend: resource colours, then the three kinds of record
    let ly = top + 10; const lx = W - 430;
    g.textBaseline = "top"; g.fillStyle = "#1B2B24"; g.font = `600 28px ${SANS}`; g.fillText("Resource", lx, ly); ly += 46;
    shownRes.forEach(r => {
      g.beginPath(); g.arc(lx + 17, ly + 17, 13, 0, 7); g.fillStyle = COLOR[r]; g.fill();
      g.fillStyle = "#1B2B24"; g.font = `400 26px ${SANS}`; g.fillText(lab(r), lx + 48, ly + 2); ly += 44;
    });
    ly += 20; g.font = `600 28px ${SANS}`; g.fillText("Kind of record", lx, ly); ly += 46;
    [["facility", "Mine, plant or field"], ["deposit", "Documented deposit"], ["exploration", "Exploration project"]].forEach(([kd, t]) => {
      const x0 = lx + 17, y0 = ly + 17, col = "#6B7B73";
      g.beginPath(); g.arc(x0, y0, kd === "exploration" ? 8 : 12, 0, 7);
      if (kd === "facility") { g.fillStyle = col; g.fill(); }
      else if (kd === "deposit") { g.fillStyle = "#fff"; g.fill(); g.strokeStyle = col; g.lineWidth = 4; g.stroke(); }
      else { g.globalAlpha = 0.5; g.fillStyle = col; g.fill(); g.globalAlpha = 1; g.strokeStyle = col; g.lineWidth = 1.5; g.stroke(); }
      g.fillStyle = "#1B2B24"; g.font = `400 26px ${SANS}`; g.fillText(t, lx + 48, ly + 2); ly += 44;
    });

    g.fillStyle = "#33433A"; g.font = `400 23px ${SANS}`; g.textBaseline = "top";
    let ny = bottom + 22; notes.forEach(t => { ny = wrap(t, 70, ny, W - 140, 30); });

    // footer: brand, source and terms
    const fy = H - 215;
    g.strokeStyle = "#D5DBCF"; g.lineWidth = 2; g.beginPath(); g.moveTo(70, fy); g.lineTo(W - 70, fy); g.stroke();
    g.save(); g.translate(70, fy + 26); g.scale(0.6, 0.6); g.lineCap = "round"; g.lineWidth = 10;
    g.strokeStyle = "#17252A"; g.beginPath(); g.arc(60, 60, 52, -Math.PI / 2, Math.PI, false); g.stroke();
    g.strokeStyle = "#2D6A4F"; g.beginPath(); g.arc(60, 60, 30, -Math.PI / 2, Math.PI, false); g.stroke();
    g.fillStyle = "#A98467"; g.beginPath(); g.arc(60, 60, 11, 0, 7); g.fill();
    g.fillStyle = "#277DA1"; g.beginPath(); g.arc(23, 23, 7, 0, 7); g.fill(); g.restore();
    g.textBaseline = "top"; g.fillStyle = "#1B2B24"; g.font = `700 40px ${SANS}`; g.fillText("TingaLens", 160, fy + 30);
    g.font = `400 24px ${SANS}`; g.fillStyle = "#56655C"; g.fillText(TL.site.replace("https://", ""), 160, fy + 76);
    g.font = `400 23px ${SANS}`;
    const ty = wrap(`Source: ${DOC.source} ${DOC.doi}. Released ${DOC.release}. Public domain. Boundaries: geoBoundaries (CC BY 4.0).`, 470, fy + 28, W - 540, 30);
    wrap("© TingaLens. You may share this image unchanged with credit. To use it without the TingaLens name, or in a product or publication, ask first: see the About page.", 470, ty + 4, W - 540, 30);

    c.toBlob(blob => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "tingalens-minerals-and-energy.png";
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }, "image/png");
  }

  Promise.all([getJSON("data/minerals.json"), getJSON("data/districts.geojson")]).then(([doc, g]) => {
    DOC = doc; PTS = doc.points; geo = g;
    doc.resources.forEach(r => LAB[r.key] = r.label);
    const present = doc.resources.filter(r => PTS.some(p => p.tags.includes(r.key)));
    present.forEach(r => on.add(r.key));
    $("mn").hidden = false;

    // resource chips
    $("mn-res").innerHTML = present.map(r => `<button type="button" class="chip" aria-pressed="true" data-k="${r.key}">${dot(COLOR[r.key])}${esc(r.label)}</button>`).join("");
    $("mn-res").querySelectorAll(".chip").forEach(b => b.onclick = () => {
      const k = b.dataset.k, solo = on.size === present.length;
      if (solo) { on = new Set([k]); } else if (on.has(k)) { on.delete(k); if (!on.size) present.forEach(r => on.add(r.key)); } else on.add(k);
      $("mn-res").querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", String(on.has(c.dataset.k))));
      redraw();
    });
    $("mn-kind").innerHTML += Object.entries(doc.kinds).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
    const regions = [...new Set(PTS.map(p => p.region).filter(Boolean))].sort();
    $("mn-region").innerHTML += regions.map(r => `<option>${esc(r)}</option>`).join("");
    $("mn-kind").onchange = e => { sel.kind = e.target.value; redraw(); };
    $("mn-region").onchange = e => { sel.region = e.target.value; sel.district = null; redraw(); };
    $("mn-q").oninput = e => { sel.q = e.target.value.trim(); redraw(); };
    $("mn-more").onclick = () => { shown += 40; drawList(); };
    $("mn-csv").onclick = csv; $("mn-png").onclick = image;

    // map
    map = L.map("mn-map", { zoomSnap: 0.25, attributionControl: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 17, maxNativeZoom: 17, opacity: 0.35 }).addTo(map);
    L.control.attribution({ prefix: false }).addAttribution("© OpenStreetMap contributors · Districts: geoBoundaries · Sites: USGS").addTo(map);
    dLayer = L.geoJSON(g, {
      style: f => dStyle(f.properties.shapeID),
      onEachFeature: (f, l) => {
        shapes[f.properties.shapeID] = l;
        l.bindTooltip(TL.clean(f.properties.shapeName), { sticky: true });
        l.on("click", () => { sel.district = f.properties.shapeID; redraw(); districtSide(f.properties.shapeID, TL.clean(f.properties.shapeName)); });
      },
    }).addTo(map);
    mLayer = L.layerGroup().addTo(map);
    PTS.forEach(p => {
      const m = L.circleMarker([p.lat, p.lon], style(p)).bindTooltip(`${esc(p.name)} · ${esc(p.commodity || lab(p.res))}`);
      m.on("click", e => { L.DomEvent.stopPropagation(e); open(p.id, false); });
      mk[p.id] = m;
    });
    const b = dLayer.getBounds(); PTS.forEach(p => b.extend([p.lat, p.lon]));
    map.fitBounds(b, { padding: [10, 10] });
    map.on("click", () => { if (sel.district) { sel.district = null; redraw(); } });

    $("mn-key").innerHTML = `<span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5.5" fill="#777" stroke="#fff" stroke-width="1.5"/></svg>Mine, plant or field</span>
      <span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="#fff" stroke="#777" stroke-width="3"/></svg>Documented deposit</span>
      <span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="3.5" fill="#777" fill-opacity=".45" stroke="#777"/></svg>Exploration project</span>`;

    // coverage
    const c = doc.counts;
    $("mn-facts").innerHTML = [[c.facility, "mines, plants and oil and gas fields"], [c.deposit, "documented deposits"], [c.exploration, "exploration projects"],
      [Object.keys(doc.districts).length + " of 260", "districts with a record"], [doc.release, "date of the USGS release"]]
      .map(([v, t]) => `<div><b>${typeof v === "number" ? mgr.format(v) : esc(v)}</b><span>${t}</span></div>`).join("");
    $("mn-cov").innerHTML = present.map(r => {
      const n = k => PTS.filter(p => p.kind === k && p.res === r.key).length;
      return `<tr style="cursor:default"><td>${dot(COLOR[r.key])} ${esc(r.label)}</td><td class="num">${n("facility")}</td><td class="num">${n("deposit")}</td><td class="num">${n("exploration")}</td></tr>`;
    }).join("");
    const off = PTS.filter(p => !p.d);
    $("mn-offshore").textContent = off.length ? `${off.length} records lie offshore or outside every district boundary (${off.map(p => p.name).join(", ")}). They are shown on the map and in the list as "Offshore" and are not counted in any district.` : "";
    $("mn-cite").innerHTML = `${esc(doc.source)} <a href="${esc(doc.doi)}">${esc(doc.doi)}</a>. Released ${esc(doc.release)}. ${esc(doc.licence)}.`;
    redraw();
  }).catch(e => { $("wait").hidden = false; $("wait-msg").textContent = "The minerals file could not be loaded: " + e.message; });
})();
