#!/usr/bin/env python3
"""
Synthetic multi-supplier hotel data generator (India-only).

Creates:
  masters.csv       hidden ground truth (one row per real hotel)
  supplier_a.csv    clean-ish feed
  supplier_b.csv    moderately messy feed (abbreviations, caps, some duplicates)
  supplier_c.csv    messiest feed (typos, reordered names, missing GPS/phone)
  suppliers.csv     supplier reliability scores (used by the ranking step)
  answer_key.csv    row_id -> master_id (NEVER show this to the matcher)
  trap_pairs.csv    pairs of DIFFERENT hotels that look alike (must NOT merge)

Run:  python generate_data.py --both     (writes data/dev  = seed 42, 100 hotels
                                                  data/test = seed 2026, 300 hotels)
      python generate_data.py --seed 7 --n 200 --out my_data

Use data/dev while building and tuning. Report final numbers ONLY on data/test.

Only the Python standard library is needed.
All hotels, phone numbers and prices are synthetic. Brand names are used
only for realism; pincodes and coordinates are approximate.
"""
import argparse
import csv
import itertools
import math
import os
import random

# ----------------------------- CONFIG ---------------------------------
CONFIG = {
    "coverage": {"A": 0.90, "B": 0.80, "C": 0.70},   # share of hotels each supplier lists
    "hard_rate": 0.20,          # share of rows made deliberately hard
    "chain_share": 0.55,        # share of hotels that are chain-branded
    "n_subbrand": 5,            # trap: Ibis vs Ibis Styles, same area, shared chain phone
    "n_chain_siblings": 3,      # trap: same brand, same city, different area, shared chain phone
    "n_same_name_same_city": 3, # trap: identical name, same city, different area
    "n_same_name_diff_city": 2, # trap: identical name, different city
    "n_near_neighbors": 5,      # trap: near-identical names ~100 m apart, different phone/stars/plot
    "b_internal_dup_rate": 0.03,  # supplier B lists the same hotel twice
}
SUPPLIERS = {
    # code: (reliability, gps_noise_m, gps_missing, phone_missing, stars_missing)
    "A": (0.95, 30, 0.05, 0.05, 0.00),
    "B": (0.88, 150, 0.12, 0.15, 0.10),
    "C": (0.80, 300, 0.25, 0.40, 0.30),
}
CANCEL = {  # supplier -> weights for the policies below
    "policies": ["Free cancellation till 48h", "Free cancellation till 24h",
                 "Partial refund", "Non-refundable"],
    "A": [0.45, 0.30, 0.15, 0.10],
    "B": [0.25, 0.30, 0.20, 0.25],
    "C": [0.10, 0.20, 0.20, 0.50],
}
PAYMENT = ["Pay now", "Pay at hotel", "Pay later (deposit)"]

