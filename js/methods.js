// Tinga Lens - Data & Methods page. Text for each product comes from the product's own data file,
// so the page always describes the version that is actually published.
(function () {
  const keys = Object.keys(TL.products);
  const formula = {
    drought: "percent of normal = rainfall over 3 months ÷ average for the same 3 months in 1991–2020 × 100\nrank = share of the 1991–2020 years that were drier\nVery dry: rank ≤ 10%   Dry: ≤ 30%   Near normal: 30–70%   Wet: ≥ 70%   Very wet: ≥ 90%",
    soil: "percent of normal = root-zone soil moisture ÷ average for the same month in other years × 100\nrank = share of other years that were drier\nVery dry: rank ≤ 10%   Dry: ≤ 30%   Near normal: 30–70%   Wet: ≥ 70%   Very wet: ≥ 90%",
    vegetation: "NDVI = (near-infrared − red) ÷ (near-infrared + red)\npercent of normal = district NDVI ÷ average for the same month in other years × 100\nrank = share of other years that were less green",
    fires: "percent of normal = detections in the last 30 days ÷ average for the same dates in earlier years × 100\nQuiet: fewer than 3 detections both now and normally",
    firerisk: "P(fire) = 1 ÷ (1 + exp(−z))\nz = b0 + b1·season + b2·surface moisture anomaly + b3·surface drying anomaly (+ further terms if they improve the test score)\nfire = at least one detection in the district in the next 5 days\nseason = how often the district had a fire on those dates in other years (as log-odds)",
    flood: "flooded area = number of 20 m pixels marked flooded on at least one pass × 400 m²\nflooded = radar shows water where the reference water map has none",
    biodiversity: "recorded species = number of different species with at least one GBIF record inside the district\nthreatened = IUCN Red List category Critically Endangered, Endangered or Vulnerable",
    pressure: "district value = average of the 300 m human modification index over the district, each cell weighted by its area\nrank = position among Ghana's 260 districts, 1 being the most modified\nclasses = fifths of that ranking",
    pressurechange: "change = district value in 2020 − district value in 1990\nclasses = fifths of Ghana's districts ranked by change",
    urban: "growth = (built-up area in 2020 ÷ built-up area in 2000 − 1) × 100\nbuilt-up area = ground covered by buildings, summed over the district from 1 km cells",
    forest: "loss rate = average tree cover lost per year over the last 3 years ÷ tree cover in 2000 × 100\ntree cover = 30 m pixels with at least 30% canopy taller than 5 m",
  };
  const pct = v => (v * 100).toFixed(1) + "%";

  Promise.all([...keys.map(k => getJSON(`data/${k}.json`).catch(() => null)), getJSON("data/firerisk_report.json").catch(() => null)]).then(res => {
    const report = res.pop(), L = Object.fromEntries(keys.map((k, i) => [k, res[i]]));

    $("products").innerHTML = keys.map(k => { const p = TL.products[k], d = L[k]; return `<tr>
      <td><a href="#m-${k}">${esc(p.name)}</a></td><td>${esc(p.module)}</td><td>${badge(p.status)}</td><td>${esc(p.source)}</td>
      <td>${esc(p.resolution)}</td><td>${esc(p.updates)}</td><td>${esc(p.baseline)}</td><td>${esc(p.version)}</td><td style="white-space:nowrap">${d ? esc(d.updated) : "–"}</td></tr>`; }).join("")
      + Object.values(TL.planned).map(p => `<tr><td><a href="${ROOT + p.page}">${esc(p.name)}</a></td><td>${esc(p.name)}</td><td><span class="badge dev">In development</span></td><td colspan="6">No data published yet</td></tr>`).join("");

    $("sections").innerHTML = keys.map(k => { const p = TL.products[k], d = L[k]; return `<h3 id="m-${k}" style="margin:26px 0 6px">${esc(p.name)} ${badge(p.status)}</h3>
      <p class="sub">${esc(p.module)} · ${esc(p.type)} · version ${esc(p.version)} · <a href="${ROOT + p.page}#${k}">open the map</a></p>
      ${d ? `<p>${esc(d.how)}</p>` : `<p class="sub">Not published yet.</p>`}
      <div class="formula">${esc(formula[k] || "")}</div>
      ${d ? `<p style="margin-bottom:4px"><strong>Limits</strong></p><ul>${d.limits.map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}`; }).join("");

    // metadata example built from a real product
    const k0 = "soil", p0 = TL.products[k0], d0 = L[k0];
    if (d0) $("meta").textContent = JSON.stringify({ product: k0, display_name: p0.name, source: p0.source, updated: d0.updated, period: d0.subtitle,
      baseline: p0.baseline, spatial_resolution: p0.resolution, unit: "percent of normal; category", version: p0.version, processing: "Tinga Lens",
      status: p0.status }, null, 2);

    if (!report) { $("validation").innerHTML = `<p class="sub">The fire model report is not published yet.</p>`; return; }
    const text = { M0: "Season only", M1: "Season + surface soil moisture", M1r: "Season + root-zone soil moisture", M2: "Season + surface + root zone", M3: "All predictors" };
    const c = report.comparisons.root_added_to_surface, s = report.comparisons.surface_over_season;
    $("validation").innerHTML = `
      <p>The fire probability model was tested on ${report.rows.toLocaleString()} district-periods. Each fire year (July to June) was left out of training in turn and then predicted. A fire occurred in ${pct(report.fire_share)} of periods.</p>
      <div class="card scroll"><table class="t"><thead><tr><th>Model</th><th class="num">ROC-AUC</th><th class="num">Brier score</th><th class="num">Skill over season alone</th><th></th></tr></thead><tbody>
      ${Object.entries(report.models).map(([m, v]) => `<tr><td>${esc(text[m] || m)}</td><td class="num">${v.auc.toFixed(3)}</td><td class="num">${v.brier.toFixed(4)}</td><td class="num">${pct(v.skill_vs_season)}</td><td>${m === report.model_used ? "used on the map" : ""}</td></tr>`).join("")}
      </tbody></table></div>
      <ul>
        <li>Most of the skill comes from the season: how often each district usually burns on those dates.</li>
        <li>Surface soil moisture reduced the error by ${s.brier_reduction_pct.toFixed(1)}% and helped in ${s.years_better} of ${s.years} test years.</li>
        <li>Adding root-zone soil moisture changed the error by ${(-c.brier_reduction_pct).toFixed(1)}% and helped in ${c.years_better} of ${c.years} test years${["M2", "M3"].includes(report.model_used) ? "" : ", so it is not used"}.</li>
        <li>Temperature, humidity and wind are not yet included.</li>
      </ul>
      ${report.by_month ? `<h3>Month by month</h3><div class="card scroll"><table class="t"><thead><tr><th>Month</th><th class="num">Periods with a fire</th><th class="num">Average estimate</th><th class="num">ROC-AUC</th><th class="num">Season alone</th></tr></thead><tbody>
      ${report.by_month.map(b => `<tr><td>${esc(b.month)}</td><td class="num">${pct(b.observed)}</td><td class="num">${pct(b.predicted)}</td><td class="num">${b.auc == null ? "–" : b.auc.toFixed(3)}</td><td class="num">${b.auc_season_only == null ? "–" : b.auc_season_only.toFixed(3)}</td></tr>`).join("")}
      </tbody></table></div>` : ""}
      <h3>Calibration</h3><p>When the model gives a chance in the range shown, how often did a fire follow?</p>
      <div class="card scroll"><table class="t"><thead><tr><th>Estimated chance</th><th class="num">Average estimate</th><th class="num">Fires observed</th><th class="num">District-periods</th></tr></thead><tbody>
      ${report.reliability_full_model.map(b => `<tr><td>${Math.round(b.predicted_from * 100)}–${Math.round(b.predicted_to * 100)}%</td><td class="num">${pct(b.mean_predicted)}</td><td class="num">${pct(b.observed)}</td><td class="num">${b.n.toLocaleString()}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="sub">Precision, recall, F1 and PR-AUC are not reported yet. They depend on choosing a threshold, which has not been set.</p>`;
  });
})();
