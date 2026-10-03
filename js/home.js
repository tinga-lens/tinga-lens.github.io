// Tinga Lens - home page: current-conditions cards. Every number comes from the published layer files.
(function () {
  const load = k => getJSON(`data/${k}.json`).catch(() => null);
  const n = o => Object.values(o).reduce((a, b) => a + b, 0);
  const card = (kicker, title, href, body, status) => `<a class="card mod" href="${ROOT + href}">
      <span class="k">${esc(kicker)}</span><h3>${esc(title)}</h3>${body}
      <span>${status.map(badge).join(" ")}</span><span class="go">Explore ${esc(kicker.toLowerCase())} →</span></a>`;
  const line = (fig, text) => `<div><span class="fig">${esc(fig)}</span><div class="sub" style="margin:0">${esc(text)}</div></div>`;

  Promise.all(["drought", "soil", "fires", "firerisk", "vegetation", "forest", "urban"].map(load)).then(([dr, so, fi, fr, ve, fo, ur]) => {
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
    const soon = (k, title, href, text) => `<a class="card mod" href="${ROOT + href}"><span class="k">${k}</span><h3>${title}</h3>
      <div class="sub" style="margin:0">${text}</div><span><span class="badge dev">In development</span></span><span class="go">See the plan →</span></a>`;
    out.push(soon("Flood", "Flooding and susceptibility", "pages/flood.html", "Satellite-observed flooding and flood-prone landscapes. No data is published yet."));
    if (ur) {
      const xs = ur.chart.x, sum = j => Object.values(ur.districts).reduce((a, x) => a + (x.v[j] || 0), 0), a0 = sum(0), a1 = sum(xs.length - 1);
      out.push(card("Urban", "Urban growth", "pages/urban.html", line(Math.round(a1).toLocaleString() + " km²", `built-up area across Ghana in ${xs[xs.length - 1]}, up ${Math.round((a1 / a0 - 1) * 100)}% since ${xs[0]}`)
        + `<div class="sub" style="margin:0">Exposure to flooding is not published yet.</div>`, ["observed"]));
    } else out.push(soon("Urban", "Urban exposure", "pages/urban.html", "Where people and new development meet environmental hazards. No data is published yet."));
    $("cards").innerHTML = out.join("");
  });

  getJSON("data/site.json").then(s => {
    if (s.signup_url) { $("signup").href = s.signup_url; $("signup").hidden = false; }
  }).catch(() => {});
})();