# city -> (alias used by some suppliers, STD code, localities)
# localities: (name, lat, lon, pincode)  -- approximate, synthetic use only
CITIES = {
    "Mumbai": ("Bombay", "22", [
        ("Andheri East", 19.1136, 72.8697, "400069"), ("Bandra West", 19.0596, 72.8295, "400050"),
        ("Colaba", 18.9067, 72.8147, "400005"), ("Juhu", 19.1075, 72.8263, "400049"),
        ("Powai", 19.1176, 72.9060, "400076")]),
    "Delhi": ("New Delhi", "11", [
        ("Connaught Place", 28.6315, 77.2167, "110001"), ("Aerocity", 28.5562, 77.1210, "110037"),
        ("Karol Bagh", 28.6519, 77.1909, "110005"), ("Mahipalpur", 28.5448, 77.1245, "110037"),
        ("Paharganj", 28.6431, 77.2135, "110055")]),
    "Bengaluru": ("Bangalore", "80", [
        ("Koramangala", 12.9352, 77.6245, "560034"), ("Whitefield", 12.9698, 77.7500, "560066"),
        ("MG Road", 12.9756, 77.6068, "560001"), ("Indiranagar", 12.9784, 77.6408, "560038"),
        ("Electronic City", 12.8452, 77.6602, "560100")]),
    "Goa": ("Goa", "832", [
        ("Calangute", 15.5440, 73.7553, "403516"), ("Candolim", 15.5189, 73.7627, "403515"),
        ("Panaji", 15.4909, 73.8278, "403001"), ("Baga", 15.5553, 73.7517, "403516")]),
    "Jaipur": ("Jaipur", "141", [
        ("C-Scheme", 26.9124, 75.7873, "302001"), ("MI Road", 26.9170, 75.8060, "302001"),
        ("Jawahar Circle", 26.8425, 75.8070, "302017"), ("Amer Road", 26.9855, 75.8513, "302002")]),
    "Chennai": ("Madras", "44", [
        ("T Nagar", 13.0418, 80.2341, "600017"), ("Nungambakkam", 13.0569, 80.2425, "600034"),
        ("Egmore", 13.0732, 80.2609, "600008"), ("Guindy", 13.0067, 80.2206, "600032")]),
    "Hyderabad": ("Hyderabad", "40", [
        ("Banjara Hills", 17.4156, 78.4347, "500034"), ("Hitech City", 17.4435, 78.3772, "500081"),
        ("Secunderabad", 17.4399, 78.4983, "500003"), ("Gachibowli", 17.4401, 78.3489, "500032")]),
    "Kolkata": ("Calcutta", "33", [
        ("Park Street", 22.5535, 88.3521, "700016"), ("Salt Lake", 22.5867, 88.4170, "700091"),
        ("Howrah", 22.5958, 88.2636, "711101"), ("New Town", 22.5800, 88.4800, "700156")]),
    "Udaipur": ("Udaipur", "294", [
        ("Lake Pichola", 24.5760, 73.6800, "313001"), ("Fatehpura", 24.6010, 73.6800, "313001"),
        ("Hiran Magri", 24.5600, 73.7100, "313002")]),
    "Kochi": ("Cochin", "484", [
        ("Fort Kochi", 9.9658, 76.2421, "682001"), ("MG Road Ernakulam", 9.9816, 76.2999, "682016"),
        ("Edappally", 10.0261, 76.3084, "682024")]),
    "Pune": ("Pune", "20", [
        ("Koregaon Park", 18.5362, 73.8940, "411001"), ("Viman Nagar", 18.5679, 73.9143, "411014"),
        ("Hinjewadi", 18.5912, 73.7389, "411057")]),
    "Agra": ("Agra", "562", [
        ("Taj Ganj", 27.1683, 78.0419, "282001"), ("Fatehabad Road", 27.1597, 78.0380, "282001"),
        ("Sadar Bazaar", 27.1590, 77.9990, "282001")]),
}
CHAINS = [("Ibis", 3), ("Novotel", 4), ("Taj", 5), ("Lemon Tree Hotel", 4), ("Radisson Blu", 5),
          ("Hyatt Regency", 5), ("Hilton Garden Inn", 4), ("Courtyard by Marriott", 4),
          ("Fortune Select", 4), ("Ginger", 3), ("Treebo Trend", 3), ("Sarovar Portico", 4),
          ("Holiday Inn", 4), ("The Leela", 5), ("ITC", 5)]
IND_WORDS = ["Sunrise", "Royal", "Grand", "Orchid", "Shree Krishna", "Blue Lagoon", "Palm",
             "Heritage", "City Palace", "Green Park", "Silver Oak", "Paradise", "Lotus",
             "Maharaja", "Pearl", "Golden Tulip", "Moti Mahal", "Ashoka", "Rajdhani", "Sapphire"]
IND_SUFFIX = ["Residency", "Inn", "Palace", "Suites", "Regency", "Retreat", "Lodge", "Plaza"]
STREETS = ["MG Road", "Station Road", "Residency Road", "Link Road", "Ring Road",
           "Church Street", "Beach Road", "Airport Road", "Nehru Road", "Main Road"]
