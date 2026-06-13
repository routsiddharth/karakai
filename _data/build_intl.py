#!/usr/bin/env python3
"""Convert classified Google places (raw/kept.json) into karak.ai region JSON.

- assigns region/state/country/currency from the scrape rectangle + coords
- converts Google opening periods -> the {mon:[open,close],...} schema (wrapped past-midnight)
- dedups against the EXISTING data.js spots and against each other by proximity+name,
  so we only add genuinely-new locations (existing hand-curated entries are untouched)
- writes region-google-<key>.json files that merge.py then folds into data.js
"""
import json, os, re, math, glob

HERE = os.path.dirname(os.path.abspath(__file__))

# region rectangle -> (state, country, currency). NYC state resolved per-address.
REGION_META = {
    "bahrain":  ("BH", "BH", "BHD"),
    "dubai":    ("DU", "AE", "AED"),
    "abudhabi": ("AD", "AE", "AED"),
    "toronto":  ("ON", "CA", "CAD"),
    # nyc handled specially (NY vs NJ)
}


def name_of(p):
    return p.get("displayName", {}).get("text", "").strip()


def haversine(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dla, dlo = la2 - la1, lo2 - lo1
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def norm_tokens(name):
    toks = re.findall(r"[a-z0-9]+", name.lower())
    stop = {"the", "cafe", "coffee", "co", "llc", "wll", "restaurant", "and",
            "of", "by", "shop", "house", "tea", "chai", "karak"}
    return set(t for t in toks if t not in stop and len(t) > 1)


def same_place(a_name, a_loc, b_name, b_loc):
    d = haversine(a_loc, b_loc)
    if d < 35:
        return True
    if d < 160:
        ta, tb = norm_tokens(a_name), norm_tokens(b_name)
        if ta and tb:
            j = len(ta & tb) / len(ta | tb)
            if j >= 0.34:
                return True
    return False


def conv_hours(goog):
    """Google regularOpeningHours -> {day:[open,close]} wrapped past midnight."""
    if not isinstance(goog, dict):
        return None
    periods = goog.get("periods")
    DAYMAP = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat"}
    if not periods:
        return None
    # 24/7: a single period with open day0 00:00 and no close
    if len(periods) == 1 and "close" not in periods[0]:
        op = periods[0].get("open", {})
        if op.get("hour", 0) == 0 and op.get("minute", 0) == 0:
            return {d: ["00:00", "24:00"] for d in DAYMAP.values()}
    out = {}
    for per in periods:
        op, cl = per.get("open"), per.get("close")
        if not op or not cl:
            continue
        d = DAYMAP.get(op.get("day"))
        if not d:
            continue
        o = f"{op.get('hour',0):02d}:{op.get('minute',0):02d}"
        ch, cm = cl.get("hour", 0), cl.get("minute", 0)
        # close at midnight on the *same* logical day -> 24:00; otherwise wrapped HH:MM
        if cl.get("day") != op.get("day") and ch == 0 and cm == 0:
            c = "24:00"
        else:
            c = f"{ch:02d}:{cm:02d}"
        # keep first open / last close if a day already present
        if d in out:
            out[d] = [min(out[d][0], o), out[d][1] if out[d][1] >= c or c == "24:00" else c]
        else:
            out[d] = [o, c]
    return out or None


# Bahrain town centroids — addresses are too messy (plus-codes, road numbers,
# Arabic) to parse, so assign the nearest known town instead.
BH_TOWNS = {
    "Manama": (26.2235, 50.5876),
    "Adliya": (26.2080, 50.5920), "Juffair": (26.2110, 50.6010),
    "Seef": (26.2360, 50.5430),
    "Muharraq": (26.2572, 50.6119), "Busaiteen": (26.2720, 50.6058),
    "Arad": (26.2510, 50.6230), "Galali": (26.2660, 50.6470),
    "Al Hidd": (26.2430, 50.6540), "Riffa": (26.1300, 50.5550),
    "East Riffa": (26.1230, 50.5750), "Hamad Town": (26.1150, 50.5060),
    "Isa Town": (26.1730, 50.5470), "Sitra": (26.1540, 50.6210),
    "Tubli": (26.2130, 50.5550), "Salmabad": (26.1700, 50.5230),
    "Sanad": (26.1530, 50.5470), "Jidhafs": (26.2190, 50.5470),
    "Budaiya": (26.2150, 50.4870), "Saar": (26.1900, 50.5050),
    "Janabiyah": (26.2080, 50.4960), "A'ali": (26.1560, 50.5240),
    "Zallaq": (26.0470, 50.4830), "Malkiya": (26.1030, 50.4520),
    "Diraz": (26.2200, 50.4760), "Hamala": (26.1700, 50.4830),
}
OTHER_EMIRATES = ["Sharjah", "Ajman", "Umm Al Quwain", "Umm al Quwain",
                  "Ras Al Khaimah", "Ras al Khaimah", "Fujairah", "Al Ain"]


def nearest_town(lat, lng):
    best, bd = "Bahrain", 1e9
    for t, (tlat, tlng) in BH_TOWNS.items():
        d = haversine((lat, lng), (tlat, tlng))
        if d < bd:
            best, bd = t, d
    return best if bd < 6000 else "Bahrain"


def uae_area(addr, emirate):
    """Pull the neighbourhood just before the emirate from a ' - ' UAE address."""
    parts = [p.strip() for p in addr.split(" - ")]
    for i, p in enumerate(parts):
        if emirate in p and i > 0:
            area = parts[i - 1]
            # skip plus-codes, unit numbers, and Abu Dhabi sector grid codes
            # (Zone 1 / ME10 / W4 / E13 02) which aren't real place names
            if (re.match(r"^[0-9A-Z]{4}\+", area) or re.match(r"^[\d\s]+$", area)
                    or re.match(r"^(Zone\s*\d+|[A-Z]{1,3}\s*-?\s*\d+(\s*-?\s*\d+)?)$", area)):
                continue
            return area[:40]
    return emirate


def parse_city(addr, region, lat, lng):
    if region == "bahrain":
        return nearest_town(lat, lng)
    parts = [p.strip() for p in (addr or "").split(",")]
    if region in ("nyc", "toronto"):
        for i, p in enumerate(parts):
            if re.search(r"\b(NY|NJ|ON)\b", p):
                return parts[i - 1] if i > 0 else parts[0]
        return parts[-3] if len(parts) >= 3 else (parts[0] if parts else region.title())
    if region == "dubai":
        return uae_area(addr, "Dubai")
    if region == "abudhabi":
        return uae_area(addr, "Abu Dhabi")
    return parts[0] if parts else region.title()


def main():
    # Dedup against the HAND-CURATED region files only (not data.js, and not our
    # own region-google-* output — otherwise re-running would dedup against last
    # run's output and shrink the set). This keeps the Google set reproducible.
    exist_idx = []
    for f in glob.glob(os.path.join(HERE, "region-*.json")):
        if os.path.basename(f).startswith("region-google-"):
            continue
        for s in json.load(open(f)):
            if isinstance(s.get("lat"), (int, float)) and isinstance(s.get("lng"), (int, float)):
                exist_idx.append((s.get("name", ""), (s["lat"], s["lng"])))

    kept = json.load(open(os.path.join(HERE, "raw", "kept.json")))

    buckets = {}      # region-file key -> list of spots
    added = []        # (name, loc) accumulator for new-vs-new dedup
    skipped_dup = 0

    for p in kept:
        loc = p.get("location", {})
        lat, lng = loc.get("latitude"), loc.get("longitude")
        if lat is None or lng is None:
            continue
        region = (p.get("_cities") or [None])[0]
        addr = p.get("formattedAddress", "")
        if region == "nyc":
            state = "NJ" if re.search(r"\bNJ\b", addr) else "NY"
            country, currency = "US", "USD"
        elif region in ("dubai", "abudhabi"):
            # drop spots that the rectangle bled into from neighbouring emirates
            if any(e in addr for e in OTHER_EMIRATES):
                skipped_dup += 1
                continue
            state, country, currency = REGION_META[region]
        elif region in REGION_META:
            state, country, currency = REGION_META[region]
        else:
            continue
        name = name_of(p)
        if not name:
            continue
        nloc = (lat, lng)

        # dedup vs existing
        dup = any(same_place(name, nloc, en, el) for en, el in exist_idx)
        if dup:
            skipped_dup += 1
            continue
        # dedup vs already-added new spots
        if any(same_place(name, nloc, an, al) for an, al in added):
            skipped_dup += 1
            continue
        added.append((name, nloc))

        city = parse_city(addr, region, lat, lng)
        spot = {
            "name": name,
            "city": city,
            "state": state,
            "address": p.get("formattedAddress", ""),
            "lat": lat, "lng": lng,
            "rating": p.get("rating"),
            "reviews": p.get("userRatingCount"),
            "hours": conv_hours(p.get("regularOpeningHours")),
            "menu": [],
            "tags": [],
            "note": "",
            "_gmaps": p.get("googleMapsUri", ""),
            "_primaryType": p.get("primaryType", ""),
        }
        if country != "US":
            spot["country"] = country
        if currency != "USD":
            spot["currency"] = currency

        key = region if region != "nyc" else "nyc"
        buckets.setdefault(key, []).append(spot)

    for key, arr in buckets.items():
        arr.sort(key=lambda s: (s["city"], s["name"]))
        path = os.path.join(HERE, f"region-google-{key}.json")
        json.dump(arr, open(path, "w"), indent=1, ensure_ascii=False)
        print(f"region-google-{key}.json: {len(arr)} new spots")
    print(f"skipped {skipped_dup} duplicates (vs existing + each other)")


if __name__ == "__main__":
    main()
