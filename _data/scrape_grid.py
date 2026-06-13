#!/usr/bin/env python3
"""Deep supplementary sweep: subdivide each city bbox into a grid so dense areas
that the citywide queries truncated (60-result cap) get fresh per-cell budgets.

Appends newly-discovered place ids into raw/places.json (dedup by id). Re-run
classify.py + build_intl.py afterwards.
"""
import json, os, time, ssl, urllib.request, urllib.error, certifi

SSL_CTX = ssl.create_default_context(cafile=certifi.where())
API_KEY = os.environ["GMAPS_KEY"]  # export GMAPS_KEY=... (Google Places API New key)
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw", "places.json")

FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.regularOpeningHours",
    "places.primaryType", "places.types", "places.businessStatus",
    "places.googleMapsUri", "nextPageToken",
])

# (low_lat, low_lng, high_lat, high_lng)
CITIES = {
    "nyc":       (40.49, -74.27, 40.92, -73.68),
    "bahrain":   (25.78,  50.30, 26.40,  50.72),
    "toronto":   (43.40, -79.65, 43.90, -79.12),
    "dubai":     (24.75,  54.85, 25.40,  55.65),
    "abudhabi":  (24.28,  54.20, 24.75,  54.85),
}
# high-yield core keywords most likely to have been truncated
KEYWORDS = ["karak", "chai", "tea", "tea time", "masala chai", "qahwah",
            "cutting chai", "pakistani tea", "cafeteria karak", "chai cafe"]
GRID = 3  # 3x3 cells per city


def search(text_query, rect, page_token=None):
    body = {"textQuery": text_query, "pageSize": 20,
            "locationRestriction": {"rectangle": {
                "low":  {"latitude": rect[0], "longitude": rect[1]},
                "high": {"latitude": rect[2], "longitude": rect[3]}}}}
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY,
                 "X-Goog-FieldMask": FIELD_MASK}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:160]}")
        return {}


def cells(rect, n):
    lat0, lng0, lat1, lng1 = rect
    dlat, dlng = (lat1 - lat0) / n, (lng1 - lng0) / n
    for i in range(n):
        for j in range(n):
            yield (lat0 + i * dlat, lng0 + j * dlng,
                   lat0 + (i + 1) * dlat, lng0 + (j + 1) * dlng)


def main():
    existing = {p["id"]: p for p in json.load(open(RAW)) if p.get("id")}
    for p in existing.values():
        p["_cities"] = set(p.get("_cities", []))
        p["_kws"] = set(p.get("_kws", []))
    start = len(existing)
    events = 0
    for city, rect in CITIES.items():
        before = len(existing)
        for cell in cells(rect, GRID):
            for kw in KEYWORDS:
                token, page = None, 0
                while page < 3:
                    data = search(f"{kw} in {city}", cell, token)
                    events += 1
                    for p in data.get("places", []):
                        pid = p.get("id")
                        if not pid:
                            continue
                        if pid not in existing:
                            existing[pid] = {**p, "_cities": set(), "_kws": set()}
                        existing[pid]["_cities"].add(city)
                        existing[pid]["_kws"].add(kw)
                    token = data.get("nextPageToken")
                    page += 1
                    if not token:
                        break
                    time.sleep(1.2)
        print(f"[{city:9}] +{len(existing)-before} new (total {len(existing)})")

    out = []
    for v in existing.values():
        v["_cities"] = sorted(v["_cities"])
        v["_kws"] = sorted(v["_kws"])
        out.append(v)
    json.dump(out, open(RAW, "w"), indent=1, ensure_ascii=False)
    print(f"\n{events} billed events -> +{len(existing)-start} new, {len(existing)} total unique")


if __name__ == "__main__":
    main()
