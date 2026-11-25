#!/usr/bin/env python3
"""
Naive baseline matchers = the FLOOR your real engine must beat.

    python baseline.py --data data/dev
    python baseline.py --data data/test

Prints a score table for three simple matchers (standard library only):
  1. exact name + city
  2. phone number only
  3. fuzzy name + GPS (what a quick hackathon script would do)
Your final pitch number is: "naive baseline X  ->  our engine Y".
"""
import argparse
import csv
import difflib
import itertools
import math
import os
import re

from evaluate import evaluate, read_csv

ALIAS = {"bombay": "mumbai", "new delhi": "delhi", "bangalore": "bengaluru",
         "madras": "chennai", "calcutta": "kolkata", "cochin": "kochi"}


def city(c):
    c = c.lower().strip()
    return ALIAS.get(c, c)


def norm(name):
    n = re.sub(r"\s*[-(].*$", "", name.lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(t for t in n.split() if t not in ("hotel", "the", "and"))


def digits(p):
    return re.sub(r"\D", "", p)[-8:]


def gps(r):
    return (float(r["lat"]), float(r["lon"])) if r["lat"] else None


def metres(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


class UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def exact_name(rows):
    return {r["row_id"]: (norm(r["name"]), city(r["city"])) for r in rows}


def phone_only(rows):
    return {r["row_id"]: (digits(r["phone"]) if r["phone"] else r["row_id"]) for r in rows}


def fuzzy_gps(rows, name_threshold=0.85, max_metres=600):
    uf = UnionFind()
    for r in rows:
        uf.find(r["row_id"])
    for a, b in itertools.combinations(rows, 2):
        if a["supplier"] == b["supplier"] or city(a["city"]) != city(b["city"]):
            continue
        if difflib.SequenceMatcher(None, norm(a["name"]), norm(b["name"])).ratio() < name_threshold:
            continue
        ga, gb = gps(a), gps(b)
        if ga and gb and metres(ga, gb) > max_metres:
            continue
        uf.union(a["row_id"], b["row_id"])
    return {r["row_id"]: uf.find(r["row_id"]) for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dev")
    a = ap.parse_args()
    rows = []
    for c in "abc":
        rows += read_csv(os.path.join(a.data, f"supplier_{c}.csv"))
    key = read_csv(os.path.join(a.data, "answer_key.csv"))
    traps = read_csv(os.path.join(a.data, "trap_pairs.csv"))

    print(f"\nBaselines on {a.data}  ({len(rows)} rows)")
    print(f"{'matcher':26s}{'precision':>10s}{'recall':>9s}{'f1':>7s}{'hard recall':>13s}{'trap merges':>13s}")
    for name, fn in (("exact name + city", exact_name), ("phone only", phone_only),
                     ("fuzzy name + GPS", fuzzy_gps)):
        assign = fn(rows)
        pred = [{"row_id": r["row_id"], "cluster_id": assign[r["row_id"]]} for r in rows]
        res = evaluate(pred, key, traps)
        print(f"{name:26s}{res['precision']:10.2f}{res['recall']:9.2f}{res['f1']:7.2f}"
              f"{res['hard-row recall']:13.2f}{res['trap false merges']:>8d}/{res['trap pairs total']}")
    print()


if __name__ == "__main__":
    main()
