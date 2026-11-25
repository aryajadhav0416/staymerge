"""End-to-end hotel deduplication and catalogue merging pipeline."""
import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src import llm_judge
from src.candidates import make_candidates
from src.cluster import cluster_records
from src.config import RULES_ONLY_MATCH_THRESHOLD
from src.normalize import load_rows, prepare
from src.rules import band, explain, pair_features, score_pair


def run_pipeline(
    data_dir: str = "data/test",
    mode: str = "hybrid",
    max_llm_calls: Optional[int] = None,
    pred_path: str = "outputs/predictions.csv",
    decisions_path: str = "outputs/decisions.csv",
) -> Dict[str, Any]:
    """Execute end-to-end matching, scoring, LLM judging, and constrained clustering."""
    start_time = time.time()

    # 1. Load and normalize
    raw_df = load_rows(data_dir)
    prep_df = prepare(raw_df)

    # 2. Candidate generation
    cand_df = make_candidates(prep_df)

    records_by_id = {r["row_id"]: r for r in prep_df.to_dict("records")}
    all_row_ids = sorted(list(records_by_id.keys()))
    supplier_map = {r["row_id"]: r.get("supplier", "") for r in records_by_id.values()}

    band_counts = defaultdict(int)
    rule_edges: List[Tuple[float, Tuple[str, str]]] = []
    llm_edges: List[Tuple[float, Tuple[str, str]]] = []
    decisions_log: List[Dict[str, Any]] = []

    llm_calls_at_start = llm_judge.API_CALL_COUNT
    llm_invocations = 0
    cache_hits = 0

    # 3. Process candidate pairs
    for _, row in cand_df.iterrows():
        id_a, id_b = row["row_id_a"], row["row_id_b"]
        rec_a, rec_b = records_by_id[id_a], records_by_id[id_b]

        feats = pair_features(rec_a, rec_b)
        sc = score_pair(feats)
        pair_band = band(sc)
        expl = explain(feats)
        band_counts[pair_band] += 1

        llm_same: Optional[bool] = None
        llm_confidence: Optional[float] = None
        llm_reason: str = ""
        final_decision: bool = False

        if pair_band == "match":
            final_decision = True
            rule_edges.append((sc, (id_a, id_b)))
        elif pair_band == "no_match":
            final_decision = False
        elif pair_band == "unsure":
            if mode == "rules-only":
                # Rules-only fallback for unsure
                final_decision = sc >= RULES_ONLY_MATCH_THRESHOLD
                if final_decision:
                    rule_edges.append((sc, (id_a, id_b)))
            else:  # hybrid mode
                # Check LLM call limits
                if max_llm_calls is not None and llm_invocations >= max_llm_calls:
                    # Treat as fallback
                    final_decision = sc >= RULES_ONLY_MATCH_THRESHOLD
                    llm_reason = "max_llm_calls_reached"
                    if final_decision:
                        rule_edges.append((sc, (id_a, id_b)))
                else:
                    pair_hash = llm_judge.compute_pair_hash(rec_a, rec_b)
                    cached_val = llm_judge.get_cached_decision(pair_hash)

                    calls_before = llm_judge.API_CALL_COUNT
                    same, conf, reason = llm_judge.judge_pair(rec_a, rec_b)
                    calls_made = llm_judge.API_CALL_COUNT - calls_before

                    llm_invocations += 1
                    if cached_val is not None and calls_made == 0:
                        cache_hits += 1

                    llm_same = same
                    llm_confidence = conf
                    llm_reason = reason

                    if same is True:
                        final_decision = True
                        llm_edges.append((sc, (id_a, id_b)))
                    elif same is False:
                        final_decision = False
                    else:  # same is None (LLM error fallback)
                        final_decision = sc >= RULES_ONLY_MATCH_THRESHOLD
                        if final_decision:
                            rule_edges.append((sc, (id_a, id_b)))

        decisions_log.append(
            {
                "row_a": id_a,
                "row_b": id_b,
                "score": f"{sc:.2f}",
                "band": pair_band,
                "llm_same": "" if llm_same is None else str(llm_same),
                "llm_confidence": "" if llm_confidence is None else f"{llm_confidence:.2f}",
                "llm_reason": llm_reason,
                "final_decision": "true" if final_decision else "false",
                "explanation": expl,
            }
        )

    # 4. Constrained clustering: sort edges descending by rule score, rule-matched edges first
    rule_edges.sort(key=lambda x: x[0], reverse=True)
    llm_edges.sort(key=lambda x: x[0], reverse=True)
    ordered_edges = [edge for _, edge in rule_edges] + [edge for _, edge in llm_edges]

    clusters = cluster_records(all_row_ids, supplier_map, ordered_edges)

    # 5. Output predictions and decisions
    os.makedirs(os.path.dirname(pred_path), exist_ok=True)
    with open(pred_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row_id", "cluster_id"])
        for rid in sorted(all_row_ids):
            writer.writerow([rid, clusters[rid]])

    os.makedirs(os.path.dirname(decisions_path), exist_ok=True)
    with open(decisions_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "row_a",
            "row_b",
            "score",
            "band",
            "llm_same",
            "llm_confidence",
            "llm_reason",
            "final_decision",
            "explanation",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(decisions_log)

    runtime_s = time.time() - start_time
    total_api_calls = llm_judge.API_CALL_COUNT - llm_calls_at_start

    print(f"\n================ Pipeline Summary ({mode.upper()}) ================")
    print(f"Data directory:       {data_dir}")
    print(f"Candidate pairs:      {len(cand_df)}")
    print(f"Band 'match':         {band_counts['match']}")
    print(f"Band 'unsure':        {band_counts['unsure']}")
    print(f"Band 'no_match':      {band_counts['no_match']}")
    print(f"LLM pairs routed:     {llm_invocations}")
    print(f"LLM API calls made:   {total_api_calls}")
    print(f"LLM Cache hits:       {cache_hits}")
    print(f"Final clusters:       {len(set(clusters.values()))}")
    print(f"Runtime:              {runtime_s:.2f} s")
    print(f"Predictions saved:    {pred_path}")
    print(f"Decisions saved:      {decisions_path}")
    print("===============================================================\n")

    return {
        "candidate_pairs": len(cand_df),
        "bands": dict(band_counts),
        "llm_calls": total_api_calls,
        "cache_hits": cache_hits,
        "runtime_s": runtime_s,
        "clusters": len(set(clusters.values())),
    }


def main():
    parser = argparse.ArgumentParser(description="Hotel Matching & Catalogue Pipeline")
    parser.add_argument("--data", default="data/test", help="Path to data directory changed to data/test")
    parser.add_argument(
        "--mode",
        choices=["rules-only", "hybrid"],
        default="hybrid",
        help="Matching mode: rules-only or hybrid (with Groq LLM)",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Maximum number of LLM calls to execute before falling back to rules",
    )
    parser.add_argument("--pred", default="outputs/predictions.csv", help="Output path for predictions.csv")
    parser.add_argument("--decisions", default="outputs/decisions.csv", help="Output path for decisions.csv")

    args = parser.parse_args()
    run_pipeline(
        data_dir=args.data,
        mode=args.mode,
        max_llm_calls=args.max_llm_calls,
        pred_path=args.pred,
        decisions_path=args.decisions,
    )


if __name__ == "__main__":
    main()
