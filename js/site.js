// Tinga Lens - shared header, navigation, footer and small helpers used on every page.
const ROOT = document.documentElement.dataset.root || "";       // "" on the home page, "../" inside pages/
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const getJSON = u => fetch(ROOT + u + "?" + Date.now()).then(r => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
const num = s => { const v = parseFloat(String(s).replace(/,/g, "")); return isNaN(v) ? null : v; };
// dark text on light colours, white text on dark colours
const ink = hex => { const n = parseInt(hex.slice(1), 16), l = 0.299 * (n >> 16) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255); return l > 150 ? "#17252A" : "#fff"; };
const MONS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const badge = status => `<span class="badge ${status}" title="${esc((TL.status[status] || {}).text || "")}">${esc((TL.status[status] || { label: "In development" }).label)}</span>`;

(function () {
  const here = document.documentElement.dataset.page || "";
  // browser tab icon
  [["icon", "image/svg+xml", "assets/logo/favicon.svg"], ["alternate icon", "image/png", "assets/logo/favicon-32.png"], ["apple-touch-icon", "", "assets/logo/apple-touch-icon.png"]].forEach(([rel, type, href]) => {
    if (document.querySelector(`link[rel="${rel}"]`)) return;
    const l = document.createElement("link"); l.rel = rel; if (type) l.type = type; l.href = ROOT + href; document.head.append(l);
  });
  const head = document.createElement("header");
  head.className = "site-head";
  head.innerHTML = `<div class="wrap">
    <a class="brand" href="${ROOT || "./"}"><svg viewBox="0 0 120 120" width="30" height="30" aria-hidden="true">
      <path d="M60 8 A52 52 0 1 1 8 60" fill="none" stroke="#F3F5F4" stroke-width="10" stroke-linecap="round"/>
      <path d="M60 30 A30 30 0 1 1 30 60" fill="none" stroke="#74C69D" stroke-width="10" stroke-linecap="round"/>
      <circle cx="60" cy="60" r="11" fill="#C9A98D"/><circle cx="23" cy="23" r="7" fill="#6CB8D8"/></svg><span>Tinga <em>Lens</em></span></a>
    <button class="menu-btn" id="menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="site-nav">☰</button>
    <nav class="site-nav" id="site-nav" aria-label="Main">${TL.nav.map(([label, href]) =>
      `<a href="${ROOT + href || "./"}"${label === here ? ' aria-current="page"' : ""}>${esc(label)}</a>`).join("")}</nav>
  </div>`;
  document.body.prepend(head);
  $("menu-btn").addEventListener("click", () => {
    const open = $("site-nav").classList.toggle("open");
    $("menu-btn").setAttribute("aria-expanded", open);
  });

  const foot = document.createElement("footer");
  foot.className = "site-foot";
  foot.innerHTML = `<div class="wrap">
    <p id="foot-layer"></p>
    <p class="disclaimer"><strong>Important:</strong> ${esc(TL.disclaimer)}</p>
    <p>Tinga Lens is independent and uses only public datasets and its own code.
      Boundaries: <a href="https://www.geoboundaries.org">geoBoundaries</a> (CC BY 4.0). Basemap © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors.
      <a href="${ROOT}pages/methods.html">Data and methods</a>, <a href="${ROOT}pages/about.html">About and contact</a>, <a href="${TL.repo}">Code</a></p>
  </div>`;
  document.body.append(foot);
})();