LANDMARKS = ["Near City Mall", "Opposite Railway Station", "Behind HDFC Bank",
             "Near Metro Station", "Opposite Bus Stand", "Near Central Market", ""]
ABBR = {"Road": "Rd", "Street": "St", "Near": "Nr.", "Opposite": "Opp.", "Behind": "Bhd."}


SUBBRANDS = {  # parent brand -> sub-brand that looks almost the same
    "Ibis": "Ibis Styles", "Hyatt Regency": "Hyatt Place", "Hilton Garden Inn": "Hilton",
    "Courtyard by Marriott": "Marriott", "Radisson Blu": "Radisson",
    "Holiday Inn": "Holiday Inn Express", "Fortune Select": "Fortune Park",
    "Lemon Tree Hotel": "Lemon Tree Premier",
}
SUFFIX_NEAR = {  # near-identical alternative endings for the 'near neighbour' trap
    "Residency": "Residence", "Regency": "Regent", "Palace": "Palace Inn", "Suites": "Suite",
    "Inn": "Inn & Suites", "Plaza": "Plaza Inn", "Lodge": "Lodge Inn", "Retreat": "Retreats",
}
CENTRAL = {}   # brand -> central reservation number (shared by every hotel of that brand)


# ----------------------------- HELPERS --------------------------------
def jitter(lat, lon, meters, rng, min_m=0.0):
    """Move a point by between min_m and `meters` in a random direction."""
    d = rng.uniform(min_m, meters)
    ang = rng.uniform(0, 2 * math.pi)
    dlat = d * math.cos(ang) / 111_000
    dlon = d * math.sin(ang) / (111_000 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def typo(text, rng):
    words = text.split()
    idx = [i for i, w in enumerate(words) if len(w) > 4]
    if not idx:
        return text
    i = rng.choice(idx)
    w = words[i]
    p = rng.randrange(1, len(w) - 1)
    if rng.random() < 0.5:                       # swap two letters
        w = w[:p] + w[p + 1] + w[p] + w[p + 2:]
    else:                                        # drop a letter
        w = w[:p] + w[p + 1:]
    words[i] = w
    return " ".join(words)


def abbreviate(text, rng):
    for full, short in ABBR.items():
        if full in text and rng.random() < 0.8:
            text = text.replace(full, short)
    return text


def central_number(brand, rng):
    parent = next((p for p, sub in SUBBRANDS.items() if brand in (p, sub)), brand)
    if parent not in CENTRAL:
        CENTRAL[parent] = "1800" + str(rng.randint(1_000_000, 9_999_999))
    return CENTRAL[parent]


def fmt_phone(digits, code, rng):
    if digits.startswith("1800"):
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}" if code == "A" else digits
    if code == "A":
        return f"+91-{digits[:2]}-{digits[2:]}"
    if code == "C" and rng.random() < 0.5:
        return f"0{digits[:5]} {digits[5:]}"
    return digits


def local_phone(std, rng):
    return std + str(rng.randint(10_000_000, 99_999_999))[: 10 - len(std)]


# ----------------------------- MASTERS --------------------------------
def make_address(loc, rng):
    plot = f"{rng.randint(1, 250)}{rng.choice(['', '/A', '/B', '-C'])}"
    street = rng.choice(STREETS)
    lm = rng.choice(LANDMARKS)
    parts = [plot, street] + ([lm] if lm else []) + [loc]
    return ", ".join(parts), street


