"""Candidate pair generation for hotel matching."""
import logging
import sys
from typing import Any, Dict, List, Tuple
import pandas as pd
from src.normalize import load_rows, prepare

logger = logging.getLogger(__name__)


def make_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Generate candidate pairs (row_id_a, row_id_b) under matching rules.

    Rules:
    - Same canonical city only.
    - Pairs from different suppliers, plus pairs inside supplier B.
    - Never pair two rows of supplier A or two rows of supplier C.
    """
    if "norm_city" not in df.columns:
        df = prepare(df)

    n_total_rows = len(df)
    total_possible_pairs = (n_total_rows * (n_total_rows - 1)) // 2

    # Group records by canonical city
    records_by_city: Dict[str, List[Dict[str, Any]]] = {}
    for r in df.to_dict("records"):
        city = r.get("norm_city")
        if not city:
            continue
        records_by_city.setdefault(city, []).append(r)

    candidate_pairs: List[Tuple[str, str]] = []

    for city, city_rows in records_by_city.items():
        n_city = len(city_rows)
        for i in range(n_city):
            row_i = city_rows[i]
            sup_i = row_i.get("supplier")
            id_i = row_i["row_id"]

            for j in range(i + 1, n_city):
                row_j = city_rows[j]
                sup_j = row_j.get("supplier")
                id_j = row_j["row_id"]

                # Disallow A-A and C-C pairs
                if sup_i == "A" and sup_j == "A":
                    continue
                if sup_i == "C" and sup_j == "C":
                    continue

                # Ensure canonical pair ordering (id_a < id_b)
                if id_i < id_j:
                    candidate_pairs.append((id_i, id_j))
                else:
                    candidate_pairs.append((id_j, id_i))

    cand_df = pd.DataFrame(candidate_pairs, columns=["row_id_a", "row_id_b"])

    logger.info(
        "Generated %d candidate pairs out of %d possible pairs (%.2f%%)",
        len(cand_df),
        total_possible_pairs,
        (len(cand_df) / total_possible_pairs * 100.0) if total_possible_pairs > 0 else 0.0,
    )

    return cand_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "data/dev"
    rows = load_rows(target_dir)
    prep = prepare(rows)
    candidates = make_candidates(prep)
    n_rows = len(prep)
    total_possible = (n_rows * (n_rows - 1)) // 2
    pct = (len(candidates) / total_possible * 100.0) if total_possible > 0 else 0.0
    print(f"Total rows: {n_rows}")
    print(f"Total possible pairs: {total_possible}")
    print(f"Candidate pairs: {len(candidates)} ({pct:.2f}%)")
