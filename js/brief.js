// Tinga Lens - "This month in Ghana": a short brief written from the published layer files.
// Every sentence is assembled from figures already on the maps. Nothing is estimated or invented here.
window.TLbrief = (function () {
  const num = s => { const v = parseFloat(String(s).replace(/,/g, "")); return isNaN(v) ? null : v; };
  const list = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
  const plural = (n, one, many) => `${n.toLocaleString()} ${n === 1 ? one : many}`;
  const count = (d, cats, back) => Object.values(d.districts).filter(x => cats.includes(back ? (x.c || [])[(x.c || []).length - 1 - back] : x.cat)).length;
  const rel = pct => { const p = Math.round(pct) - 100; return p === 0 ? "equal to normal" : `${Math.abs(p)}% ${p > 0 ? "above" : "below"} normal`; };
  const where = (rows, REG) => {                      // "Northern (6), Oti (4)": the regions holding most of a set of districts
    const by = {};
    rows.forEach(([id]) => { const r = REG[id] || "another region"; by[r] = (by[r] || 0) + 1; });
    return Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([r, n]) => `${r} (${n})`);
  };
  const change = (now, before, what) => before == null ? "" : now === before ? ` That is the same number as the month before.`
    : ` That is ${now > before ? "up" : "down"} from ${before} the month before.`;

  // one "anomaly" product: rainfall, soil moisture or vegetation
  function anomaly(d, REG, o) {
    if (!d) return null;
    const E = Object.entries(d.districts), n = k => E.filter(([, x]) => x.cat === k).length;
    const vd = n("very_dry"), dr = n("dry"), wet = n("wet") + n("very_wet"), rated = E.filter(([, x]) => num(x.big) !== null).length;
    const low = E.filter(([, x]) => x.cat === "very_dry").sort((a, b) => num(a[1].big) - num(b[1].big));
    const paras = [];
    if (o.rated) paras.push(`${rated} of ${E.length} districts could be rated; the rest were hidden by cloud.`);
    paras.push(`${plural(vd, "district was", "districts were")} ${o.very} and ${dr} ${o.some}, while ${wet} ${wet === 1 ? "was" : "were"} ${o.high}.`
      + change(vd, (E[0][1].c || []).length > 1 ? count(d, ["very_dry"], 1) : null));
    if (low.length) paras.push(`${low.length === 1 ? "It is" : "Most of them are"} in ${list(where(low, REG))}.`);
    else paras.push(`No district was ${o.very}.`);
    return { key: o.key, title: o.title, when: d.subtitle, paras,
             items: low.slice(0, 5).map(([id, x]) => [x.name, REG[id] || "", rel(num(x.big))]), head: o.head };
  }

  function fires(d, REG) {
    if (!d) return null;
    const E = Object.entries(d.districts), total = E.reduce((a, [, x]) => a + (num(x.big) || 0), 0);
    const normal = E.reduce((a, [, x]) => a + (num(((x.rows || []).find(r => /^Normal/.test(r[0])) || [])[1]) || 0), 0);
    const far = E.filter(([, x]) => x.cat === "far_more").sort((a, b) => num(b[1].big) - num(a[1].big));
    const paras = [`Satellites recorded ${plural(Math.round(total), "fire", "fires")} across Ghana, against about ${Math.round(normal).toLocaleString()} usually seen on these dates.`];
    paras.push(far.length ? `${plural(far.length, "district", "districts")} had far more fires than usual, mostly in ${list(where(far, REG))}.`
      : "No district had far more fires than usual.");
    return { key: "fires", title: "Fires", when: d.subtitle, paras, head: "Most fires among them",
             items: far.slice(0, 5).map(([id, x]) => [x.name, REG[id] || "", plural(num(x.big), "detection", "detections")]) };
  }

  function risk(d, REG) {
    if (!d) return null;
    const E = Object.entries(d.districts), high = E.filter(([, x]) => ["p4", "p5"].includes(x.cat)).sort((a, b) => num(b[1].big) - num(a[1].big));
    const paras = [high.length ? `The model put the chance of at least one fire at "high" or "very high" in ${plural(high.length, "district", "districts")}, mostly in ${list(where(high, REG))}.`
      : "The model did not put any district in the \"high\" or \"very high\" class.", "This is a statistical estimate, not an observation."];
    return { key: "firerisk", title: "Chance of fire", when: d.subtitle, paras, head: "Highest estimates",
             items: high.slice(0, 5).map(([id, x]) => [x.name, REG[id] || "", x.big]) };
  }

  function build(L, REG) {
    const out = [
      anomaly(L.drought, REG, { key: "drought", title: "Rainfall", very: "very dry", some: "dry", high: "wetter than normal", head: "Driest districts" }),
      anomaly(L.soil, REG, { key: "soil", title: "Soil moisture", very: "very dry", some: "dry", high: "wetter than normal", head: "Driest districts" }),
      fires(L.fires, REG), risk(L.firerisk, REG),
      anomaly(L.vegetation, REG, { key: "vegetation", title: "Vegetation", very: "much less green than normal", some: "less green", high: "greener than normal", head: "Furthest below normal", rated: true }),
    ].filter(Boolean);
    const dates = Object.values(L).filter(Boolean).map(d => d.updated).sort();
    return { sections: out, updated: dates[dates.length - 1] || "" };
  }

  const niceDate = iso => { const [y, m, d] = iso.split("-").map(Number); return `${d} ${["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][m - 1]} ${y}`; };

  function text(b) {                                   // the brief as plain text, for copying into a message
    return [`Tinga Lens: this month in Ghana (data as of ${niceDate(b.updated)})`, ""].concat(b.sections.flatMap(s =>
      [`${s.title.toUpperCase()} (${s.when})`, ...s.paras, ...(s.items.length ? [s.head + ": " + s.items.map(i => `${i[0]}${i[1] ? ", " + i[1] : ""} (${i[2]})`).join("; ") + "."] : []), ""]),
      ["Estimates from satellite and climate records. Not an official warning.", "https://tingalens.org/pages/brief.html"]).join("\n");
  }

  const load = () => Promise.all(["drought", "soil", "fires", "firerisk", "vegetation"].map(k => getJSON(`data/${k}.json`).catch(() => null))
    .concat([getJSON("data/regions.json").catch(() => ({}))]))
    .then(([drought, soil, fires_, firerisk, vegetation, REG]) => build({ drought, soil, fires: fires_, firerisk, vegetation }, REG));

  // the brief as one image (1080 x 1350), sized for phone messaging apps
  function image(b) {
    const W = 1080, H = 1350, c = document.createElement("canvas"), g = c.getContext("2d");
    c.width = W; c.height = H;
    if (!g.roundRect) g.roundRect = function (x, y, w, h) { this.rect(x, y, w, h); };
    const sans = '"Source Sans 3", system-ui, sans-serif', serif = '"Source Serif 4", Georgia, serif';
    g.fillStyle = "#F2F4EE"; g.fillRect(0, 0, W, H);
    g.fillStyle = "#1D4534"; g.fillRect(0, 0, W, 270);
    g.lineCap = "round"; g.lineWidth = 9;
    g.strokeStyle = "#F3F5F4"; g.beginPath(); g.arc(104, 92, 38, -Math.PI / 2, Math.PI); g.stroke();
    g.strokeStyle = "#74C69D"; g.beginPath(); g.arc(104, 92, 21, -Math.PI / 2, Math.PI); g.stroke();
    g.fillStyle = "#C9A98D"; g.beginPath(); g.arc(104, 92, 8, 0, 7); g.fill();
    g.font = `700 44px "Sora", ${sans}`; g.fillStyle = "#F3F5F4"; g.fillText("Tinga", 162, 108);
    g.fillStyle = "#74C69D"; g.fillText("Lens", 162 + g.measureText("Tinga ").width, 108);
    g.font = `600 70px ${serif}`; g.fillStyle = "#FFFFFF"; g.fillText("This month in Ghana", 64, 205);
    g.font = `400 30px ${sans}`; g.fillStyle = "#CFE3D6"; g.fillText(`Data as of ${niceDate(b.updated)}`, 64, 247);
    const wrap = (t, w, max) => {
      const words = t.split(" "), lines = []; let cur = "";
      words.forEach(x => { const n = cur ? cur + " " + x : x; if (g.measureText(n).width > w && cur) { lines.push(cur); cur = x; } else cur = n; });
      if (cur) lines.push(cur);
      if (lines.length > max) { lines.length = max; lines[max - 1] = lines[max - 1].replace(/[ ,;.]*\S*$/, "") + "…"; }
      return lines;
    };
    let y = 330;
    b.sections.slice(0, 5).forEach(s => {
      g.fillStyle = "#2D6A4F"; g.beginPath(); g.roundRect(64, y - 28, 10, 150, 5); g.fill();
      g.font = `600 36px ${sans}`; g.fillStyle = "#1B2B24"; g.fillText(`${s.title}  `, 98, y);
      const tw = g.measureText(`${s.title}  `).width;
      g.font = `400 26px ${sans}`; g.fillStyle = "#56655C"; g.fillText(s.when, 98 + tw, y);
      g.font = `400 29px ${sans}`; g.fillStyle = "#33433A";
      wrap(s.paras[0], W - 170, 3).forEach((l, i) => g.fillText(l, 98, y + 44 + i * 38));
      y += 190;
    });
    g.fillStyle = "#1D4534"; g.fillRect(0, H - 118, W, 118);
    g.font = `600 34px ${sans}`; g.fillStyle = "#FFFFFF"; g.fillText("tingalens.org/pages/brief.html", 64, H - 66);
    g.font = `400 26px ${sans}`; g.fillStyle = "#CFE3D6"; g.fillText("Estimates from satellite and climate records, not an official warning.", 64, H - 28);
    return c;
  }

  return { load, text, niceDate, image };
})();
