// Tinga Lens - district profiles: every product for one district on one page.
(function () {
  const keys = Object.keys(TL.products);
  let layers = {}, geo = null, map = null, shapes = {}, current = null, REG = {}, all = null, CEN = {};
  getJSON("data/centroids.json").then(c => { CEN = c; }).catch(() => {});

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
    $("card").addEventListener("click", () => makeCard(false));
    $("share").addEventListener("click", () => makeCard(true));
    // the Share button appears only where the device can share an image (phones, and some computers)
    try { $("share").hidden = !(navigator.canShare && navigator.canShare({ files: [new File([""], "x.png", { type: "image/png" })] })); } catch (e) { $("share").hidden = true; }
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

  // ---------- a single image of the district's key figures, sized for phone messaging apps ----------
  // Status colours on the card mean one thing only: how far from usual. Facts carry no colour.
  const TONE = { alert: "#B8502E", watch: "#D49A2A", usual: "#A9B5AD", wetter: "#2A6F8F", fact: null };
  const toneOf = cat => ({ very_dry: "alert", dry: "watch", normal: "usual", wet: "wetter", very_wet: "wetter",
    far_more: "alert", more: "watch", fewer: "usual", far_fewer: "usual", quiet: "usual",
    p5: "alert", p4: "alert", p3: "watch", p2: "usual", p1: "usual" }[cat] || "usual");
  const diff = x => Math.round(num(x.big)) - 100;
  const than = (x, more, less, same) => { const d = diff(x); return d === 0 ? same : d > 0 ? `${d}% ${more} than usual` : `${-d}% ${less} than usual`; };
  const FIRE = { far_more: "far more than usual", more: "more than usual", normal: "about the usual number", fewer: "fewer than usual", far_fewer: "far fewer than usual", quiet: "a quiet period" };
  const CARD = [   // [product, title, how to word the value, has a status colour]
    ["drought", "Rainfall", (x, lab) => num(x.big) === null ? lab : `${lab}: ${than(x, "more rain", "less rain", "the usual amount of rain")}`, true],
    ["soil", "Soil moisture", (x, lab) => num(x.big) === null ? lab : `${lab}: ${than(x, "wetter", "drier", "about the usual level")}`, true],
    ["vegetation", "Vegetation", (x, lab) => num(x.big) === null ? "Too cloudy to measure" : (x.cat === "normal" ? "Near normal: " : "") + than(x, "greener", "less green", "as green as usual").replace(/^./, c => x.cat === "normal" ? c : c.toUpperCase()), true],
    ["fires", "Fires in the last 30 days", x => num(x.big) ? `${x.big} fire${x.big === "1" ? "" : "s"} detected, ${FIRE[x.cat] || ""}`.replace(/, $/, "") : "No fires detected", true],
    ["firerisk", "Estimated chance of fire", (x, lab) => `${lab}: ${x.big} chance of a fire being detected`, true],
    ["forest", "Forest", x => `${x.big} of tree cover lost each year`, false],
    ["floodprone", "Flooding", x => x.big === "None" ? "No land seen flooded repeatedly" : `${x.big} of land flooded in 2 or more years`, false],
    ["urban", "Towns and buildings", x => num(x.big) === null ? x.big : `Built-up area has ${num(x.big) < 0 ? "shrunk" : "grown"} ${Math.abs(num(x.big)).toLocaleString()}% since 2000`, false],
    ["biodiversity", "Wildlife and plants", x => `${x.big} species recorded`, false],
  ];
  const when = e => (e.d.subtitle || "").split(",")[0].replace(/ against.*$/, "").replace(/^(\w+) (\d{4}) to (\w+) \2$/, "$1 to $3 $2");

  function drawCard() {
    const W = 1080, H = 1350, c = document.createElement("canvas"), g = c.getContext("2d");
    c.width = W; c.height = H;
    const sans = '"Source Sans 3", system-ui, sans-serif', serif = '"Source Serif 4", Georgia, serif';
    g.fillStyle = "#F2F4EE"; g.fillRect(0, 0, W, H);
    g.fillStyle = "#1D4534"; g.fillRect(0, 0, W, 300);
    // mark
    g.lineCap = "round"; g.lineWidth = 9;
    g.strokeStyle = "#F3F5F4"; g.beginPath(); g.arc(104, 92, 38, -Math.PI / 2, Math.PI); g.stroke();
    g.strokeStyle = "#74C69D"; g.beginPath(); g.arc(104, 92, 21, -Math.PI / 2, Math.PI); g.stroke();
    g.fillStyle = "#C9A98D"; g.beginPath(); g.arc(104, 92, 8, 0, 7); g.fill();
    g.textBaseline = "alphabetic";
    g.font = `700 44px "Sora", ${sans}`; g.fillStyle = "#F3F5F4"; g.fillText("Tinga", 162, 108);
    g.fillStyle = "#74C69D"; g.fillText("Lens", 162 + g.measureText("Tinga ").width, 108);
    // district name, shrunk to fit
    let size = 78; g.fillStyle = "#FFFFFF";
    do { g.font = `600 ${size}px ${serif}`; size -= 4; } while (g.measureText(current.name).width > W - 128 && size > 40);
    g.fillText(current.name, 64, 218);
    g.font = `400 34px ${sans}`; g.fillStyle = "#CFE3D6";
    g.fillText([REG[current.id] ? REG[current.id] + " Region" : "", "Ghana"].filter(Boolean).join(", "), 64, 268);

    const rows = CARD.map(([k, title, say, status]) => {
      const e = entry(k, current.id); if (!e || e.x.cat === "out" || e.x.big === "–" && k !== "vegetation") return null;
      const cat = e.d.categories.find(q => q.key === e.x.cat) || { label: "" };
      const unrated = num(e.x.big) === null && ["drought", "soil", "vegetation"].includes(k);
      return { title: title + (["drought", "soil", "vegetation"].includes(k) ? ", " + when(e) : ""), value: say(e.x, cat.label),
               tone: status ? (unrated ? "usual" : toneOf(e.x.cat)) : "fact" };
    }).filter(Boolean).slice(0, 8);
    const top = 348, step = Math.min(108, (H - top - 190) / Math.max(rows.length, 1));
    rows.forEach((r, i) => {
      const y = top + i * step;
      if (TONE[r.tone]) { g.fillStyle = TONE[r.tone]; g.beginPath(); g.roundRect(64, y - 14, 12, 82, 6); g.fill(); }
      else { g.fillStyle = "#D5DBCF"; g.beginPath(); g.roundRect(64, y - 14, 12, 82, 6); g.fill(); }
      g.font = `400 29px ${sans}`; g.fillStyle = "#56655C"; g.fillText(r.title, 104, y + 12);
      let size = 39; g.fillStyle = "#1B2B24";
      do { g.font = `600 ${size}px ${sans}`; size -= 2; } while (g.measureText(r.value).width > W - 168 && size > 26);
      g.fillText(r.value, 104, y + 60);
    });
    // what the colours mean
    const ky = H - 150; let kx = 64;
    g.font = `400 25px ${sans}`;
    [["alert", "Very unusual"], ["watch", "Unusual"], ["usual", "About usual"], ["wetter", "Wetter or greener"]].forEach(([t, label]) => {
      g.fillStyle = TONE[t]; g.beginPath(); g.roundRect(kx, ky - 20, 22, 22, 5); g.fill();
      g.fillStyle = "#56655C"; g.fillText(label, kx + 32, ky); kx += 32 + g.measureText(label).width + 30;
    });
    const dates = Object.values(layers).map(d => d.updated).sort(), d = dates[dates.length - 1] || "";
    g.fillStyle = "#1D4534"; g.fillRect(0, H - 118, W, 118);
    g.font = `600 34px ${sans}`; g.fillStyle = "#FFFFFF"; g.fillText("tingalens.org", 64, H - 66);
    g.font = `400 26px ${sans}`; g.fillStyle = "#CFE3D6";
    const [yy, mo, dd] = d.split("-").map(Number);
    const nice = yy ? `${dd} ${["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][mo - 1]} ${yy}` : d;
    g.fillText(`Data as of ${nice}. Estimates from satellite records, not an official warning.`, 64, H - 28);
    return c;
  }

  function makeCard(share) {
    if (!current) return;
    const fonts = document.fonts && document.fonts.load ? Promise.all(['600 60px "Source Serif 4"', '600 40px "Source Sans 3"', '400 30px "Source Sans 3"', '700 44px "Sora"'].map(f => document.fonts.load(f))).catch(() => {}) : Promise.resolve();
    fonts.then(() => drawCard().toBlob(blob => {
      const name = `tinga-lens-${current.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`;
      const save = () => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      };
      if (!share) return save();
      const file = new File([blob], name, { type: "image/png" });
      const link = `${TL.site}/pages/districts.html#${encodeURIComponent(current.name)}`;
      navigator.share({ files: [file], title: `${current.name}, Tinga Lens`, text: `${current.name}: environmental conditions from Tinga Lens. ${link}` })
        .catch(e => { if (e && e.name !== "AbortError") save(); });      // if sharing fails, fall back to a download
    }, "image/png"));
  }

  function download() {
    if (!current) return;
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lines = [["District", "District centre latitude", "District centre longitude", "Product", "Kind", "Rating", "Main figure", "What the figure means", "Detail", "Value", "Source", "Updated", "Product version"].map(q).join(",")];
    keys.forEach(k => {
      const p = TL.products[k], e = entry(k, current.id); if (!e) return;
      const c = e.d.categories.find(x => x.key === e.x.cat) || { label: "" };
      const head = [current.name, ...(CEN[current.id] || ["", ""]), p.name, TL.status[p.status].label, c.label, e.x.big, e.x.big_note];
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
