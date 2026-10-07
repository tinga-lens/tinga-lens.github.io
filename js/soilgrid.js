// Soil values across Ghana on a 1 km grid, shown under the district outlines on the Agriculture page.
// For each soil layer data/soilgrid/<key>.png (grey image) and .json (extent, low and high values) are read; if they are missing nothing changes.
(function () {
  const ROOT = document.documentElement.dataset.root || "";
  const RAMP = ["#f3f6ec", "#d9e8bf", "#a9d28f", "#62ac66", "#2a7a4b", "#14462e"];
  let useGrid = true, overlay = null, popup = null, token = 0;

  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  function colour(t) {                                   // 0..1 along the ramp
    const x = Math.min(Math.max(t, 0), 1) * (RAMP.length - 1), i = Math.min(Math.floor(x), RAMP.length - 2), f = x - i;
    const a = hex(RAMP[i]), b = hex(RAMP[i + 1]);
    return a.map((v, k) => Math.round(v + (b[k] - v) * f));
  }
  const fmt = (v, dec) => v.toLocaleString("en-GB", { minimumFractionDigits: dec, maximumFractionDigits: dec });

  function clear() {
    if (overlay) { map.removeLayer(overlay); overlay = null; }
    if (popup) { map.closePopup(popup); popup = null; }
    map.off("click", onClick);
    const box = document.getElementById("gridbox"); if (box) box.remove();
  }

  let cur = null;                                        // { meta, values (Uint8Array), w, h }
  function onClick(e) {
    if (!cur) return;
    const [[s, w], [n, ea]] = cur.meta.bounds;
    const col = Math.floor((e.latlng.lng - w) / (ea - w) * cur.w), row = Math.floor((n - e.latlng.lat) / (n - s) * cur.h);
    if (col < 0 || row < 0 || col >= cur.w || row >= cur.h) return;
    const q = cur.values[row * cur.w + col];
    if (!q) return;
    const m = cur.meta, v = m.low + (q - 1) / 254 * (m.high - m.low);
    const edge = q === 1 ? "at or below " : q === 255 ? "at or above " : "";
    const unit = m.unit ? " " + m.unit : "";
    popup = L.popup({ autoPan: false, className: "gridpop" }).setLatLng(e.latlng)
      .setContent(`<b>${edge}${fmt(v, m.dec)}${unit}</b><br><span>${m.short}, about 1 km around here (model estimate)</span>`).openOn(map);
  }

  TL.afterRender = function (key, d) {
    const mine = ++token;
    clear();
    cur = null;
    if (!(TL.products[key] || {}).group || (TL.products[key] || {}).group !== "soilprops") { restyle(false); return; }
    fetch(`${ROOT}data/soilgrid/${key}.json`).then(r => { if (!r.ok) throw 0; return r.json(); }).then(meta => {
      if (mine !== token) return;
      const holder = document.getElementById("legend");
      const box = document.createElement("div");
      box.id = "gridbox"; box.className = "gridbox";
      box.innerHTML = `<label><input type="checkbox" id="gridon" ${useGrid ? "checked" : ""}> Show values across Ghana (1 km grid)</label>`;
      holder.parentNode.insertBefore(box, holder);
      box.querySelector("input").addEventListener("change", e => { useGrid = e.target.checked; render(key, d); });
      if (!useGrid) { restyle(false); return; }
      const img = new Image();
      img.onload = () => {
        if (mine !== token) return;
        const c = document.createElement("canvas"); c.width = img.width; c.height = img.height;
        const g = c.getContext("2d"); g.drawImage(img, 0, 0);
        const px = g.getImageData(0, 0, c.width, c.height), vals = new Uint8Array(c.width * c.height);
        for (let i = 0; i < vals.length; i++) {
          const q = px.data[i * 4];
          vals[i] = q;
          if (!q) { px.data[i * 4 + 3] = 0; continue; }
          const [r, gg, b] = colour((q - 1) / 254);
          px.data[i * 4] = r; px.data[i * 4 + 1] = gg; px.data[i * 4 + 2] = b; px.data[i * 4 + 3] = 235;
        }
        g.putImageData(px, 0, 0);
        if (!map.getPane("soilgrid")) { map.createPane("soilgrid"); map.getPane("soilgrid").style.zIndex = 350; map.getPane("soilgrid").style.pointerEvents = "none"; }
        overlay = L.imageOverlay(c.toDataURL(), meta.bounds, { pane: "soilgrid", interactive: false }).addTo(map);
        overlay.getElement().style.imageRendering = "auto";
        cur = { meta, values: vals, w: c.width, h: c.height };
        map.on("click", onClick);
        restyle(true);
        const unit = meta.unit ? " " + meta.unit : "";
        const lg = document.getElementById("legend");
        lg.innerHTML = `<li class="gridleg"><span class="bar" style="background:linear-gradient(90deg,${RAMP.join(",")})"></span>
          <span class="lab"><span>${fmt(meta.low, meta.dec)}${unit} or less</span><span>${fmt(meta.high, meta.dec)}${unit} or more</span></span></li>
          <li class="gridnote">Each cell is about 1 km. Click the map for the value at that spot. District outlines are kept; click one for its district average.</li>`;
        document.getElementById("bar").innerHTML = "";
        const cr = document.getElementById("foot-layer");
        if (cr) cr.innerHTML += ` Grid: ${meta.source}.`;
      };
      img.src = `${ROOT}data/soilgrid/${key}.png?v=${meta.updated}`;
    }).catch(() => restyle(false));
  };

  function restyle(on) {                                 // with the grid on, the districts are outlines only
    if (typeof geoLayer === "undefined" || !geoLayer) return;
    if (on) geoLayer.eachLayer(l => l.setStyle({ fillOpacity: 0 }));
  }
})();
