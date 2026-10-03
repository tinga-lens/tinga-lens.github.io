// Tinga Lens - district profiles: every product for one district on one page.
(function () {
  const keys = Object.keys(TL.products);
  let layers = {}, geo = null, map = null, shapes = {}, current = null, REG = {}, all = null;

  Promise.all([getJSON("data/districts.geojson"), ...keys.map(k => getJSON(`data/${k}.json`).catch(() => null))]).then(([g, ...ls]) => {
    geo = g;
    keys.forEach((k, i) => { if (ls[i]) layers[k] = ls[i]; });
    const names = g.features.map(f => f.properties.shapeName).sort();
    const idOf = Object.fromEntries(g.features.map(f => [f.properties.shapeName, f.properties.shapeID]));
    const fill = () => {                                  // the district list follows the chosen region
      const r = $("region").value, list = names.filter(n => !r || REG[idOf[n]] === r);
      $("pick").innerHTML = `<option value="">Choose a district…</option>` + list.map(n => `<option>${esc(n)}</option>`).join("");
      if (current && list.includes(current.name)) $("pick").value = current.name;
    };
    fill();
    getJSON("data/regions.json").then(r => {
      REG = r;
      $("region").innerHTML += [...new Set(Object.values(r))].sort().map(n => `<option>${esc(n)}</option>`).join("");
      if (current) { $("region").value = REG[current.id] || ""; fill(); }
    }).catch(() => { $("region").hidden = true; document.querySelector('label[for="region"]').hidden = true; });
    $("region").addEventListener("change", () => {
      fill();
      const r = $("region").value; let b = null;
      Object.entries(shapes).forEach(([n, l]) => { if (!r || REG[idOf[n]] === r) b = b ? b.extend(l.getBounds()) : L.latLngBounds(l.getBounds().getSouthWest(), l.getBounds().getNorthEast()); });
      if (b && !(current && REG[current.id] === r)) map.fitBounds(b, { padding: [6, 6] });
    });

    map = L.map("mini", { zoomSnap: 0.25, attributionControl: false, scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 12, opacity: 0.45 }).addTo(map);
    all = L.geoJSON(g, {
      style: { fillColor: "#9fb0ad", fillOpacity: 0.25, color: "#55605c", weight: 0.5 },
      onEachFeature: (f, l) => { shapes[f.properties.shapeName] = l; l.bindTooltip(f.properties.shapeName, { sticky: true }); l.on("click", () => show(f.properties.shapeName)); },
    }).addTo(map);
    map.fitBounds(all.getBounds(), { padding: [6, 6] });

    const go = v => { const hit = names.find(n => n.toLowerCase() === v.trim().toLowerCase()); if (hit) show(hit); };
    $("pick").addEventListener("change", e => go(e.target.value));
    $("download").addEventListener("click", download);
    window.addEventListener("hashchange", () => go(decodeURIComponent(location.hash.slice(1))));
    go(decodeURIComponent(location.hash.slice(1)));
  }).catch(e => { $("profile").innerHTML = `<p class="sub">Could not load the data files: ${esc(e.message)}</p>`; });

  function entry(k, id) { const d = layers[k]; return d && d.districts[id] ? { d, x: d.districts[id] } : null; }

  function show(name) {
    const f = geo.features.find(x => x.properties.shapeName === name);
    if (!f) return;
    current = { name, id: f.properties.shapeID };
    history.replaceState(null, "", "#" + encodeURIComponent(name));
    if (REG[current.id] && $("region").value !== REG[current.id]) { $("region").value = REG[current.id]; $("region").dispatchEvent(new Event("change")); }
    $("pick").value = name;
    Object.values(shapes).forEach(l => l.setStyle({ fillColor: "#9fb0ad", fillOpacity: 0.25, color: "#55605c", weight: 0.5 }));
    shapes[name].setStyle({ fillColor: "#2D6A4F", fillOpacity: 0.7, color: "#111", weight: 2 }).bringToFront();
    map.fitBounds(shapes[name].getBounds().pad(2.2));
    $("dname").textContent = name;
    $("head").hidden = false;

    const modules = [...new Set(Object.values(TL.products).map(p => p.module))];
    $("profile").innerHTML = modules.map(m => {
      const cards = keys.filter(k => TL.products[k].module === m).map(k => {
        const p = TL.products[k], e = entry(k, current.id);
        if (!e) return `<div class="card"><div>${badge(p.status)}</div><h2>${esc(p.name)}</h2><p class="sub">No data for this district yet.</p></div>`;
        const c = e.d.categories.find(q => q.key === e.x.cat) || { color: "#bdbdbd", label: "" };
        return `<div class="card"><div>${badge(p.status)}</div><h2 style="margin-top:6px">${esc(p.name)}</h2>
          <div><span class="big">${esc(e.x.big)}</span><span class="pill" style="background:${c.color};color:${ink(c.color)}">${esc(c.label)}</span></div>
          <p class="sub">${esc(e.x.big_note)}</p>
          <dl>${e.x.rows.map(r => `<dt>${esc(r[0])}</dt><dd>${esc(r[1])}</dd>`).join("")}</dl>
          <p class="sub" style="margin:0">Updated ${esc(e.d.updated)} · version ${esc(p.version)} · <a href="${ROOT + p.page}#${k}">Open on the map</a></p></div>`;
      }).join("");
      return `<h2>${esc(m)}</h2><div class="profile">${cards}</div>`;
    }).join("") + Object.values(TL.planned).map(p =>
      `<h2>${esc(p.name)}</h2><div class="card"><span class="badge dev">In development</span><p class="sub" style="margin:8px 0 0">No ${esc(p.name.toLowerCase())} data is published yet. <a href="${ROOT + p.page}">See the plan</a>.</p></div>`).join("");
  }

  function download() {
    if (!current) return;
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lines = [["District", "Product", "Kind", "Rating", "Main figure", "What the figure means", "Detail", "Value", "Source", "Updated", "Product version"].map(q).join(",")];
    keys.forEach(k => {
      const p = TL.products[k], e = entry(k, current.id); if (!e) return;
      const c = e.d.categories.find(x => x.key === e.x.cat) || { label: "" };
      const head = [current.name, p.name, TL.status[p.status].label, c.label, e.x.big, e.x.big_note];
      const tail = [e.d.source, e.d.updated, p.version];
      (e.x.rows.length ? e.x.rows : [["", ""]]).forEach(r => lines.push(head.concat(r, tail).map(q).join(",")));
    });
    lines.push("", q("Tinga Lens, " + TL.site + ". Estimates from satellite, climate and model data; not official warnings."));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
    a.download = `tinga-lens-${current.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
})();
