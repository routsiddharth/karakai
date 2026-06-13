/* karak.ai — map app. Vanilla JS + MapLibre GL + OpenFreeMap positron (warm-tinted). */
(function () {
  "use strict";

  // ---------- data prep ----------
  const SPOTS = (window.KARAK_SPOTS || []).map((s, i) => ({ ...s, id: i }));

  const STATE_TZ = {
    CT:"America/New_York", DE:"America/New_York", FL:"America/New_York", GA:"America/New_York",
    IN:"America/New_York", KY:"America/New_York", ME:"America/New_York", MD:"America/New_York",
    MA:"America/New_York", MI:"America/New_York", NH:"America/New_York", NJ:"America/New_York",
    NY:"America/New_York", NC:"America/New_York", OH:"America/New_York", PA:"America/New_York",
    RI:"America/New_York", SC:"America/New_York", VT:"America/New_York", VA:"America/New_York",
    WV:"America/New_York", DC:"America/New_York",
    AL:"America/Chicago", AR:"America/Chicago", IL:"America/Chicago", IA:"America/Chicago",
    KS:"America/Chicago", LA:"America/Chicago", MN:"America/Chicago", MS:"America/Chicago",
    MO:"America/Chicago", NE:"America/Chicago", ND:"America/Chicago", OK:"America/Chicago",
    SD:"America/Chicago", TN:"America/Chicago", TX:"America/Chicago", WI:"America/Chicago",
    CO:"America/Denver", ID:"America/Denver", MT:"America/Denver", NM:"America/Denver",
    UT:"America/Denver", WY:"America/Denver", AZ:"America/Phoenix",
    CA:"America/Los_Angeles", NV:"America/Los_Angeles", OR:"America/Los_Angeles", WA:"America/Los_Angeles",
    BH:"Asia/Bahrain", DU:"Asia/Dubai", AD:"Asia/Dubai", ON:"America/Toronto",
  };
  const STATE_NAMES = {
    AL:"Alabama", AZ:"Arizona", AR:"Arkansas", CA:"California", CO:"Colorado", CT:"Connecticut",
    DE:"Delaware", DC:"Washington DC", FL:"Florida", GA:"Georgia", ID:"Idaho", IL:"Illinois",
    IN:"Indiana", IA:"Iowa", KS:"Kansas", KY:"Kentucky", LA:"Louisiana", ME:"Maine", MD:"Maryland",
    MA:"Massachusetts", MI:"Michigan", MN:"Minnesota", MS:"Mississippi", MO:"Missouri", MT:"Montana",
    NE:"Nebraska", NV:"Nevada", NH:"New Hampshire", NJ:"New Jersey", NM:"New Mexico", NY:"New York",
    NC:"North Carolina", ND:"North Dakota", OH:"Ohio", OK:"Oklahoma", OR:"Oregon", PA:"Pennsylvania",
    RI:"Rhode Island", SC:"South Carolina", SD:"South Dakota", TN:"Tennessee", TX:"Texas", UT:"Utah",
    VT:"Vermont", VA:"Virginia", WA:"Washington", WV:"West Virginia", WI:"Wisconsin", WY:"Wyoming",
    BH:"Bahrain", DU:"Dubai", AD:"Abu Dhabi", ON:"Toronto",
  };
  // international region codes show their full name; US states keep the abbreviation
  const INTL = { BH:"Bahrain", DU:"Dubai", AD:"Abu Dhabi", ON:"Toronto" };
  const stLabel = (st) => INTL[st] || st;
  const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  const DAY_LABEL = { sun:"Sun", mon:"Mon", tue:"Tue", wed:"Wed", thu:"Thu", fri:"Fri", sat:"Sat" };

  // ---------- time helpers ----------
  function nowInTz(tz) {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
    }).formatToParts(new Date());
    const get = (t) => (parts.find((p) => p.type === t) || {}).value;
    const day = (get("weekday") || "Sun").toLowerCase().slice(0, 3);
    let hh = parseInt(get("hour"), 10); if (hh === 24) hh = 0;
    return { day, mins: hh * 60 + parseInt(get("minute"), 10) };
  }
  const toMins = (hhmm) => {
    const [h, m] = hhmm.split(":").map(Number);
    return h * 60 + m;
  };
  function fmt12(hhmm) {
    let [h, m] = hhmm.split(":").map(Number);
    if (h >= 24) h -= 24;
    const ap = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    return m ? `${h}:${String(m).padStart(2, "0")} ${ap}` : `${h} ${ap}`;
  }

  // Open state for a spot right now (handles past-midnight closes).
  function openState(spot) {
    const tz = STATE_TZ[spot.state] || "America/New_York";
    const { day, mins } = nowInTz(tz);
    const di = DAYS.indexOf(day);
    const today = spot.hours && spot.hours[day];
    // spilled-over window from yesterday (e.g. open until 2 AM)
    const yKey = DAYS[(di + 6) % 7];
    const y = spot.hours && spot.hours[yKey];
    if (y && toMins(y[1] >= "24:00" ? "23:59" : y[1]) < toMins(y[0]) && mins < toMins(y[1])) {
      return { open: true, until: y[1] };
    }
    if (today) {
      if (today[0] === "00:00" && (today[1] === "24:00" || today[1] === "00:00")) {
        return { open: true, allDay: true };
      }
      const o = toMins(today[0]);
      let c = toMins(today[1]);
      const wraps = c <= o; // closes after midnight (or 24h if equal)
      if (today[1] === "24:00") c = 1440;
      if (!wraps && mins >= o && mins < c) return { open: true, until: today[1] };
      if (wraps && mins >= o) return { open: true, until: today[1] };
      if (mins < o) return { open: false, next: `${fmt12(today[0])}` };
    }
    // find next opening day
    for (let k = 1; k <= 7; k++) {
      const d = DAYS[(di + k) % 7];
      if (spot.hours && spot.hours[d]) {
        return { open: false, next: `${DAY_LABEL[d]} ${fmt12(spot.hours[d][0])}` };
      }
    }
    return { open: false, next: null };
  }
  function opensLate(spot) {
    const tz = STATE_TZ[spot.state] || "America/New_York";
    const { day } = nowInTz(tz);
    const h = spot.hours && spot.hours[day];
    if (!h) return false;
    const c = toMins(h[0]), cl = toMins(h[1] === "24:00" ? "23:59" : h[1]);
    return cl >= 23 * 60 || cl < c; // closes 11 PM+ or past midnight
  }

  // ---------- filters / geojson ----------
  const state = { openNow: false, late: false, selected: null };

  function visibleSpots() {
    return SPOTS.filter((s) =>
      (!state.openNow || openState(s).open) && (!state.late || opensLate(s))
    );
  }
  function toGeoJSON(spots) {
    return {
      type: "FeatureCollection",
      features: spots.map((s) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [s.lng, s.lat] },
        properties: { id: s.id, name: s.name },
      })),
    };
  }

  // ---------- basemap: warm-tint positron ----------
  function warmify(style) {
    for (const l of style.layers) {
      const id = l.id.toLowerCase();
      l.paint = l.paint || {};
      try {
        if (l.type === "background") {
          l.paint["background-color"] = "#efe2c2";
        } else if (l.type === "fill") {
          if (id === "water" || /water|ocean/.test(id)) l.paint["fill-color"] = "#a9c6b4";
          else if (/park|wood|grass|cemetery|pitch|stadium/.test(id)) l.paint["fill-color"] = "#d3d6a8";
          else if (/ice|glacier/.test(id)) l.paint["fill-color"] = "#f0e9d4";
          else if (/residential|landuse|landcover/.test(id)) l.paint["fill-color"] = "#ecdfbc";
          else if (/building/.test(id)) {
            l.paint["fill-color"] = "#e1cfa6";
            l.paint["fill-outline-color"] = "#cfb785";
          }
          else if (/aeroway|pier/.test(id)) l.paint["fill-color"] = "#e5d6ae";
        } else if (l.type === "line") {
          if (/waterway|river/.test(id)) l.paint["line-color"] = "#96b8a4";
          else if (/boundary|admin/.test(id)) l.paint["line-color"] = "#9c7340";
          else if (/casing/.test(id)) l.paint["line-color"] = "#cfa860";
          else if (/inner/.test(id)) l.paint["line-color"] = "#fbf2da";
          else if (/subtle|path|minor|track|service/.test(id)) l.paint["line-color"] = "#d8bd86";
          else if (/railway/.test(id)) l.paint["line-color"] = /dash/.test(id) ? "#efe2c2" : "#bca372";
          else if (/aeroway|pier/.test(id)) l.paint["line-color"] = "#ddcb9d";
        } else if (l.type === "symbol") {
          l.paint["text-color"] = "#7c531f";
          l.paint["text-halo-color"] = "#f2e6c6";
          l.layout = l.layout || {};
          if (/place|city|town|village|state|country|continent/.test(id)) {
            l.paint["text-color"] = "#2b1c10";
            l.paint["text-halo-color"] = "#efe2c2";
            l.layout["text-transform"] = "uppercase";
            l.layout["text-letter-spacing"] = 0.12;
          }
        }
      } catch (e) { /* non-fatal: keep positron default for this layer */ }
    }
    return style;
  }

  // ---------- map ----------
  const US_BOUNDS = [[-125.5, 24.2], [-66.0, 49.6]];
  const REGIONS = {
    us: US_BOUNDS,
    nyc: [[-74.10, 40.55], [-73.70, 40.92]],
    bh: [[50.30, 25.78], [50.72, 26.34]],
    dubai: [[54.95, 24.80], [55.55, 25.35]],
    abudhabi: [[54.25, 24.30], [54.80, 24.72]],
    toronto: [[-79.95, 43.40], [-78.95, 43.95]],
  };
  let currentRegion = "bh";
  let map, hoverPop;

  fetch("https://tiles.openfreemap.org/styles/positron")
    .then((r) => r.json())
    .then((style) => initMap(warmify(style)))
    .catch(() => initMap("https://tiles.openfreemap.org/styles/positron")); // fallback untinted

  function initMap(style) {
    map = new maplibregl.Map({
      container: "map",
      style,
      bounds: REGIONS[currentRegion],
      fitBoundsOptions: { padding: 40 },
      attributionControl: false,
      minZoom: 3,
      fadeDuration: 150,
    });
    // gentler wheel steps so cluster reflow doesn't jump
    map.scrollZoom.setWheelZoomRate(1 / 900);
    map.scrollZoom.setZoomRate(1 / 180);

    map.on("load", () => {
      map.addSource("spots", {
        type: "geojson",
        data: toGeoJSON(visibleSpots()),
        cluster: true,
        clusterMaxZoom: 11,
        clusterRadius: 52,
      });

      map.addLayer({
        id: "clusters", type: "circle", source: "spots",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#e23d1d",
          "circle-stroke-color": "#2b1c10",
          "circle-stroke-width": 2.5,
          "circle-radius": ["step", ["get", "point_count"], 15, 5, 19, 15, 25],
          "circle-radius-transition": { duration: 350, delay: 0 },
          "circle-opacity-transition": { duration: 200, delay: 0 },
        },
      });
      map.addLayer({
        id: "cluster-count", type: "symbol", source: "spots",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-font": ["Noto Sans Bold"],
          "text-size": 13.5,
        },
        paint: { "text-color": "#f4ead2" },
      });
      map.addLayer({
        id: "spot-dot", type: "circle", source: "spots",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": "#2b1c10",
          "circle-stroke-color": "#f4ead2",
          "circle-stroke-width": 2,
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 6, 10, 7.5, 14, 9],
        },
      });
      map.addLayer({
        id: "spot-selected", type: "circle", source: "spots",
        filter: ["==", ["get", "id"], -1],
        paint: {
          "circle-color": "#e23d1d",
          "circle-stroke-color": "#2b1c10",
          "circle-stroke-width": 3,
          "circle-radius": 11,
        },
      });
      map.addLayer({
        id: "spot-label", type: "symbol", source: "spots",
        filter: ["!", ["has", "point_count"]],
        minzoom: 9.5,
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Bold"],
          "text-size": 12,
          "text-anchor": "left",
          "text-offset": [1.0, 0],
          "text-max-width": 9,
          "text-transform": "uppercase",
          "text-letter-spacing": 0.06,
        },
        paint: {
          "text-color": "#2b1c10",
          "text-halo-color": "#f2e6c6",
          "text-halo-width": 1.6,
        },
      });

      wireMapEvents();
      updateCount();
      updateCoords();
    });
  }

  function wireMapEvents() {
    map.on("click", "clusters", (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ["clusters"] })[0];
      map.getSource("spots").getClusterExpansionZoom(f.properties.cluster_id).then((z) => {
        map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.4, duration: 650 });
      });
    });
    map.on("click", "spot-dot", (e) => {
      const id = e.features[0].properties.id;
      selectSpot(SPOTS[id], { fly: false });
    });

    hoverPop = new maplibregl.Popup({
      closeButton: false, closeOnClick: false, className: "hoverpop", offset: 14,
    });
    const mapEl = document.getElementById("map");
    for (const layer of ["spot-dot", "clusters"]) {
      map.on("mouseenter", layer, (e) => {
        mapEl.classList.add("hovering");
        if (layer === "spot-dot" && map.getZoom() < 9.5) {
          const f = e.features[0];
          hoverPop.setLngLat(f.geometry.coordinates).setText(f.properties.name).addTo(map);
        }
      });
      map.on("mouseleave", layer, () => {
        mapEl.classList.remove("hovering");
        hoverPop.remove();
      });
    }

    map.on("move", updateCoords);
    map.on("moveend", updateCount);
  }

  function refreshSource() {
    const src = map && map.getSource("spots");
    if (src) src.setData(toGeoJSON(visibleSpots()));
    updateCount();
  }

  // ---------- spot card ----------
  const card = document.getElementById("card");
  const cardInner = document.getElementById("card-inner");

  function esc(t) {
    return String(t).replace(/[&<>"]/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));
  }
  const money = (n, cur) => {
    if (cur === "BHD") return n < 1 ? `${Math.round(n * 1000)} fils` : `BD ${n.toFixed(2)}`;
    if (cur === "AED") return `AED ${Number.isInteger(n) ? n : n.toFixed(2)}`;
    if (cur === "CAD") return "C$" + (Number.isInteger(n) ? n : n.toFixed(2));
    return "$" + (Number.isInteger(n) ? n : n.toFixed(2));
  };

  function selectSpot(spot, opts = {}) {
    state.selected = spot.id;
    if (map.getLayer("spot-selected")) {
      map.setFilter("spot-selected", ["==", ["get", "id"], spot.id]);
    }
    if (opts.fly !== false) {
      map.flyTo({ center: [spot.lng, spot.lat], zoom: Math.max(map.getZoom(), 13.5), duration: 1400, essential: true });
    }
    renderCard(spot);
    card.hidden = false;
  }
  function closeCard() {
    card.hidden = true;
    state.selected = null;
    if (map && map.getLayer("spot-selected")) {
      map.setFilter("spot-selected", ["==", ["get", "id"], -1]);
    }
  }
  document.getElementById("card-close").addEventListener("click", closeCard);

  function renderCard(s) {
    const st = openState(s);
    const tz = STATE_TZ[s.state] || "America/New_York";
    const today = nowInTz(tz).day;
    const est = s.priceEstimated ? '<span class="est-mark" title="estimated price">~</span>' : "";

    const statusHtml = st.open
      ? `<div class="c-status is-open"><span class="dotmark"></span><span><b>Open</b> · ${st.allDay ? "24 hours" : "until " + fmt12(st.until)}</span></div>`
      : `<div class="c-status is-closed"><span class="dotmark"></span><span><b>Closed</b>${st.next ? " · opens " + st.next : ""}</span></div>`;

    const hoursRows = DAYS.map((d) => {
      const h = s.hours && s.hours[d];
      const v = !h ? "closed"
        : (h[0] === "00:00" && (h[1] === "24:00" || h[1] === "00:00")) ? "24 hours"
        : `${fmt12(h[0])} – ${fmt12(h[1])}`;
      return `<tr class="${d === today ? "today" : ""}"><td>${DAY_LABEL[d]}</td><td>${v}</td></tr>`;
    }).join("");

    let karakMarked = false;
    const menuHtml = (s.menu || []).map((m) => {
      const isK = !karakMarked && /karak|chai|adeni|doodh/i.test(m.item);
      if (isK) karakMarked = true;
      return `<li class="${isK ? "is-karak" : ""}">
        <span class="m-item">${esc(m.item)}</span>
        <span class="m-leader"></span>
        <span class="m-price">${est}${money(m.price, s.currency)}</span>
      </li>`;
    }).join("");

    const gmaps = "https://www.google.com/maps/search/?api=1&query=" +
      encodeURIComponent(`${s.name} ${s.address}`);

    cardInner.innerHTML = `
      <h2 class="c-name">${esc(s.name)}</h2>
      <div class="c-meta">
        <span class="c-rating"><span class="star">★</span> ${s.rating ? s.rating.toFixed(1) : "—"}</span>
        ${s.reviews ? `<span class="c-reviews">(${s.reviews.toLocaleString()})</span>` : ""}
        <span>·</span><span>${esc(s.city)}, ${esc(stLabel(s.state))}</span>
      </div>
      ${statusHtml}
      <details class="c-hours"><summary>all hours</summary><table>${hoursRows}</table></details>
      <div class="c-label">on the menu</div>
      <ul class="c-menu">${menuHtml}</ul>
      ${s.note ? `<p class="c-note">${esc(s.note)}</p>` : ""}
      <div class="c-foot">
        <span class="c-addr">${esc(s.address)}</span>
        <a class="c-dir" href="${gmaps}" target="_blank" rel="noopener">☞ directions</a>
      </div>`;
  }

  // ---------- filters ----------
  const chipOpen = document.getElementById("chip-open");
  const chipLate = document.getElementById("chip-late");
  chipOpen.addEventListener("click", () => {
    state.openNow = !state.openNow;
    chipOpen.classList.toggle("on", state.openNow);
    refreshSource();
  });
  chipLate.addEventListener("click", () => {
    state.late = !state.late;
    chipLate.classList.toggle("on", state.late);
    refreshSource();
  });

  function updateCount() {
    const el = document.getElementById("spot-count");
    if (!map) { el.textContent = SPOTS.length; return; }
    const b = map.getBounds();
    const n = visibleSpots().filter((s) => b.contains([s.lng, s.lat])).length;
    el.textContent = n;
  }

  // ---------- coords strip ----------
  function updateCoords() {
    if (!map) return;
    const c = map.getCenter();
    const lat = Math.abs(c.lat).toFixed(4) + "°" + (c.lat >= 0 ? "N" : "S");
    const lng = Math.abs(c.lng).toFixed(4) + "°" + (c.lng >= 0 ? "E" : "W");
    document.getElementById("coords").textContent =
      `${lat} ${lng} Z ${map.getZoom().toFixed(1)}`;
  }

  // ---------- zoom / reset ----------
  document.getElementById("zoom-in").addEventListener("click", () => map && map.zoomIn({ duration: 250 }));
  document.getElementById("zoom-out").addEventListener("click", () => map && map.zoomOut({ duration: 250 }));
  document.getElementById("reset-view").addEventListener("click", resetView);
  document.getElementById("wordmark").addEventListener("click", (e) => { e.preventDefault(); resetView(); });
  function resetView() {
    closeCard();
    map && map.fitBounds(REGIONS[currentRegion], { padding: 40, duration: 1200 });
  }

  document.querySelectorAll(".region-btn").forEach((b) => {
    b.addEventListener("click", () => {
      currentRegion = b.dataset.region;
      document.querySelectorAll(".region-btn").forEach((x) => x.classList.toggle("on", x === b));
      closeCard();
      map && map.fitBounds(REGIONS[currentRegion], { padding: 40, duration: 1700 });
    });
  });

  // ---------- search ----------
  const searchEl = document.getElementById("search");
  const resultsEl = document.getElementById("search-results");
  let searchIdx = [];

  function buildSearchIndex() {
    searchIdx = [];
    for (const s of SPOTS) {
      searchIdx.push({ kind: "spot", label: s.name, sub: `${s.city}, ${stLabel(s.state)}`, key: `${s.name} ${s.city} ${s.state} ${STATE_NAMES[s.state] || ""}`.toLowerCase(), spot: s });
    }
    const cities = new Map();
    for (const s of SPOTS) {
      const k = `${s.city}|${s.state}`;
      if (!cities.has(k)) cities.set(k, { city: s.city, state: s.state, spots: [] });
      cities.get(k).spots.push(s);
    }
    for (const c of cities.values()) {
      searchIdx.push({ kind: "city", label: `${c.city}, ${stLabel(c.state)}`, sub: `${c.spots.length} spot${c.spots.length > 1 ? "s" : ""}`, key: `${c.city} ${c.state} ${STATE_NAMES[c.state] || ""}`.toLowerCase(), spots: c.spots });
    }
    const states = new Map();
    for (const s of SPOTS) {
      if (!states.has(s.state)) states.set(s.state, []);
      states.get(s.state).push(s);
    }
    for (const [ab, arr] of states) {
      searchIdx.push({ kind: "state", label: STATE_NAMES[ab] || ab, sub: `${arr.length} spot${arr.length > 1 ? "s" : ""}`, key: `${ab} ${(STATE_NAMES[ab] || "").toLowerCase()}`.toLowerCase(), spots: arr });
    }
  }
  buildSearchIndex();

  let selIdx = -1, curResults = [];
  function runSearch(q) {
    q = q.trim().toLowerCase();
    if (q.length < 2) { resultsEl.hidden = true; return; }
    curResults = searchIdx
      .map((r) => {
        const at = r.key.indexOf(q);
        if (at < 0) return null;
        const kindRank = r.kind === "city" ? 0 : r.kind === "state" ? 1 : 2;
        return { r, score: (at === 0 ? 0 : 1) * 10 + kindRank };
      })
      .filter(Boolean)
      .sort((a, b) => a.score - b.score)
      .slice(0, 8)
      .map((x) => x.r);
    selIdx = -1;
    if (!curResults.length) { resultsEl.hidden = true; return; }
    resultsEl.innerHTML = curResults.map((r, i) =>
      `<div class="search-result" data-i="${i}">
         <span class="r-name">${esc(r.label)}</span>
         <span class="r-loc">${esc(r.sub)}</span>
       </div>`).join("");
    resultsEl.hidden = false;
  }
  function chooseResult(r) {
    resultsEl.hidden = true;
    searchEl.value = r.label;
    searchEl.blur();
    if (r.kind === "spot") {
      selectSpot(r.spot);
    } else {
      closeCard();
      const lats = r.spots.map((s) => s.lat), lngs = r.spots.map((s) => s.lng);
      const pad = r.kind === "city" ? 0.06 : 0.4;
      map.fitBounds(
        [[Math.min(...lngs) - pad, Math.min(...lats) - pad], [Math.max(...lngs) + pad, Math.max(...lats) + pad]],
        { padding: 80, duration: 1300, maxZoom: r.kind === "city" ? 13 : 10 }
      );
    }
  }
  searchEl.addEventListener("input", () => runSearch(searchEl.value));
  searchEl.addEventListener("keydown", (e) => {
    if (resultsEl.hidden) return;
    if (e.key === "ArrowDown") { selIdx = Math.min(selIdx + 1, curResults.length - 1); paintSel(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { selIdx = Math.max(selIdx - 1, 0); paintSel(); e.preventDefault(); }
    else if (e.key === "Enter") { chooseResult(curResults[Math.max(selIdx, 0)]); }
    else if (e.key === "Escape") { resultsEl.hidden = true; }
  });
  function paintSel() {
    [...resultsEl.children].forEach((el, i) => el.classList.toggle("sel", i === selIdx));
  }
  resultsEl.addEventListener("mousedown", (e) => {
    const el = e.target.closest(".search-result");
    if (el) chooseResult(curResults[+el.dataset.i]);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) resultsEl.hidden = true;
  });

  // ---------- about ----------
  const about = document.getElementById("about");
  document.getElementById("nav-about").addEventListener("click", (e) => { e.preventDefault(); about.hidden = false; });
  document.getElementById("about-close").addEventListener("click", () => { about.hidden = true; });
  about.addEventListener("click", (e) => { if (e.target === about) about.hidden = true; });

  // ---------- keyboard ----------
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { about.hidden = true; closeCard(); }
    if (e.key === "/" && document.activeElement !== searchEl) { e.preventDefault(); searchEl.focus(); }
  });

  // re-evaluate "open now" every minute so statuses stay honest
  setInterval(() => { if (state.openNow) refreshSource(); }, 60_000);

  // test hook (harmless in prod)
  window.__karak = { get map() { return map; }, selectSpot, SPOTS };
})();
