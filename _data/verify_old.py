#!/usr/bin/env python3
"""Verify the hand-curated (non-Google) region files against the Google Places
API. Each spot is looked up by name near its claimed coordinates; if a real
matching place is found we KEEP it (refreshing coords/rating/reviews/hours/
address from Google while preserving the hand-added menu/note/tags). If nothing
matches, the spot was unreliable and is DROPPED.

One billed Text Search event per spot. Run:  GMAPS_KEY=... python3 verify_old.py
"""
import json, os, glob, time, ssl, math, re, urllib.request, urllib.error
import certifi
from build_intl import conv_hours, haversine

# Light normalization for verification. Unlike the dedup tokenizer we KEEP
# distinctive words like "qahwah/haraz/karak/chai/coffee" — only drop generic
# corporate/filler tokens — so names made of those words still match. Anything
# after an em/en dash is a hand-added branch label (" — West Dearborn") that
# Google won't have, so we trim it before tokenizing.
GENERIC = {"the", "and", "of", "by", "llc", "co", "inc", "wll", "llp",
           "company", "ltd", "a", "an"}


def vtokens(name):
    name = re.split(r"\s[—–-]\s", name)[0]  # drop " — branch" suffix
    toks = re.findall(r"[a-z0-9]+", name.lower())
    return set(t for t in toks if t not in GENERIC and len(t) > 1)


def jaccard(a, b):
    return (len(a & b) / len(a | b)) if (a and b) else 0.0


def contain(a, b):
    """How fully the smaller name sits inside the larger — catches subset names
    like 'Karak House Coffee Co' vs 'Karak House Coffee Co | Tea & Chai'."""
    return (len(a & b) / min(len(a), len(b))) if (a and b) else 0.0

SSL_CTX = ssl.create_default_context(cafile=certifi.where())
API_KEY = os.environ["GMAPS_KEY"]
HERE = os.path.dirname(os.path.abspath(__file__))

# the curated files to verify (everything except the Google sweep output)
TARGETS = sorted(
    f for f in glob.glob(os.path.join(HERE, "region-*.json"))
    if not os.path.basename(f).startswith("region-google-")
)

FIELD_MASK = ",".join([
    "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.regularOpeningHours",
    "places.businessStatus",
])


def search(text_query, lat, lng):
    body = {
        "textQuery": text_query,
        "pageSize": 10,
        "locationBias": {"circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": 5000.0,
        }},
    }
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
        print(f"  HTTP {e.code}: {e.read().decode()[:160]}")
        return {}
    except Exception as e:
        print(f"  ERR {e}")
        return {}


def match(spot, places):
    """Return the (place, distance, jaccard) that confirms this spot, or None.

    Confirmed when a Google result is either right on top of the claimed coords,
    or shares the name and is plausibly nearby. Hand-curated coords are often
    imprecise, so the name-match bands tolerate larger distances. As a final
    tier, a near-exact name match is accepted at long range ONLY when it is the
    single such candidate in the search area — that disambiguates a genuinely-
    mislocated spot from a dense multi-branch chain where we can't tell which
    branch was meant."""
    sloc = (spot["lat"], spot["lng"])
    st = vtokens(spot["name"])
    cands = []
    for p in places:
        ploc = p.get("location", {})
        pll = (ploc.get("latitude"), ploc.get("longitude"))
        if pll[0] is None or p.get("businessStatus") == "CLOSED_PERMANENTLY":
            continue
        d = haversine(sloc, pll)
        pt = vtokens(p.get("displayName", {}).get("text", ""))
        cands.append((p, d, jaccard(st, pt), contain(st, pt)))

    near = [c for c in cands if (
        c[1] < 200                          # coords trustworthy, accept
        or (c[1] < 700 and c[2] >= 0.34)    # decent name match nearby
        or (c[1] < 2000 and c[2] >= 0.6))]  # strong name match, imprecise coords
    if near:
        return min(near, key=lambda c: c[1])

    # final tier: exactly one near-exact-name place in the area -> relocate to it.
    # containment (not jaccard) so a subset name still counts as near-exact.
    strong = [c for c in cands if c[3] >= 0.8 and c[1] < 6000]
    if len(strong) == 1:
        return strong[0]
    return None


def refresh(spot, p):
    """Keep curated name/menu/note/tags; refresh location & live facts."""
    loc = p["location"]
    out = dict(spot)
    out["lat"] = round(loc["latitude"], 5)
    out["lng"] = round(loc["longitude"], 5)
    out["address"] = p.get("formattedAddress", spot.get("address", ""))
    if p.get("rating") is not None:
        out["rating"] = p["rating"]
    if p.get("userRatingCount") is not None:
        out["reviews"] = p["userRatingCount"]
    gh = conv_hours(p.get("regularOpeningHours"))
    if gh:
        out["hours"] = gh
    return out


def main():
    grand_keep = grand_drop = 0
    for f in TARGETS:
        arr = json.load(open(f))
        kept, dropped = [], []
        for s in arr:
            lat, lng = s.get("lat"), s.get("lng")
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                dropped.append((s.get("name", "?"), "no coords"))
                continue
            q = f"{s['name']} {s.get('city','')}".strip()
            data = search(q, lat, lng)
            m = match(s, data.get("places", []))
            if m:
                kept.append(refresh(s, m[0]))
            else:
                dropped.append((s["name"], "unverified"))
            time.sleep(0.15)
        json.dump(kept, open(f, "w"), indent=1, ensure_ascii=False)
        grand_keep += len(kept)
        grand_drop += len(dropped)
        print(f"\n== {os.path.basename(f)}: kept {len(kept)}/{len(arr)}")
        for n, why in dropped:
            print(f"   drop: {n} — {why}")
    print(f"\nTOTAL kept {grand_keep}, dropped {grand_drop}")


if __name__ == "__main__":
    main()
