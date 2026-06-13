# karak.ai

A map of where to find karak chai. **~1,200 spots** across Bahrain, the UAE
(Dubai & Abu Dhabi), the United States (full Manhattan + the Qahwah House chain),
and Toronto. Static site — no build step, no backend, no API key in the page.

## Run

Open `index.html` in a browser, or serve it:

```sh
python3 -m http.server 8000
# → http://localhost:8000
```

## Deploy

Upload `index.html`, `styles.css`, `app.js`, `data.js` to any static host
(Vercel, Netlify, GitHub Pages, Cloudflare Pages). The `_data/` folder is
tooling only and doesn't need to ship.

## Stack

- **Map**: MapLibre GL JS + OpenFreeMap `positron` vector tiles, re-tinted at
  load time to a chai-stained parchment palette (`warmify()` in `app.js`). No
  key needed in the browser.
- **Design**: "Scher cut" — typography-as-geography. Anton (display) · Oswald
  (condensed UI) · Archivo (body) · IBM Plex Mono (hours, prices, coordinates).
  Palette: masala ink `#2b1c10`, chai cream `#f4ead2`, enamel red `#e23d1d`,
  caramel `#c8862e`, cardamom green `#3e6e46`. Flat blocks, hard edges, no
  gradients. Alternate explorations live in `design-demos/`.
- **Data**: spots in `data.js`. Open-now status is computed client-side in each
  spot's own timezone. International prices render in local currency
  (`BHD` → fils/BD, `AED`, `CAD`). A region switcher flies between USA, NYC,
  Bahrain, Dubai, Abu Dhabi, and Toronto.

## Dataset

Spots come from two sources, both folded into `data.js` by `_data/merge.py`:

1. **Hand-curated** entries in `_data/region-*.json` (with menus, prices, notes).
2. **Google Places** entries in `_data/region-google-*.json`, scraped + filtered
   by the pipeline below. These carry accurate coordinates, hours and ratings
   but no editorial copy yet.

### Editing by hand

Edit/add spots in `_data/region-*.json` (schema: name, city, state, address,
lat, lng, rating, reviews, hours per-day `["HH:MM","HH:MM"]` or `null`,
menu `[{item, price}]`, tags, note, optional `priceEstimated`/`country`/`currency`),
then rebuild:

```sh
python3 _data/merge.py   # validates, dedupes, sorts → data.js
```

Prices marked `~` in the UI are estimates (`priceEstimated: true`).

### Re-scraping Google Places

Uses the Google **Places API (New)** Text Search. One request returns up to 20
full records (name, coords, rating, hours) and is billed as a single event, so a
keyword × city sweep is cheap. Set your key as an environment variable — it is
**never** committed or shipped to the browser:

```sh
export GMAPS_KEY="your-google-places-api-key"

python3 _data/scrape.py        # citywide sweep  → _data/raw/places.json
python3 _data/scrape_grid.py   # 3×3 grid deep-sweep (beats the 60-result/query cap)
python3 _data/classify.py      # name-signal precision filter → _data/raw/kept.json
python3 _data/build_intl.py    # schema-convert + dedupe vs hand-curated → region-google-*.json
python3 _data/merge.py         # → data.js
```

`classify.py` keeps only genuine karak/chai/qahwah/desi tea spots (Latin + Arabic +
Bengali name tokens; a bare "tea" counts only at Gulf coordinates) and hard-excludes
boba/coffee chains, premium loose-leaf retail, and Hebrew "chai" (=life) homonyms.
`build_intl.py` dedupes against the hand-curated files only, so it is idempotent.

## Verify

`node _data/verify-intl.mjs` drives the site with Playwright (needs
`npm i playwright`), checks console errors, asserts every spot sits inside its
expected geo-box, and screenshots each region into `_data/shots/`.
