#!/usr/bin/env python3
"""Classify raw Places results into genuine karak/chai/tea spots vs noise.

Lesson from the data: in NYC/Toronto the tea_house/tea_store *types* are dominated
by boba / matcha / Chinese gongfu shops, which are NOT karak/chai. The name is the
only trustworthy signal, and a bare "tea" only implies karak in the Gulf. So:

  - STRONG name tokens (karak/chai/qahwah/desi, latin + arabic + bengali) -> keep anywhere
  - bare "tea"/"shai"/tea-compound -> keep ONLY at Gulf coordinates
  - hard EXCLUDE list kills boba brands, coffee chains, premium loose-leaf retail
  - type alone never keeps anything

Reads raw/places.json -> raw/kept.json + raw/dropped.json (with reasons).
"""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))

# keep anywhere — distinctive tokens, safe as substrings (rarely inside other words)
STRONG_LATIN = [
    "karak", "qahwah", "qahwa", "gahwa", "gahwah", "kahwa",
    "adeni", "sulaimani", "sulaymani", "sulemani", "doodh patti", "doodhpatti",
    "cutting chai", "chaiwala", "chaiiwala", "chai wala", "chai walla", "kadak",
    "tapri", "chaayos", "chai point", "chai khana", "masala tea", "masala chai",
    "kashmiri", "noon chai", "irani chai", "pink tea", "filli",
    "tea time", "teatime", "tea stall", "tea wala", "tchai", "tea junction",
]
# bare "chai"/"chay" etc — require word boundaries so "chainsmoker", "lang chai
# vietnamese", "chai kee noodle" don't sneak in via context excludes below
STRONG_WORD = re.compile(r"\b(chai|chay|chaii|chaai|chaii?wala)\b")
# arabic / bengali / urdu script — keep anywhere
STRONG_SCRIPT = [
    "كرك", "چای", "چائے", "چاي", "شاي", "شای", "قهوة", "چا", "চা", "চাই",
    "چاي خانة", "كافتيريا", "شاى",
]
# bare tea words — keep ONLY in the Gulf, where they reliably mean karak.
# NB: a true \btea\b match is also accepted (see classify). We deliberately do NOT
# include "cafeteria"/"cha"/"chay" here — those drag in generic eateries; genuine
# karak/tea cafeterias already match via "karak"/\btea\b/script tokens.
GULF_TEA = ["shay", "shai", "al shay", "al chai"]

