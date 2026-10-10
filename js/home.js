// Tinga Lens - home page: current-conditions cards. Every number comes from the published layer files.
(function () {
  const load = k => getJSON(`data/${k}.json`).catch(() => null);
  const n = o => Object.values(o).reduce((a, b) => a + b, 0);
  const card = (kicker, title, href, body, status) => `<div class="stat">
      <h3><a href="${ROOT + href}">${esc(kicker)}</a></h3>${body}</div>`;
  const line = (fig, text) => `<div><span class="fig">${esc(fig)}</span><div class="sub" style="margin:0">${esc(text)}</div></div>`;

  Promise.all(["drought", "soil", "fires", "firerisk", "vegetation", "forest", "urban", "flood", "biodiversity", "pressure"].map(load)).then(([dr, so, fi, fr, ve, fo, ur, fl, bi, hp]) => {
    const out = [];

    // Drought: rainfall and soil moisture, districts drier than normal
    let body = "";
    if (dr) body += line(`${(dr.counts.dry || 0) + (dr.counts.very_dry || 0)} of ${n(dr.counts)}`, `districts drier than normal for rainfall, ${dr.subtitle}`);
    if (so) body += line(`${(so.counts.dry || 0) + (so.counts.very_dry || 0)} of ${n(so.counts)}`, `districts drier than normal for soil moisture, ${so.subtitle.split(",")[0]}`);
    out.push(card("Drought", "Rainfall and soil moisture", "pages/drought.html", body || line("–", "No data yet"), ["condition"]));

    // Fire: detections, and the experimental estimate
    body = "";
    if (fi) {
      const total = Object.values(fi.districts).reduce((a, x) => a + (num(x.big) || 0), 0);
      body += line(total.toLocaleString(), `fire detections, ${fi.subtitle.split(",")[0]}`);
      body += `<div class="sub" style="margin:0">${(fi.counts.more || 0) + (fi.counts.far_more || 0)} districts above their normal for these dates</div>`;
    }
    if (fr) body += `<div class="sub" style="margin:0">Model: ${(fr.counts.p4 || 0) + (fr.counts.p5 || 0)} districts with a high estimated chance of fire, ${esc(fr.subtitle)}</div>`;
    out.push(card("Fire", "Active fires and fire probability", "pages/fire.html", body || line("–", "No data yet"), fr ? ["observed", "model"] : ["observed"]));

    // Vegetation and forest
    body = "";
    if (ve) {
      const rated = n(ve.counts) - (ve.counts.cloud || 0);
      body += line(`${(ve.counts.dry || 0) + (ve.counts.very_dry || 0)} of ${rated}`, `rated districts less green than normal, ${ve.subtitle.split(",")[0]} (${ve.counts.cloud || 0} too cloudy to rate)`);
    }
    if (fo) {
      const years = fo.chart.x, last = years[years.length - 1];
      const ha = Object.values(fo.districts).reduce((a, x) => a + (x.v[x.v.length - 1] || 0), 0);
      body += line(Math.round(ha).toLocaleString() + " ha", `tree cover lost across Ghana in ${last}`);
    }
    out.push(card("Vegetation", "Vegetation and forest change", "pages/vegetation.html", body || line("–", "No data yet"), ["condition", "observed"]));

    // planned modules: no numbers until there is real data
    const soon = () => "";   // unpublished topics are left off the home page until they have data
    if (fl) {
      const hit = Object.values(fl.districts).filter(x => !["out", "f0"].includes(x.cat)), km = hit.reduce((a, x) => a + (num(x.big) || 0), 0);
      out.push(card("Flood", "Observed flooding", "pages/flood.html", line(Math.round(km).toLocaleString() + " km²", `of land seen flooded in ${hit.length} districts. Past event: ${fl.subtitle}`)
        + `<div class="sub" style="margin:0">Not a live flood map.</div>`, ["observed"]));
    } else out.push(soon("Flood", "Flooding and susceptibility", "pages/flood.html", "Satellite-observed flooding and flood-prone landscapes. No data is published yet."));
    if (hp) {
      const v = Object.values(hp.districts), xs = hp.chart.x, mean = j => v.reduce((a, x) => a + x.v[j], 0) / v.length;
      let b = line(mean(xs.length - 1).toFixed(2), `average human modification across districts in ${xs[xs.length - 1]} (0 to 1), up from ${mean(0).toFixed(2)} in ${xs[0]}`);
      if (ur) { const us = ur.chart.x, sum = j => Object.values(ur.districts).reduce((a, x) => a + (x.v[j] || 0), 0);
        b += line(Math.round(sum(us.length - 1)).toLocaleString() + " km²", `built-up area in ${us[us.length - 1]}, up ${Math.round((sum(us.length - 1) / sum(0) - 1) * 100)}% since ${us[0]}`); }
      out.push(card("Human pressure", "Human pressure", "pages/pressure.html", b, ["index"]));
    } else if (ur) {
      const xs = ur.chart.x, sum = j => Object.values(ur.districts).reduce((a, x) => a + (x.v[j] || 0), 0), a0 = sum(0), a1 = sum(xs.length - 1);
      out.push(card("Urban", "Urban growth", "pages/pressure.html", line(Math.round(a1).toLocaleString() + " km²", `built-up area across Ghana in ${xs[xs.length - 1]}, up ${Math.round((a1 / a0 - 1) * 100)}% since ${xs[0]}`)
        + `<div class="sub" style="margin:0">Exposure to flooding is not published yet.</div>`, ["observed"]));
    } else out.push(soon("Urban", "Urban exposure", "pages/pressure.html", "Where people and new development meet environmental hazards. No data is published yet."));
    if (bi && bi.coverage) out.push(card("Biodiversity", "Recorded species", "pages/biodiversity.html",
      line(bi.coverage.species.toLocaleString(), `species recorded in Ghana, from ${bi.coverage.records.toLocaleString()} records`), ["observed"]));
    $("cards").innerHTML = out.filter(Boolean).join("");
  });

  getJSON("data/site.json").then(s => {
    if (s.signup_url) { $("signup").href = s.signup_url; $("signup").hidden = false; }
  }).catch(() => {});
})();

// Under the home map: a pointer to the topic's own page, which has the tools the home map leaves out.
(function () {
  const extra = {
    biodiversity: "The species list for each district, the species explorer and the species downloads are on the",
  };
  document.addEventListener("tl:layer", e => {
    const p = TL.products[e.detail.key], el = document.getElementById("more");
    if (!p || !el) return;
    el.innerHTML = `${extra[e.detail.key] || "More detail and the notes for this map are on the"} <a href="${ROOT + p.page}#${e.detail.key}">${esc(p.module)} page</a>.`;
    el.hidden = false;
  });
})();

// "This month in Ghana": the first sentence of each section of the brief
(function () {
  if (!window.TLbrief || !document.getElementById("teaser")) return;
  TLbrief.load().then(b => {
    if (!b.sections.length) return;
    $("teaser-list").innerHTML = b.sections.slice(0, 3).map(s => `<li><strong>${esc(s.title)}, ${esc(s.when.split(",")[0])}:</strong> ${esc(s.paras[s.paras.length > 2 && /could be rated/.test(s.paras[0]) ? 1 : 0])}</li>`).join("");
    $("teaser-date").textContent = "Data as of " + TLbrief.niceDate(b.updated) + ".";
    $("teaser").hidden = false;
  }).catch(() => {});
})();
