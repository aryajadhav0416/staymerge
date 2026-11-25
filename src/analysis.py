"""Developer analysis tools (permitted to inspect answer_key.csv and ground truth)."""
import argparse
import csv
import itertools
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from src.candidates import make_candidates
from src.normalize import load_rows, prepare
from src.rules import band, pair_features, score_pair


def load_true_pairs(data_dir: str) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]]]:
    """Load ground truth pairs and hard true pairs from answer_key.csv."""
    key_path = os.path.join(data_dir, "answer_key.csv")
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"answer_key.csv not found at {key_path}")

    groups = defaultdict(list)
    hard_rows = set()
    with open(key_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            groups[r["master_id"]].append(r["row_id"])
            if r.get("difficulty") == "hard":
                hard_rows.add(r["row_id"])

    true_pairs = set()
    for ids in groups.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            true_pairs.add((a, b))

    hard_pairs = {p for p in true_pairs if p[0] in hard_rows or p[1] in hard_rows}
    return true_pairs, hard_pairs


def candidate_recall(data_dir: str) -> None:
    """Evaluate recall of true hotel pairs captured by candidate generator."""
    df = load_rows(data_dir)
    prep = prepare(df)
    cand_df = make_candidates(prep)

    cand_pairs = set()
    for _, row in cand_df.iterrows():
        a, b = row["row_id_a"], row["row_id_b"]
        cand_pairs.add((a, b) if a < b else (b, a))

    true_pairs, hard_pairs = load_true_pairs(data_dir)

    captured = cand_pairs & true_pairs
    recall = len(captured) / len(true_pairs) if true_pairs else 1.0

    captured_hard = cand_pairs & hard_pairs
    hard_recall = len(captured_hard) / len(hard_pairs) if hard_pairs else 1.0

    print(f"Dataset: {data_dir}")
    print(f"Total true pairs: {len(true_pairs)}")
    print(f"Captured true pairs: {len(captured)}")
    print(f"Candidate Recall: {recall:.4f} ({recall * 100:.2f}%)")
    print(f"Hard true pairs: {len(hard_pairs)}")
    print(f"Captured hard pairs: {len(captured_hard)}")
    print(f"Candidate Hard Recall: {hard_recall:.4f} ({hard_recall * 100:.2f}%)")


def band_recall(data_dir: str) -> None:
    """Evaluate distribution of truly-same and truly-different pairs across score bands."""
    df = load_rows(data_dir)
    prep = prepare(df)
    cand_df = make_candidates(prep)

    records_by_id = {r["row_id"]: r for r in prep.to_dict("records")}
    true_pairs, _ = load_true_pairs(data_dir)

    counts = {
        "match": {"same": 0, "diff": 0},
        "unsure": {"same": 0, "diff": 0},
        "no_match": {"same": 0, "diff": 0},
    }

    for _, row in cand_df.iterrows():
        id_a, id_b = row["row_id_a"], row["row_id_b"]
        pair_key = (id_a, id_b) if id_a < id_b else (id_b, id_a)
        is_same = pair_key in true_pairs

        feats = pair_features(records_by_id[id_a], records_by_id[id_b])
        sc = score_pair(feats)
        b = band(sc)

        if is_same:
            counts[b]["same"] += 1
        else:
            counts[b]["diff"] += 1

    print(f"\n--- Band Recall & Distribution ({data_dir}) ---")
    print(f"{'Band':<10} {'Truly-Same':>12} {'Truly-Different':>16} {'Total Pairs':>12}")
    print("-" * 54)
    for b in ["match", "unsure", "no_match"]:
        same = counts[b]["same"]
        diff = counts[b]["diff"]
        tot = same + diff
        print(f"{b:<10} {same:>12} {diff:>16} {tot:>12}")
    print("-" * 54)
    tot_same = sum(counts[b]["same"] for b in counts)
    tot_diff = sum(counts[b]["diff"] for b in counts)
    print(f"{'Total':<10} {tot_same:>12} {tot_diff:>16} {tot_same + tot_diff:>12}\n")


def classify_cause(
    row_a: Dict[str, Any],
    row_b: Dict[str, Any],
    dec: Dict[str, Any],
    is_false_merge: bool,
) -> str:
    """Derive error cause strictly from the pair's own signals.

    Allowed causes:
    - cluster conflict
    - llm wrong
    - gps far (known GPS over 450 m apart)
    - missing gps
    - central phone
    - same name
    - name noise
    """
    feats = pair_features(row_a, row_b)
    name_a = (row_a.get("norm_name") or "").lower()
    name_b = (row_b.get("norm_name") or "").lower()
    gps_dist = feats.get("gps_distance_m")

    # Cluster conflict: pair had final_decision=true in decisions.csv but was not merged in predictions
    if not is_false_merge and dec.get("final_decision") == "true":
        return "cluster conflict"

    # LLM wrong: LLM made a decision contrary to truth
    llm_same = dec.get("llm_same", "")
    if is_false_merge and llm_same == "True":
        return "llm wrong"
    if not is_false_merge and llm_same == "False":
        return "llm wrong"

    # Known GPS over 450 m apart
    if gps_dist is not None and gps_dist > 450.0:
        return "gps far"

    # Missing GPS
    if not row_a.get("gps") or not row_b.get("gps"):
        return "missing gps"

    # Central phone proving nothing
    if row_a.get("phone_is_central") or row_b.get("phone_is_central"):
        return "central phone"

    # Same name vs name noise
    if name_a and name_b and name_a == name_b:
        return "same name"

    return "name noise"


def export_errors(
    data_dir: str = "data/dev",
    pred_path: str = "outputs/predictions.csv",
    decisions_path: str = "outputs/decisions.csv",
    output_md: str = "outputs/errors.md",
) -> None:
    """Generate errors.md listing all false merges and missed matches with signal-derived causes."""
    # 1. Load answer key metadata
    key_path = os.path.join(data_dir, "answer_key.csv")
    truth_master = {}
    row_trap = {}
    difficulty = {}
    with open(key_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            truth_master[r["row_id"]] = r["master_id"]
            row_trap[r["row_id"]] = r.get("trap_group", "")
            difficulty[r["row_id"]] = r.get("difficulty", "")

    # Ground truth pairs
    true_groups = defaultdict(list)
    for rid, m in truth_master.items():
        true_groups[m].append(rid)

    true_pairs = set()
    for ids in true_groups.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            true_pairs.add((a, b))

    # 2. Load predictions
    pred_clusters = defaultdict(list)
    if os.path.exists(pred_path):
        with open(pred_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                pred_clusters[r["cluster_id"]].append(r["row_id"])
    pred_pairs = set()
    for ids in pred_clusters.values():
        for a, b in itertools.combinations(sorted(ids), 2):
            pred_pairs.add((a, b))

    # 3. Load decisions
    decisions = {}
    if os.path.exists(decisions_path):
        with open(decisions_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                a, b = r["row_a"], r["row_b"]
                pair_key = (a, b) if a < b else (b, a)
                decisions[pair_key] = r

    # 4. Load raw records
    df = load_rows(data_dir)
    prep = prepare(df)
    records = {r["row_id"]: r for r in prep.to_dict("records")}

    false_merges = sorted(list(pred_pairs - true_pairs))
    missed_matches = sorted(list(true_pairs - pred_pairs))

    # Tally cause counts
    cause_counts = defaultdict(int)

    def format_row_block(r: Dict[str, Any]) -> str:
        return (
            f"**{r['row_id']} ({r.get('supplier')})**: `{r.get('name')}` | "
            f"Addr: `{r.get('address')}` | City: `{r.get('city')}` | Pin: `{r.get('pincode')}` | "
            f"GPS: `{r.get('gps')}` | Phone: `{r.get('phone')}` | Stars: `{r.get('stars')}`"
        )

    lines = [
        "# Error Analysis Report\n",
        f"**Dataset**: `{data_dir}`  ",
        f"**Total Predictions**: `{len(pred_pairs)}` pairs  ",
        f"**Total True Pairs**: `{len(true_pairs)}` pairs  ",
        f"**False Merges**: `{len(false_merges)}`  ",
        f"**Missed Matches**: `{len(missed_matches)}`\n",
    ]

    # Process false merges
    fm_blocks = []
    for a, b in false_merges:
        ra, rb = records[a], records[b]
        dec = decisions.get((a, b), {})
        tgroup = row_trap.get(a) or row_trap.get(b) or ""
        cause = classify_cause(ra, rb, dec, is_false_merge=True)
        cause_counts[f"false_merge: {cause}"] += 1

        fm_blocks.append(
            f"### False Merge: `{a}` + `{b}` (Cause: {cause})\n"
            f"- **Ground Truth**: Master A = `{truth_master.get(a)}`, Master B = `{truth_master.get(b)}`\n"
            f"- **Trap Type**: `{tgroup if tgroup else 'None'}`\n"
            f"- **Pair Decision**: Score = `{dec.get('score', 'N/A')}`, Band = `{dec.get('band', 'N/A')}`, LLM same = `{dec.get('llm_same', 'N/A')}`, Confidence = `{dec.get('llm_confidence', 'N/A')}`\n"
            f"- **LLM Reason**: {dec.get('llm_reason', 'N/A')}\n"
            f"- **Explanation**: {dec.get('explanation', 'N/A')}\n\n"
            f"| Side | Row Details |\n"
            f"|---|---|\n"
            f"| **Row A** | {format_row_block(ra)} |\n"
            f"| **Row B** | {format_row_block(rb)} |\n"
        )

    # Process missed matches
    mm_blocks = []
    for a, b in missed_matches:
        ra, rb = records[a], records[b]
        dec = decisions.get((a, b), {})
        tgroup = row_trap.get(a) or row_trap.get(b) or ""
        cause = classify_cause(ra, rb, dec, is_false_merge=False)
        cause_counts[f"missed_match: {cause}"] += 1

        mm_blocks.append(
            f"### Missed Match: `{a}` + `{b}` (Cause: {cause})\n"
            f"- **Ground Truth**: Master = `{truth_master.get(a)}` (Difficulty: `{difficulty.get(a)}` / `{difficulty.get(b)}`)\n"
            f"- **Trap Type**: `{tgroup if tgroup else 'None'}`\n"
            f"- **Pair Decision**: Score = `{dec.get('score', 'N/A')}`, Band = `{dec.get('band', 'N/A')}`, LLM same = `{dec.get('llm_same', 'N/A')}`, Confidence = `{dec.get('llm_confidence', 'N/A')}`\n"
            f"- **LLM Reason**: {dec.get('llm_reason', 'N/A')}\n"
            f"- **Explanation**: {dec.get('explanation', 'N/A')}\n\n"
            f"| Side | Row Details |\n"
            f"|---|---|\n"
            f"| **Row A** | {format_row_block(ra)} |\n"
            f"| **Row B** | {format_row_block(rb)} |\n"
        )

    lines.append("## Error Counts by Cause\n")
    lines.append("| Category | Cause | Count |")
    lines.append("|---|---|---|")
    for k, cnt in sorted(cause_counts.items()):
        cat, cse = k.split(": ")
        lines.append(f"| {cat} | {cse} | {cnt} |")
    lines.append("\n---\n")

    lines.append(f"## False Merges ({len(false_merges)})\n")
    lines.extend(fm_blocks if fm_blocks else ["*No false merges.*\n"])

    lines.append(f"## Missed Matches ({len(missed_matches)})\n")
    lines.extend(mm_blocks if mm_blocks else ["*No missed matches.*\n"])

    os.makedirs(os.path.dirname(output_md), exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Error report generated at {output_md}")
    print(f"False merges: {len(false_merges)}, Missed matches: {len(missed_matches)}")
    print("\nCause Counts:")
    for k, cnt in sorted(cause_counts.items()):
        print(f"  {k}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="StayMerge Analysis CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    recall_parser = subparsers.add_parser("candidate-recall", help="Calculate candidate pair recall")
    recall_parser.add_argument("data_dir", nargs="?", default="data/dev", help="Path to data directory")

    band_parser = subparsers.add_parser("band-recall", help="Calculate band recall for true and different pairs")
    band_parser.add_argument("data_dir", nargs="?", default="data/dev", help="Path to data directory")

    err_parser = subparsers.add_parser("errors", help="Export errors.md analysis")
    err_parser.add_argument("data_dir", nargs="?", default="data/dev", help="Path to data directory")
    err_parser.add_argument("--pred", default="outputs/predictions.csv", help="Predictions CSV")
    err_parser.add_argument("--decisions", default="outputs/decisions.csv", help="Decisions CSV")
    err_parser.add_argument("--output", default="outputs/errors.md", help="Output markdown file")

    args = parser.parse_args()
    if args.command == "candidate-recall":
        candidate_recall(args.data_dir)
    elif args.command == "band-recall":
        band_recall(args.data_dir)
    elif args.command == "errors":
        export_errors(args.data_dir, args.pred, args.decisions, args.output)


if __name__ == "__main__":
    main()