def make_master(mid, rng, city=None, loc=None, name=None, brand=None, stars=None):
    city = city or rng.choice(list(CITIES))
    alias, std, locs = CITIES[city]
    loc = loc or rng.choice(locs)
    lname, lat, lon, pin = loc
    if name is None:
        if rng.random() < CONFIG["chain_share"]:
            brand, stars = rng.choice(CHAINS)
            name = f"{brand} {lname}"
        else:
            name = f"{rng.choice(['Hotel', 'The', 'Hotel The'])} {rng.choice(IND_WORDS)} {rng.choice(IND_SUFFIX)}"
            stars = rng.choice([2, 3, 3, 4])
    la, lo = jitter(lat, lon, 250, rng)
    addr, street = make_address(lname, rng)
    price = {2: (1200, 2200), 3: (2500, 4500), 4: (5000, 9000), 5: (11000, 25000)}[stars]
    return {
        "master_id": f"M{mid:04d}", "name": name, "brand": brand or "", "city": city,
        "locality": lname, "street": street, "address": addr, "pincode": pin,
        "lat": round(la, 6), "lon": round(lo, 6), "stars": stars,
        "phone": local_phone(std, rng), "phone_alt": local_phone(std, rng),
        "central_phone": central_number(brand, rng) if brand else "",
        "base_price_inr": rng.randrange(price[0], price[1], 100), "trap_group": "",
    }


def build_masters(n, rng):
    CENTRAL.clear()
    masters, seen = [], set()
    mid = 1

    def add(m):
        nonlocal mid
        masters.append(m)
        seen.add((m["name"], m["city"], m["locality"]))
        mid += 1

    def free(pred):
        return [m for m in masters if pred(m) and not m["trap_group"]]

    while len(masters) < n:                       # base hotels
        m = make_master(mid, rng)
        if (m["name"], m["city"], m["locality"]) not in seen:
            add(m)

    # Trap A: sub-brand in the SAME area (Ibis vs Ibis Styles), shared chain phone
    pool = free(lambda m: m["brand"] in SUBBRANDS)
    for g, base in enumerate(rng.sample(pool, min(CONFIG["n_subbrand"], len(pool))), 1):
        sub = SUBBRANDS[base["brand"]]
        loc = next(l for l in CITIES[base["city"]][2] if l[0] == base["locality"])
        twin = make_master(mid, rng, city=base["city"], loc=loc, name=f"{sub} {base['locality']}",
                           brand=sub, stars=base["stars"])
        twin["lat"], twin["lon"] = (round(x, 6) for x in jitter(base["lat"], base["lon"], 800, rng, 350))
        base["trap_group"] = twin["trap_group"] = f"T1S-{g}"
        add(twin)

    # Trap B: same brand, same city, different area, shared chain phone
    pool = free(lambda m: m["brand"])
    for g, base in enumerate(rng.sample(pool, min(CONFIG["n_chain_siblings"], len(pool))), 1):
        loc = rng.choice([l for l in CITIES[base["city"]][2] if l[0] != base["locality"]])
        sib = make_master(mid, rng, city=base["city"], loc=loc, name=f"{base['brand']} {loc[0]}",
                          brand=base["brand"], stars=base["stars"])
        base["trap_group"] = sib["trap_group"] = f"T1-{g}"
        add(sib)

    # Trap C: identical independent name, SAME city, different area
    pool = free(lambda m: not m["brand"] and len(CITIES[m["city"]][2]) > 1)
    for g, base in enumerate(rng.sample(pool, CONFIG["n_same_name_same_city"]), 1):
        loc = rng.choice([l for l in CITIES[base["city"]][2] if l[0] != base["locality"]])
        twin = make_master(mid, rng, city=base["city"], loc=loc, name=base["name"], stars=base["stars"])
        base["trap_group"] = twin["trap_group"] = f"T2S-{g}"
        add(twin)

    # Trap D: identical independent name, different city
    pool = free(lambda m: not m["brand"])
    for g, base in enumerate(rng.sample(pool, CONFIG["n_same_name_diff_city"]), 1):
        city = rng.choice([c for c in CITIES if c != base["city"]])
        twin = make_master(mid, rng, city=city, name=base["name"], stars=base["stars"])
        base["trap_group"] = twin["trap_group"] = f"T2-{g}"
        add(twin)

    # Trap E: near-identical name ~100 m away; different phone, stars and plot number
    pool = free(lambda m: not m["brand"] and m["name"].split()[-1] in SUFFIX_NEAR)
    for g, base in enumerate(rng.sample(pool, CONFIG["n_near_neighbors"]), 1):
        parts = base["name"].split()
        alt = " ".join(parts[:-1] + [SUFFIX_NEAR[parts[-1]]])
        stars = rng.choice([s for s in (2, 3, 4) if s != base["stars"]])
        nb = make_master(mid, rng, city=base["city"], name=alt, stars=stars)
        for k in ("locality", "street", "pincode"):
            nb[k] = base[k]
        nb["lat"], nb["lon"] = (round(x, 6) for x in jitter(base["lat"], base["lon"], 120, rng, 50))
        nb["address"] = base["address"].replace(base["address"].split(",")[0], str(rng.randint(251, 300)), 1)
        base["trap_group"] = nb["trap_group"] = f"T3-{g}"
        add(nb)
    return masters


