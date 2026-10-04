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
    // "At a glance": one plain sentence per product, built only from the published figures
    // "94%" of normal reads more easily as "6% below normal"
    const rel = x => { const p = Math.round(parseFloat(x.big)) - 100; return !isFinite(p) ? x.big + " of normal" : p === 0 ? "equal to normal" : `${Math.abs(p)}% ${p > 0 ? "above" : "below"} normal`; };
    // where this period ranks among the comparison years, taken from the published "… that were drier" row
    const rank = (x, more, less) => {
      const r = x.rows.find(q => /years that were (drier|less green)/i.test(q[0])); if (!r) return "";
      const m = /(about )?(\d+) of (\d+)/.exec(r[1]); if (!m) return "";
      const k = +m[2], n = +m[3], kind = /^Baseline/.test(r[0]) ? "baseline" : "earlier";
      return k * 2 >= n ? `; ${more} than ${m[1] || ""}${k} of ${n} ${kind} years` : `; ${less} than ${m[1] || ""}${n - k} of ${n} ${kind} years`;
    };
    const say = {
      drought: (x, lab, when) => `Rainfall over ${when} was ${lab} (${rel(x)}${rank(x, "wetter", "drier")}).`,
      soil: (x, lab, when) => `Soil moisture in ${when} was ${lab} (${rel(x)}${rank(x, "wetter", "drier")}).`,
      vegetation: (x, lab, when) => `Vegetation in ${when} was ${lab} (greenness ${rel(x)}${rank(x, "greener", "less green")}).`,
      fires: (x, lab, when) => `${x.big} fire detection${x.big === "1" ? "" : "s"}, ${when}; ${lab} for these dates.`,
      firerisk: (x, lab, when) => `Estimated chance of fire, ${when}: ${x.big} (${lab}). This is a model estimate.`,
      forest: x => `Tree cover: ${x.big} ${x.big_note}.`,
      flood: x => `Flooding, 2023 lower Volta event: ${x.big} ${x.big_note.split(",")[0]}.`,
      flood2020: x => `Flooding, 2020 northern event: ${x.big} ${x.big_note.split(",")[0]}.`,
      water: x => `Permanent surface water: ${x.big} between the 1980s and 2021.`,
      floodprone: x => `Flood-prone land: ${x.big} ${x.big_note.replace(/^of land /, "")}.`,
      floodhazard: x => `River flood hazard (model): ${x.big} ${x.big_note}.`,
      pressure: x => `Human modification of the land: ${x.big} on a scale from 0 to 1${(x.rows.find(r => r[0] === "Rank in Ghana") || [0, ""])[1] ? ", rank " + x.rows.find(r => r[0] === "Rank in Ghana")[1].split(" (")[0] + " in Ghana" : ""}.`,
      urban: x => `Built-up area grew ${x.big.replace("+", "")} between 2000 and 2020.`,
      biodiversity: x => `${x.big} species recorded, which reflects how much the district has been surveyed.`,
    };
    const glance = keys.map(k => {
      const e = entry(k, current.id); if (!e || !say[k]) return "";
      const c = e.d.categories.find(q => q.key === e.x.cat) || { label: "" };
      if ((k === "flood" || k === "flood2020") && e.x.cat === "out") return "";                       // the event did not cover this district
      const unrated = e.x.big === "–" || e.x.big === "None";
      const text = unrated ? `${TL.products[k].name}: ${c.label.toLowerCase()}.` : say[k](e.x, c.label.toLowerCase(), e.x.big_note.split(", ").slice(1).join(", "));
      return `<li>${esc(text)}</li>`;
    }).join("");
    $("profile").innerHTML = (glance ? `<h2>At a glance</h2><ul class="glance">${glance}</ul>` : "") + modules.map(m => {
      const cards = keys.filter(k => TL.products[k].module === m).map(k => {
        const p = TL.products[k], e = entry(k, current.id);
        if (!e) return `<div class="card"><div>${badge(p.status)}</div><h2>${esc(p.name)}</h2><p class="sub">No data for this district yet.</p></div>`;
        const c = e.d.categories.find(q => q.key === e.x.cat) || { color: "#bdbdbd", label: "" };
        return `<div class="card"><div>${badge(p.status)}</div><h2 style="margin-top:6px">${esc(p.name)}</h2>
          <div><span class="big">${esc(TL.relBig(e.x.big, e.x.big_note)[0])}</span><span class="pill" style="background:${c.color};color:${ink(c.color)}">${esc(c.label)}</span></div>
          <p class="sub">${esc(TL.relBig(e.x.big, e.x.big_note)[1])}</p>
          <dl>${e.x.rows.map(r => `<dt>${esc(r[0])}</dt><dd>${esc(TL.rel(r[1]))}</dd>`).join("")}</dl>
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
