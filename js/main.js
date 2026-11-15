/* Shared helpers: language switching, nav state, painting-card rendering, placeholder art. */

let ARTISTS = [];
let PAINTINGS = [];

function fetchJson(url) {
  return fetch(url)
    .then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .catch(err => {
      console.error("Could not load " + url + ":", err);
      showFetchErrorBanner();
      return [];
    });
}

function loadArtists() {
  return fetchJson("artists.json").then(data => { ARTISTS = data; return data; });
}

function loadPaintings() {
  return fetchJson("paintings.json").then(data => { PAINTINGS = data; return data; });
}

function loadAll() {
  return Promise.all([loadArtists(), loadPaintings()]);
}

function showFetchErrorBanner() {
  if (document.getElementById("fetch-error-banner")) return;
  const banner = document.createElement("div");
  banner.id = "fetch-error-banner";
  banner.style.cssText = "position:fixed;bottom:0;left:0;right:0;background:#1a1714;color:#faf8f4;padding:14px 20px;font-family:sans-serif;font-size:13px;z-index:9999;text-align:center;";
  banner.innerHTML = "This page loads data from a .json file and needs a local server — opening the file directly won't work. Run <code>python3 -m http.server</code> in the site folder, then open <code>http://localhost:8000</code>.";
  document.body.appendChild(banner);
}

function getArtist(id) {
  return ARTISTS.find(a => a.id === id) || {
    id: id,
    name: { en: id, ua: id },
    years: "",
    title: null,
    hue: ["#a89078", "#5a4a3a", "#d8c9b0"],
    bio: [],
    sources: []
  };
}

function getPaintingsByArtist(id) {
  return PAINTINGS.filter(p => p.artistId === id);
}

function getPaintingById(id) {
  return PAINTINGS.find(p => p.id === id);
}

function statusLabel(status, t) {
  return t["status_" + status] || t.status_available;
}

function getLang() {
  try {
    return localStorage.getItem("lang") || "en";
  } catch (e) {
    return "en";
  }
}

function storeLang(lang) {
  try {
    localStorage.setItem("lang", lang);
  } catch (e) {
    /* ignore */
  }
}

function brushSvg(hues, seed) {
  const [a, b, c] = hues;
  return `
    <svg viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="g${seed}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${a}"/>
          <stop offset="55%" stop-color="${b}"/>
          <stop offset="100%" stop-color="${c}"/>
        </linearGradient>
      </defs>
      <rect width="400" height="500" fill="url(#g${seed})"/>
      <path d="M0 ${140 + seed * 8} Q 100 ${90 + seed * 6} 200 ${150 + seed * 4} T 400 ${130 + seed * 5}" stroke="${c}" stroke-width="26" fill="none" opacity="0.35"/>
      <path d="M0 ${330 - seed * 6} Q 150 ${300 - seed * 4} 260 ${360 - seed * 3} T 400 ${340 - seed * 4}" stroke="${a}" stroke-width="34" fill="none" opacity="0.3"/>
      <circle cx="${90 + seed * 20}" cy="${420 - seed * 10}" r="${38 + seed * 3}" fill="${b}" opacity="0.4"/>
    </svg>
  `;
}

function yearLabel(p, lang) {
  if (p.yearNote) return p.yearNote[lang];
  return p.year != null ? String(p.year) : "—";
}

