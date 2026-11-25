"""Score candidate pairs using rule heuristics and run rules-only clustering."""
import csv
import logging
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

from src.candidates import make_candidates
from src.cluster import cluster_records
from src.config import BAND_HIGH_THRESHOLD, BAND_LOW_THRESHOLD, RULES_ONLY_MATCH_THRESHOLD
from src.normalize import load_rows, prepare
from src.rules import band, explain, pair_features, score_pair

logger = logging.getLogger(__name__)


def run_rules(data_dir: str = "data/test", output_path: str = "outputs/predictions.csv") -> None:
    """Score candidate pairs, count bands, and output rules-only cluster predictions."""
    df = load_rows(data_dir)
    prep = prepare(df)
    cand_df = make_candidates(prep)

    # Index rows by row_id
    records_by_id = {r["row_id"]: r for r in prep.to_dict("records")}
    all_row_ids = sorted(list(records_by_id.keys()))
    supplier_map = {r["row_id"]: r.get("supplier", "") for r in records_by_id.values()}

    band_counts = defaultdict(int)
    accepted_edges: List[Tuple[str, str]] = []

    matched_pairs_count = 0
    for _, row in cand_df.iterrows():
        id_a, id_b = row["row_id_a"], row["row_id_b"]
        rec_a, rec_b = records_by_id[id_a], records_by_id[id_b]

        features = pair_features(rec_a, rec_b)
        score = score_pair(features)
        pair_band = band(score)
        band_counts[pair_band] += 1

        if score >= RULES_ONLY_MATCH_THRESHOLD:
            accepted_edges.append((id_a, id_b))
            matched_pairs_count += 1

    row_to_cluster = cluster_records(all_row_ids, supplier_map, accepted_edges)

    # Format clusters
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row_id", "cluster_id"])
        for rid in sorted(all_row_ids):
            writer.writerow([rid, row_to_cluster[rid]])

    print(f"\n--- Rules Scoring Summary ({data_dir}) ---")
    print(f"Total candidate pairs scored: {len(cand_df)}")
    print(f"Band 'match'    (score >= {BAND_HIGH_THRESHOLD}): {band_counts['match']}")
    print(f"Band 'unsure'   ({BAND_LOW_THRESHOLD} < score < {BAND_HIGH_THRESHOLD}): {band_counts['unsure']}")
    print(f"Band 'no_match' (score <= {BAND_LOW_THRESHOLD}): {band_counts['no_match']}")
    print(f"Pairs merged (score >= {RULES_ONLY_MATCH_THRESHOLD}): {matched_pairs_count}")
    print(f"Total clusters generated: {len(set(row_to_cluster.values()))}")
    print(f"Predictions written to: {output_path}")


if __name__ == "__main__":
    target_data = sys.argv[1] if len(sys.argv) > 1 else "data/test"
    run_rules(target_data)

