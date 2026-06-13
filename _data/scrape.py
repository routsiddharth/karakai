#!/usr/bin/env python3
"""Sweep Google Places API (New) Text Search for karak/chai/tea spots across target cities.

Billing: one request = one billed event returning up to 20 full records (incl. rating + hours).
We paginate up to 3 pages/query and dedup by place id, so the whole sweep is ~100-150 events.
Raw results cached to _data/raw/places.json so re-classification needs zero API calls.
"""
import json, os, time, ssl, urllib.request, urllib.error
import certifi

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

API_KEY = os.environ["GMAPS_KEY"]  # export GMAPS_KEY=... (Google Places API New key)
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)

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

KEYWORDS = [
    "karak", "karak tea", "karak chai", "chai", "masala chai", "cutting chai",
    "tea time", "tea stall", "chai house", "qahwah", "adeni tea", "doodh patti",
    "kashmiri chai", "pakistani tea cafe", "indian chai cafe", "desi tea",
    "sulaimani tea", "tea cafe", "milk tea karak", "chai wala",
]


def search(text_query, rect, page_token=None):
    body = {
        "textQuery": text_query,
        "pageSize": 20,
        "locationRestriction": {"rectangle": {
            "low":  {"latitude": rect[0], "longitude": rect[1]},
            "high": {"latitude": rect[2], "longitude": rect[3]},
        }},
    }
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return {}


def main():
    by_id = {}
    events = 0
    for city, rect in CITIES.items():
        for kw in KEYWORDS:
            q = f"{kw} in {city}"
            token, page = None, 0
            while page < 3:
                data = search(q, rect, token)
                events += 1
                places = data.get("places", [])
                new = 0
                for p in places:
                    pid = p.get("id")
                    if not pid:
                        continue
                    if pid not in by_id:
                        by_id[pid] = {**p, "_cities": set(), "_kws": set()}
                        new += 1
                    by_id[pid]["_cities"].add(city)
                    by_id[pid]["_kws"].add(kw)
                token = data.get("nextPageToken")
                page += 1
                if not token:
                    break
                time.sleep(1.2)  # token needs a moment to become valid
            print(f"[{city:9}] {kw:18} -> {len(places):2} results ({new} new) | total {len(by_id)}")

    out = []
    for v in by_id.values():
        v["_cities"] = sorted(v["_cities"])
        v["_kws"] = sorted(v["_kws"])
        out.append(v)
    with open(os.path.join(RAW, "places.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n{events} billed events -> {len(out)} unique places cached to raw/places.json")


if __name__ == "__main__":
    main()