function paintingCardHtml(p, lang, seed) {
  const t = Object.assign({}, I18N_COMMON[lang]);
  const artist = getArtist(p.artistId);
  const artistHref = `artist/${p.artistId}.html`;
  const paintingHref = `painting/${p.id}.html`;
  const yearText = yearLabel(p, lang);
  const [gA, , gC] = p.hue;
  const gradientStyle = `background: linear-gradient(135deg, ${gA}, ${gC});`;
  const frontPhoto = p.photos && p.photos.front;
  const media = frontPhoto
    ? `<img src="${frontPhoto}" alt="${p.title[lang]}" loading="lazy" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none'">`
    : brushSvg(p.hue, seed);
  const lifeRow = artist.years
    ? `<div class="meta-row"><span>${t.life_field}</span><span>${artist.years}</span></div>`
    : "";
  return `
    <article class="painting-card">
      <a class="canvas" style="${gradientStyle}" href="${paintingHref}">
        ${media}
        <span class="status-badge">${statusLabel(p.status, t)}</span>
      </a>
      <div class="card-body">
        <a href="${paintingHref}" class="painting-title-link"><h3 class="painting-title">${p.title[lang]}, ${yearText}</h3></a>
        <a class="painting-artist" href="${artistHref}">${artist.name[lang]}</a>
        <div class="meta-row"><span>${t.artist_field}</span><span>${artist.name[lang]}</span></div>
        ${lifeRow}
        <div class="meta-row"><span>${t.year_field}</span><span>${yearText}</span></div>
        <div class="meta-row"><span>${t.medium_field}</span><span>${p.medium[lang]}</span></div>
        <div class="meta-row"><span>${t.size_field}</span><span>${p.size}</span></div>
        <div class="meta-row"><span>${t.price_field}</span><span>${t.price_on_request}</span></div>
        <button class="inquire-btn" title="${p.id}" onclick="window.open('https://instagram.com/theodesaschool', '_blank')">${t.inquire}</button>
      </div>
    </article>
  `;
}

function paintingThumbHtml(p, lang, seed) {
  const [gA, , gC] = p.hue;
  const frontPhoto = p.photos && p.photos.front;
  const media = frontPhoto
    ? `<img src="${frontPhoto}" alt="${p.title[lang]}" loading="lazy" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none'">`
    : brushSvg(p.hue, seed);
  return `
    <a class="thumb-item" href="painting/${p.id}.html" style="background: linear-gradient(135deg, ${gA}, ${gC});">
      ${media}
      <span class="thumb-title">${p.title[lang]}, ${yearLabel(p, lang)}</span>
    </a>
  `;
}

function translatePage(lang) {
  const dict = Object.assign({}, I18N_COMMON[lang], (window.PAGE_I18N && window.PAGE_I18N[lang]) || {});
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (dict[key] !== undefined) el.innerHTML = dict[key];
  });
  return dict;
}

function setActiveNav() {
  const page = document.body.getAttribute("data-page");
  document.querySelectorAll("nav.main-nav a").forEach(a => {
    a.classList.toggle("active", a.getAttribute("data-nav") === page);
  });
}

function initLangSwitch(onChange) {
  const lang = getLang();
  applyLang(lang, onChange);
  const btnEn = document.getElementById("btn-en");
  const btnUa = document.getElementById("btn-ua");
  if (btnEn) btnEn.addEventListener("click", () => { storeLang("en"); applyLang("en", onChange); });
  if (btnUa) btnUa.addEventListener("click", () => { storeLang("ua"); applyLang("ua", onChange); });
}

function applyLang(lang, onChange) {
  document.documentElement.lang = lang;
  const btnEn = document.getElementById("btn-en");
  const btnUa = document.getElementById("btn-ua");
  if (btnEn) btnEn.classList.toggle("active", lang === "en");
  if (btnUa) btnUa.classList.toggle("active", lang === "ua");
  const dict = translatePage(lang);
  setActiveNav();
  if (typeof onChange === "function") onChange(lang, dict);
}

/* Scroll-reveal: fades in painting cards / thumbs as they enter the viewport.
   Watches the whole page so it works on cards rendered later (after fetch, after language switch). */
(function () {
  const REVEAL_SELECTOR = ".painting-card, .thumb-item";
  let observer = null;

  function getObserver() {
    if (observer || !("IntersectionObserver" in window)) return observer;
    observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -60px 0px" });
    return observer;
  }

  function watch(el) {
    if (el.classList.contains("is-visible")) return;
    const obs = getObserver();
    if (!obs) { el.classList.add("is-visible"); return; }
    obs.observe(el);
  }

  function scan(root) {
    if (!root.querySelectorAll) return;
    root.querySelectorAll(REVEAL_SELECTOR).forEach(watch);
  }

  document.addEventListener("DOMContentLoaded", () => {
    scan(document);
    new MutationObserver(mutations => {
      mutations.forEach(m => {
        m.addedNodes.forEach(node => {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches(REVEAL_SELECTOR)) watch(node);
          scan(node);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  });
})();