# ----------------------------- FEEDS ----------------------------------
def name_for(m, code, hard, rng):
    name = m["name"]
    if m["brand"] and rng.random() < (0.10, 0.25, 0.30)["ABC".index(code)]:
        name = f"{m['brand']} {m['city']} {m['locality']}"          # chain naming variant
    if code == "A":
        if rng.random() < 0.25:
            name = name.replace(" and ", " & ")
        if name.startswith("The ") and rng.random() < 0.3:
            name = name[4:]
    elif code == "B":
        if rng.random() < 0.3 and name.startswith(("Hotel ", "The ")):
            name = name.split(" ", 1)[1]
        if rng.random() < 0.25:
            name += rng.choice([" - Best Price", f" {m['city']}", " (Book Now)"])
        if rng.random() < 0.2:
            name = name.upper()
    else:
        if rng.random() < 0.6:
            name = typo(name, rng)
        if rng.random() < 0.3:                    # move 'Hotel' to the end
            w = name.split()
            if w[0] in ("Hotel", "The"):
                name = " ".join(w[1:] + [w[0]])
        if rng.random() < 0.3:
            name = name.replace(" & ", " and ")
        if rng.random() < 0.2 and len(name.split()) >= 3:     # drop a middle/last word
            w = name.split()
            del w[rng.randrange(1, len(w))]
            name = " ".join(w)
    if hard:
        w = name.split()
        if len(w) >= 3 and rng.random() < 0.6:   # rotate words: 'Sunrise Residency Hotel'
            w = w[1:] + w[:1]
        name = typo(" ".join(w), rng)
        if rng.random() < 0.5:
            name = name.replace("Hotel ", "").replace("The ", "")
        if rng.random() < 0.3:
            name = f"{m['locality']} {name}"
    return name


def pick_phone(m, code, hard, ph_miss, rng):
    if (hard and rng.random() < 0.6) or rng.random() < ph_miss:
        return ""
    if m["central_phone"]:
        kind = rng.choices(["phone", "phone_alt", "central_phone"], [0.55, 0.20, 0.25])[0]
    else:
        kind = rng.choices(["phone", "phone_alt"], [0.75, 0.25])[0]
    return fmt_phone(m[kind], code, rng)


def make_row(m, code, idx, hard, rng):
    rel, gps_noise, gps_miss, ph_miss, st_miss = SUPPLIERS[code]
    city = m["city"]
    if code == "C" and rng.random() < 0.4:
        city = CITIES[city][0]                    # alias e.g. Bangalore / Cochin
    address = m["address"]
    if code == "B":
        address = abbreviate(address, rng)
        if rng.random() < 0.3:
            address = address.upper()
    if (code == "C" and rng.random() < 0.3) or (hard and rng.random() < 0.6):
        address = f"{m['locality']}"              # only the area, no street / plot
    pin_drop = 0.6 if hard else (0.2 if code != "A" else 0.02)
    pin = m["pincode"] if rng.random() > pin_drop else ""
    lat = lon = ""
    if hard:
        if rng.random() < 0.3:                    # a few hard rows keep a rough GPS
            lat, lon = (round(x, 6) for x in jitter(m["lat"], m["lon"], 600, rng, 300))
    elif rng.random() > gps_miss:
        noise = gps_noise if rng.random() > 0.03 else 1000   # rare outlier
        lat, lon = (round(x, 6) for x in jitter(m["lat"], m["lon"], noise, rng))
    stars = "" if rng.random() < st_miss else m["stars"]
    factor = {"A": rng.uniform(0.99, 1.03), "B": rng.uniform(0.93, 1.04), "C": rng.uniform(0.90, 1.08)}[code]
    return {
        "row_id": f"{code}-{idx:04d}", "supplier": code,
        "supplier_hotel_id": f"SUP{code}{rng.randint(100000, 999999)}",
        "name": name_for(m, code, hard, rng), "address": address, "city": city,
        "pincode": pin, "lat": lat, "lon": lon,
        "phone": pick_phone(m, code, hard, ph_miss, rng), "stars": stars,
        "price_inr": int(round(m["base_price_inr"] * factor, -1)),
        "cancellation_policy": rng.choices(CANCEL["policies"], CANCEL[code])[0],
        "payment_terms": rng.choices(PAYMENT, [0.5, 0.3, 0.2])[0],
    }


