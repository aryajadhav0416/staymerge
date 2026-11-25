"""Unit tests for candidate pair generation."""
import pandas as pd
import pytest

from src.candidates import make_candidates


def test_make_candidates_rules():
    """Test candidate pairing rules: same city, cross-supplier, B-B allowed, A-A and C-C forbidden."""
    data = [
        {"row_id": "A-01", "supplier": "A", "norm_city": "Mumbai"},
        {"row_id": "A-02", "supplier": "A", "norm_city": "Mumbai"},
        {"row_id": "B-01", "supplier": "B", "norm_city": "Mumbai"},
        {"row_id": "B-02", "supplier": "B", "norm_city": "Mumbai"},
        {"row_id": "C-01", "supplier": "C", "norm_city": "Mumbai"},
        {"row_id": "C-02", "supplier": "C", "norm_city": "Mumbai"},
        {"row_id": "A-03", "supplier": "A", "norm_city": "Delhi"},
    ]
    df = pd.DataFrame(data)
    candidates = make_candidates(df)

    pairs = set(zip(candidates["row_id_a"], candidates["row_id_b"]))

    # Same city only: no pairs across Mumbai and Delhi
    for a, b in pairs:
        assert not (a == "A-03" or b == "A-03")

    # A-A forbidden
    assert ("A-01", "A-02") not in pairs

    # C-C forbidden
    assert ("C-01", "C-02") not in pairs

    # B-B allowed
    assert ("B-01", "B-02") in pairs

    # Cross supplier allowed
    assert ("A-01", "B-01") in pairs
    assert ("A-01", "C-01") in pairs
    assert ("B-01", "C-01") in pairs


def test_make_candidates_empty():
    """Test candidate generation on empty dataframe."""
    df = pd.DataFrame(columns=["row_id", "supplier", "norm_city"])
    candidates = make_candidates(df)
    assert candidates.empty
    assert list(candidates.columns) == ["row_id_a", "row_id_b"]


def test_make_candidates_order():
    """Test candidate pair IDs are always ordered canonically (id_a < id_b)."""
    data = [
        {"row_id": "B-02", "supplier": "B", "norm_city": "Kolkata"},
        {"row_id": "A-01", "supplier": "A", "norm_city": "Kolkata"},
    ]
    df = pd.DataFrame(data)
    candidates = make_candidates(df)
    assert len(candidates) == 1
    assert candidates.iloc[0]["row_id_a"] == "A-01"
    assert candidates.iloc[0]["row_id_b"] == "B-02"

