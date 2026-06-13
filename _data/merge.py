#!/usr/bin/env python3
"""Merge regional research JSON files into data.js with validation + dedupe."""
import json, glob, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# rough lat/lng sanity boxes (min_lat, max_lat, min_lng, max_lng)
BOXES = {
    "US": (24.0, 49.6, -125.5, -66.0),
    "BH": (25.70, 26.40, 50.25, 50.80),
    "AE": (22.5, 26.5, 51.0, 56.5),       # United Arab Emirates
    "CA": (43.0, 44.6, -80.6, -78.8),     # Greater Toronto Area
}

def in_box(lat, lng, box):
    return box[0] <= lat <= box[1] and box[2] <= lng <= box[3]

def clean_hours(h):
    if not isinstance(h, dict):
        return None
    out = {}
    for d in DAYS:
        v = h.get(d)
        if v and isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, str) and re.match(r"^\d{1,2}:\d{2}$", x) for x in v):
            out[d] = [v[0].zfill(5), v[1].zfill(5)]
        # null/missing → closed that day
    return out or None

def main():
    spots, seen, dropped = [], set(), []
    files = sorted(glob.glob(os.path.join(HERE, "region-*.json")))
    if not files:
        sys.exit("no region-*.json files found")
    for f in files:
        try:
            arr = json.load(open(f))
        except Exception as e:
            print(f"!! {os.path.basename(f)}: parse error {e}")
            continue
        for s in arr:
            name, city, state = s.get("name"), s.get("city"), s.get("state")
            lat, lng = s.get("lat"), s.get("lng")
            country = (s.get("country") or "US").upper()
            box = BOXES.get(country)
            why = None
            if not (name and city and state):
                why = "missing name/city/state"
            elif not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                why = "missing coords"
            elif box is None:
                why = f"unknown country {country}"
            elif not in_box(lat, lng, box):
                why = f"coords outside {country} ({lat},{lng})"
            if why:
                dropped.append((name or "?", why)); continue
            key = re.sub(r"[^a-z0-9]", "", (name + str(s.get("address") or city)).lower())
            if key in seen:
                dropped.append((name, "duplicate")); continue
            seen.add(key)
            menu = []
            for m in (s.get("menu") or [])[:4]:
                try:
                    menu.append({"item": str(m["item"])[:48], "price": round(float(m["price"]), 2)})
                except Exception:
                    pass
            spot = {
                "name": str(name)[:60], "city": str(city)[:40], "state": str(state)[:2].upper(),
                "address": str(s.get("address") or "")[:90],
                "lat": round(lat, 5), "lng": round(lng, 5),
                "rating": round(float(s["rating"]), 1) if s.get("rating") else None,
                "reviews": int(s["reviews"]) if s.get("reviews") else None,
                "hours": clean_hours(s.get("hours")),
                "menu": menu,
                "tags": [t for t in (s.get("tags") or []) if isinstance(t, str)][:6],
                "note": str(s.get("note") or "")[:110],
            }
            if s.get("priceEstimated"):
                spot["priceEstimated"] = True
            if country != "US":
                spot["country"] = country
            if s.get("currency") and s["currency"] != "USD":
                spot["currency"] = s["currency"]
            spots.append(spot)

    spots.sort(key=lambda s: (s["state"], s["city"], s["name"]))
    out = "// karak.ai — curated dataset. Researched + web-verified; prices marked ~ are estimates.\n"
    out += "window.KARAK_SPOTS = " + json.dumps(spots, indent=1, ensure_ascii=False) + ";\n"
    with open(os.path.join(HERE, "..", "data.js"), "w") as f:
        f.write(out)
    print(f"wrote {len(spots)} spots from {len(files)} regions")
    states = sorted({s['state'] for s in spots})
    print("states:", " ".join(states))
    no_hours = [s["name"] for s in spots if not s["hours"]]
    if no_hours: print("no hours:", ", ".join(no_hours))
    for n, w in dropped: print(f"dropped: {n} — {w}")

if __name__ == "__main__":
    main()