def build_feeds(masters, rng):
    rows = {c: [] for c in SUPPLIERS}
    key = []
    for m in masters:
        listed = [c for c in SUPPLIERS if rng.random() < CONFIG["coverage"][c]]
        if not listed:
            listed = [rng.choice(list(SUPPLIERS))]
        for c in listed:
            copies = 2 if (c == "B" and rng.random() < CONFIG["b_internal_dup_rate"]) else 1
            for _ in range(copies):
                hard = rng.random() < CONFIG["hard_rate"]
                r = make_row(m, c, len(rows[c]) + 1, hard, rng)
                rows[c].append(r)
                key.append({"row_id": r["row_id"], "supplier": c, "master_id": m["master_id"],
                            "difficulty": "hard" if hard else "easy", "trap_group": m["trap_group"]})
    remap = {}                                    # old row_id -> new row_id after shuffling
    for c in rows:
        rng.shuffle(rows[c])                      # hide the master order
        for i, r in enumerate(rows[c], 1):
            remap[r["row_id"]] = f"{c}-{i:04d}"
            r["row_id"] = remap[r["row_id"]]
    for k in key:
        k["row_id"] = remap[k["row_id"]]
    return rows, key


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def generate(seed, n, out):
    rng = random.Random(seed)
    os.makedirs(out, exist_ok=True)
    masters = build_masters(n, rng)
    rows, key = build_feeds(masters, rng)

    write_csv(f"{out}/masters.csv", masters)
    for c, r in rows.items():
        write_csv(f"{out}/supplier_{c.lower()}.csv", r)
    write_csv(f"{out}/answer_key.csv", key)
    write_csv(f"{out}/suppliers.csv",
              [{"supplier": c, "reliability": v[0]} for c, v in SUPPLIERS.items()])
    groups = {}
    for m in masters:
        if m["trap_group"]:
            groups.setdefault(m["trap_group"], []).append(m["master_id"])
    pairs = [{"trap_group": g, "master_id_1": x, "master_id_2": y}
             for g, ids in groups.items() for x, y in itertools.combinations(ids, 2)]
    write_csv(f"{out}/trap_pairs.csv", pairs)

    hard = sum(k["difficulty"] == "hard" for k in key)
    print(f"[{out}] seed={seed} masters: {len(masters)} | rows: "
          + ", ".join(f"{c}={len(r)}" for c, r in rows.items())
          + f" | total rows: {len(key)} | hard rows: {hard} ({hard / len(key):.0%}) | trap pairs: {len(pairs)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=100, help="base hotels (traps are added on top)")
    ap.add_argument("--out", default="data")
    ap.add_argument("--both", action="store_true",
                    help="write out/dev (seed 42, 100 hotels) and out/test (seed 2026, 300 hotels)")
    a = ap.parse_args()
    if a.both:
        generate(42, 100, f"{a.out}/dev")
        generate(2026, 300, f"{a.out}/test")
    else:
        generate(a.seed, a.n, a.out)


if __name__ == "__main__":
    main()
