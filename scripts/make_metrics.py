#!/usr/bin/env python3
"""
Write outputs/metrics.json with StayMerge and baseline metrics for dev and test.

Run from the project root, after the data/test pipeline run has written
outputs/predictions.csv:   python scripts/make_metrics.py

It calls evaluate.py and baseline.py and parses their printed tables. It never
opens answer_key.csv, masters.csv or trap_pairs.csv itself.
"""
import json
import os
import re
import subprocess
import sys

KEYS = ("precision", "recall", "f1", "hard_row_recall", "trap_false_merges",
        "total_trap_pairs", "predicted_hotels", "true_hotels", "rows_scored")

# Copied from the printed summary of the data/test hybrid run. Update these
# numbers if you ever re-run the pipeline on data/test.
LLM = {
    "candidate_pairs": 19511,
    "llm_pairs_routed": 620,
    "llm_api_calls": 172,
    "llm_cache_hits": 448,
    "runtime_seconds": 618.81,
}


def run_evaluate(pred_path: str, data_dir: str) -> dict:
    """Run evaluate.py and parse its stdout into a metrics dict."""
    proc = subprocess.run(
        [sys.executable, "evaluate.py", "--pred", pred_path, "--data", data_dir],
        capture_output=True, text=True, check=True,
    )
    out = proc.stdout

    def extract(pattern: str, cast=float, default=0):
        m = re.search(pattern, out)
        return cast(m.group(1)) if m else default

    return {
        "precision": extract(r"precision\s+([0-9.]+)", float),
        "recall": extract(r"recall\s+([0-9.]+)", float),
        "f1": extract(r"f1\s+([0-9.]+)", float),
        "hard_row_recall": extract(r"hard-row recall\s+([0-9.]+)", float),
        "trap_false_merges": extract(r"trap false merges\s+([0-9]+)", int),
        "total_trap_pairs": extract(r"trap pairs total\s+([0-9]+)", int),
        "predicted_hotels": extract(r"predicted hotels\s+([0-9]+)", int),
        "true_hotels": extract(r"true hotels\s+([0-9]+)", int),
        "rows_scored": extract(r"rows scored\s+([0-9]+)", int),
        "rows_missing": extract(r"rows missing from predictions\s+([0-9]+)", int),
    }


def run_baseline(data_dir: str) -> dict:
    """Run baseline.py and parse its stdout table into a dict."""
    proc = subprocess.run(
        [sys.executable, "baseline.py", "--data", data_dir],
        capture_output=True, text=True, check=True,
    )
    baselines = {}
    pattern = (r"^(exact name \+ city|phone only|fuzzy name \+ GPS)"
               r"\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9]+)/([0-9]+)")
    for line in proc.stdout.splitlines():
        m = re.match(pattern, line.strip())
        if m:
            baselines[m.group(1)] = {
                "precision": float(m.group(2)),
                "recall": float(m.group(3)),
                "f1": float(m.group(4)),
                "hard_row_recall": float(m.group(5)),
                "trap_false_merges": int(m.group(6)),
                "total_trap_pairs": int(m.group(7)),
            }
    if len(baselines) != 3:
        sys.exit(f"Could not parse all three baselines for {data_dir}. Run baseline.py by hand and check its table.")
    return baselines


def previous_dev(existing: dict):
    """Find the dev StayMerge numbers, however deeply an earlier run nested them."""
    d = existing.get("dev")
    if isinstance(d, dict) and "staymerge" in d:
        s = d["staymerge"]
        while isinstance(s, dict) and "staymerge" in s:
            s = s["staymerge"]
        return {k: s[k] for k in KEYS if k in s}
    if existing.get("rows_scored") == 298:  # the old flat dev-only file
        return {k: existing[k] for k in KEYS if k in existing}
    return None


def main():
    os.makedirs("outputs", exist_ok=True)
    existing = {}
    if os.path.exists("outputs/metrics.json"):
        with open("outputs/metrics.json", "r", encoding="utf-8") as f:
            existing = json.load(f)

    test_staymerge = run_evaluate("outputs/predictions.csv", "data/test")
    if test_staymerge.pop("rows_missing") > 0:
        sys.exit("outputs/predictions.csv is not the data/test run. "
                 "Run the pipeline on data/test first.")
    test_baselines = run_baseline("data/test")
    dev_baselines = run_baseline("data/dev")

    dev_staymerge = previous_dev(existing)
    if not dev_staymerge:
        sys.exit("Could not find the dev numbers in outputs/metrics.json. "
                 "Restore the file from outputs/backup_dev and run again.")

    payload = {
        **test_staymerge,            # top-level keys stay the test numbers
        "baselines": test_baselines,
        "llm": LLM,
        "dev": {"staymerge": dev_staymerge, "baselines": dev_baselines},
        "test": {"staymerge": test_staymerge, "baselines": test_baselines, "llm": LLM},
    }
    with open("outputs/metrics.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Updated outputs/metrics.json with dev and test metrics.")
    print(f"test F1 {test_staymerge['f1']}, dev F1 {dev_staymerge['f1']}, "
          f"baselines: {', '.join(k + ' ' + str(v['f1']) for k, v in test_baselines.items())}")


if __name__ == "__main__":
    main()