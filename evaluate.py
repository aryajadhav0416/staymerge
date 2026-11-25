#!/usr/bin/env python3
"""
Score a hotel matcher against the hidden answer key.

Your matcher must write a predictions file with two columns:
    row_id,cluster_id
Rows that your matcher thinks are the SAME hotel share one cluster_id
(any string or number). Every row from the supplier files should appear once.

Usage:
    python evaluate.py --pred predictions.csv --data sample_data
    python evaluate.py --selftest --data sample_data     (checks this script itself)

Metrics (pairwise, the standard way to score deduplication):
    precision        of the pairs we merged, how many were truly the same hotel
    recall           of the truly-same pairs, how many we merged
    f1               balance of the two
    trap false merges  different-but-look-alike hotels we wrongly merged (want 0)
    hard-row recall  recall on pairs that involve at least one hard row
Only the standard library is needed.
"""
import argparse
import csv
import itertools
import os
import sys
from collections import defaultdict


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pairs_from_groups(groups):
    """groups: {label: [row_ids]} -> set of frozenset({a, b}) for rows sharing a label."""
    out = set()
    for ids in groups.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            out.add((a, b))
    return out


def evaluate(pred_rows, key_rows, trap_rows):
    truth_master = {r["row_id"]: r["master_id"] for r in key_rows}
    hard = {r["row_id"] for r in key_rows if r["difficulty"] == "hard"}

    pred_cluster, missing_rows = {}, []
    for r in pred_rows:
        pred_cluster[r["row_id"]] = r["cluster_id"]
    missing_rows = [rid for rid in truth_master if rid not in pred_cluster]
    unknown_rows = [rid for rid in pred_cluster if rid not in truth_master]

    # rows the matcher forgot are treated as singletons (each its own cluster)
    for i, rid in enumerate(missing_rows):
        pred_cluster[rid] = f"__missing_{i}"
    for rid in unknown_rows:
        del pred_cluster[rid]

    true_groups, pred_groups = defaultdict(list), defaultdict(list)
    for rid, m in truth_master.items():
        true_groups[m].append(rid)
        pred_groups[pred_cluster[rid]].append(rid)
    true_pairs = pairs_from_groups(true_groups)
    pred_pairs = pairs_from_groups(pred_groups)

    tp = len(true_pairs & pred_pairs)
    precision = tp / len(pred_pairs) if pred_pairs else 1.0
    recall = tp / len(true_pairs) if true_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    hard_true = {p for p in true_pairs if p[0] in hard or p[1] in hard}
    hard_recall = len(hard_true & pred_pairs) / len(hard_true) if hard_true else 1.0

    # false merges between look-alike hotels (trap pairs)
    trap = {frozenset((t["master_id_1"], t["master_id_2"])) for t in trap_rows}
    wrong_masters = set()
    for a, b in pred_pairs - true_pairs:
        ma, mb = truth_master[a], truth_master[b]
        if ma != mb and frozenset((ma, mb)) in trap:
            wrong_masters.add(frozenset((ma, mb)))
    other_false = len(pred_pairs - true_pairs)

    return {
        "rows scored": len(truth_master),
        "true hotels": len(true_groups),
        "predicted hotels": len(pred_groups),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "hard-row recall": hard_recall,
        "trap pairs total": len(trap),
        "trap false merges": len(wrong_masters),
        "all false-merged row pairs": other_false,
        "rows missing from predictions": len(missing_rows),
        "unknown rows ignored": len(unknown_rows),
    }


def print_report(res):
    print("\n=== Matcher evaluation ===")
    for k, v in res.items():
        print(f"{k:32s} {v:.3f}" if isinstance(v, float) else f"{k:32s} {v}")
    print()
    if res["trap false merges"]:
        print(f"WARNING: {res['trap false merges']} look-alike hotels were wrongly merged.")
    if res["rows missing from predictions"]:
        print("WARNING: some rows were missing from your predictions file.")


def selftest(key_rows, trap_rows):
    """Checks the scorer itself with three predictions whose answers we already know."""
    ok = True

    def check(name, pred, cond):
        nonlocal ok
        res = evaluate(pred, key_rows, trap_rows)
        passed = cond(res)
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: P={res['precision']:.2f} "
              f"R={res['recall']:.2f} trap_merges={res['trap false merges']}")

    perfect = [{"row_id": k["row_id"], "cluster_id": k["master_id"]} for k in key_rows]
    check("perfect matcher", perfect,
          lambda r: r["precision"] == 1 and r["recall"] == 1 and r["trap false merges"] == 0)

    singles = [{"row_id": k["row_id"], "cluster_id": k["row_id"]} for k in key_rows]
    check("matcher that merges nothing", singles,
          lambda r: r["recall"] == 0 and r["precision"] == 1)

    trap_group = {k["master_id"]: k["trap_group"] for k in key_rows if k["trap_group"]}
    lazy = [{"row_id": k["row_id"], "cluster_id": trap_group.get(k["master_id"], k["master_id"])}
            for k in key_rows]
    check("matcher that merges every trap pair", lazy,
          lambda r: r["trap false merges"] == len(trap_rows) and r["recall"] == 1
          and r["precision"] < 1)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", help="predictions.csv with row_id,cluster_id")
    ap.add_argument("--data", default="data", help="folder with answer_key.csv and trap_pairs.csv")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    key_rows = read_csv(os.path.join(a.data, "answer_key.csv"))
    trap_rows = read_csv(os.path.join(a.data, "trap_pairs.csv"))

    if a.selftest:
        sys.exit(0 if selftest(key_rows, trap_rows) else 1)
    if not a.pred:
        ap.error("--pred is required (or use --selftest)")
    pred_rows = read_csv(a.pred)
    if not pred_rows or not {"row_id", "cluster_id"} <= set(pred_rows[0]):
        sys.exit("predictions file needs columns: row_id,cluster_id")
    print_report(evaluate(pred_rows, key_rows, trap_rows))


if __name__ == "__main__":
    main()