EXCLUDE = [
    # boba / bubble tea brands
    "bubble tea", "boba", "gong cha", "gongcha", "chatime", "cha time", "coco ",
    "kung fu tea", "machi machi", "sharetea", "share tea", "tiger sugar", "heytea",
    "hey tea", "yi fang", "yifang", "xing fu", "truedan", "the alley", "ten ren",
    "presotea", "happy lemon", "quickly", "tp tea", "dakasi", "möge", "moge tee",
    "vivi bubble", "bubbe tea", "catering", "chun yang", "molly tea", "machi", "kokee", "real fruit",
    "öko", "oko tea", "bubble world", "bober", "miguo", "tiger sugar", "partea",
    "alimama", "coco fresh", "fruit tea", "wushiland", "koi the", "koi thé",
    "chicha san chen", "royaltea", "shuyi", "palgong", "chatramue", "chichasan",
    "formocha", "fruiteao", "teazzi", "yaya tea", "tbaar", "moomoochaa",
    "chill tea", "young tea", "tea for u", "its tea", "baroness", "bubble baby",
    "icha tea", "fifty", "wolf forest", "chapayom", "tamsui", "qilin",
    # matcha / japanese / chinese gongfu tea (not karak)
    "matcha", "green tea", "nana's green tea", "nana’s green tea", "puerh",
    "pu erh", "pu-erh", "gong fu", "gongfu", "setsugekka", "cha-an", "kettl tea",
    "tea drunk", "tea mania", "teasthetic", "wanpo", "jin yun fu", "miss du",
    "fang gourmet", "nippon cha", "teado", "charlie's tea", "cha miao",
    "tea parlour", "tea parlor", "nom wah", "angelina", "nomad tea", "crimson tea",
    "ming yue", "lau sun", "co-op 1950", "tao tea leaf", "say tea", "ceylon company",
    "physical graffitea", "bellocq", "té company", "te company", "harney",
    "teavana", "puer", "debutea", "débutea", "teamakers", "tea mania",
    # premium loose-leaf retail
    "twg tea", "twg ", "tealand", "dilmah", "avantcha", "davidstea", "davids tea",
    "fortnum", "t2 tea", "pippins", "feel good tea", "seasons tea", "leaf cafe",
    "teapot cafe", "soul & soul", "abooz", "zak tea", "tea post", "bombay cartel",
    # coffee chains
    "starbucks", "tim horton", "costa coffee", "dunkin", "mccaf", "mcdonald",
    "second cup", "country style", "caffe nero", "peet", "blue bottle",
    "% arabica", "%arabica", "caribou coffee", "tims express",
    "coffee bean & tea leaf", "coffee bean and tea leaf",
    # not a cafe
    "supermarket", "hypermarket", "lulu ", "carrefour", "spar ", "grocery",
    "pharmacy", "petrol", "gas station", "spa ", "salon", "barber",
    "laundry", "money exchange", "western union", "art gallery", "dog cafe",
    "juice center", "juice hub", "juicy hub",
    # "chai"-substring false positives: clinics, noodle houses, BBQ, retailers
    "urgent care", "noodle", "wonton", "vietnamese", "chainsmoker", "vending",
    "steakhouse", "chai kee", "lang chai", "chai hai", "online premium",
    "chai hwa", "kashmiri pizza", "gyro &",
    # Hebrew "chai" (חי = life) — Jewish institutions, not tea
    "foundation", "lifeline", "jcc ", "krav maga", "chai defense", "acupuncture",
    "chai center", "chai centre", "ohel", "avi chai", "chai sports", "synagogue",
    "chabad", "yogic", "daniel's chai", "chai lifeline",
    # other non-cafe "chai"/"tea" homonyms
    "therapy", "nail ", "real estate", "tutoring", "academy", "school",
]


def name_of(p):
    return p.get("displayName", {}).get("text", "")


def is_gulf(p):
    loc = p.get("location", {})
    lng = loc.get("longitude", 0)
    lat = loc.get("latitude", 0)
    return 45 <= lng <= 60 and 22 <= lat <= 30


def classify(p):
    name = name_of(p)
    low = name.lower()
    sp = f" {low} "

    for ex in EXCLUDE:
        if ex in sp:
            return False, f"exclude:{ex.strip()}"

    if any(s in sp for s in STRONG_LATIN):
        return True, "strong"
    if STRONG_WORD.search(low):
        return True, "strong-word"
    if any(s in name for s in STRONG_SCRIPT):
        return True, "strong-script"
    if is_gulf(p) and (any(g in sp for g in GULF_TEA) or re.search(r"\btea\b", low)):
        return True, "gulf-tea"
    return False, f"no-signal:{p.get('primaryType','?')}"


def main():
    raw = json.load(open(os.path.join(HERE, "raw", "places.json")))
    kept, dropped = [], []
    for p in raw:
        if p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
            dropped.append({**p, "_reason": "closed"}); continue
        ok, reason = classify(p)
        (kept if ok else dropped).append({**p, "_reason": reason})
    json.dump(kept, open(os.path.join(HERE, "raw", "kept.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(dropped, open(os.path.join(HERE, "raw", "dropped.json"), "w"), indent=1, ensure_ascii=False)
    print(f"kept {len(kept)} / dropped {len(dropped)}")
    print("keep reasons:", dict(collections.Counter(k["_reason"] for k in kept)))
    cc = collections.Counter()
    for k in kept:
        for c in k.get("_cities", []):
            cc[c] += 1
    print("kept by city:", dict(cc))


if __name__ == "__main__":
    main()
