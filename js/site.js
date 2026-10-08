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
  const onTopic = TL.topics.some(([label]) => label === here);
  const head = document.createElement("header");
  head.className = "site-head";
  head.innerHTML = `<div class="wrap">
    <a class="brand" href="${ROOT || "./"}"><svg viewBox="0 0 120 120" width="30" height="30" aria-hidden="true">
      <path d="M60 8 A52 52 0 1 1 8 60" fill="none" stroke="#F3F5F4" stroke-width="10" stroke-linecap="round"/>
      <path d="M60 30 A30 30 0 1 1 30 60" fill="none" stroke="#74C69D" stroke-width="10" stroke-linecap="round"/>
      <circle cx="60" cy="60" r="11" fill="#C9A98D"/><circle cx="23" cy="23" r="7" fill="#6CB8D8"/></svg><span>Tinga <em>Lens</em></span></a>
    <button class="menu-btn" id="menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="site-nav">☰</button>
    <nav class="site-nav" id="site-nav" aria-label="Main">${TL.nav.map(([label, href]) => href === null
      ? `<div class="nav-group"><button type="button" class="nav-drop${onTopic ? " here" : ""}" id="maps-btn" aria-expanded="false" aria-controls="maps-menu">${esc(label)} <span aria-hidden="true">▾</span></button>
          <div class="nav-menu" id="maps-menu">${TL.topics.map(([t, h]) => `<a href="${ROOT + h}"${t === here ? ' aria-current="page"' : ""}>${esc(t)}</a>`).join("")}</div></div>`
      : `<a href="${ROOT + href || "./"}"${label === here ? ' aria-current="page"' : ""}>${esc(label)}</a>`).join("")}</nav>
  </div>`;
  document.body.prepend(head);
  if (onTopic) {       // on a map page: a row of the other topics
    const row = document.createElement("nav");
    row.className = "topic-nav"; row.setAttribute("aria-label", "Topics");
    row.innerHTML = `<div class="wrap"><span>Maps</span>${TL.topics.map(([label, href]) =>
      `<a href="${ROOT + href}"${label === here ? ' aria-current="page"' : ""}>${esc(label)}</a>`).join("")}</div>`;
    head.after(row);
  }
  const mapsBtn = $("maps-btn"), mapsMenu = $("maps-menu");
  const setMaps = open => { mapsMenu.classList.toggle("open", open); mapsBtn.setAttribute("aria-expanded", open); };
  mapsBtn.addEventListener("click", e => { e.stopPropagation(); setMaps(!mapsMenu.classList.contains("open")); });
  document.addEventListener("click", e => { if (!mapsMenu.contains(e.target)) setMaps(false); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") setMaps(false); });
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
      <a href="${ROOT}pages/methods.html">Data and methods</a>, <a href="${ROOT}pages/brief.html">This month in Ghana</a>, <a href="${ROOT}pages/about.html">About</a>, <a href="${ROOT}pages/contact.html">Contact us</a>, <a href="${TL.repo}">Code</a></p>
    <p class="sub">We count visits and map downloads with GoatCounter to see how Tinga Lens is used. It sets no cookies and stores no names, email addresses or IP addresses.</p>
  </div>`;
  document.body.append(foot);
})();

// ---- Visit and download counts (GoatCounter: no cookies, no personal data) ----
// A download is counted as two events: "download/<page>/<item>" (what was taken) and "download-total" (shown on the home page).
(function () {
  const CODE = "tingalens";
  const s = document.createElement("script");
  s.async = true; s.src = "https://gc.zgo.at/count.js";
  s.dataset.goatcounter = `https://${CODE}.goatcounter.com/count`;
  document.head.append(s);

  const slug = t => String(t).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
  const send = name => {
    let tries = 0;
    const go = () => {
      if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: name, title: name, event: true, no_session: true });
      else if (tries++ < 50) setTimeout(go, 100);
    };
    go();
  };
  // Count a click on a visible download button or link. Links the page builds for itself have no text, so one click is never counted twice.
  document.addEventListener("click", e => {
    const el = e.target.closest("a[download], button");
    if (!el) return;
    const label = (el.textContent || "").trim();
    if (!label || !(/^download\b/i.test(label) || el.hasAttribute("download"))) return;
    const where = slug(document.documentElement.dataset.page || "home") + (location.hash ? "-" + slug(location.hash) : "");
    send(`download/${where}/${el.id || slug(label)}`);
    send("download-total");
  }, true);

  // Home page: show the total, only when there is a real number.
  const box = document.getElementById("dl-count");
  if (box) {
    const read = path => fetch(`https://${CODE}.goatcounter.com/counter/${encodeURIComponent(path)}.json`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(j => num(j.count));
    read("download-total").catch(() => read("/download-total")).then(n => {
      if (n > 0) { box.textContent = `Maps and tables downloaded so far: ${n.toLocaleString("en")}`; box.hidden = false; }
    }).catch(() => {});
  }
})();
