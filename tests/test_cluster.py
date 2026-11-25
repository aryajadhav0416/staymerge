"""Unit tests for constrained clustering in src/cluster.py."""
import pytest
from src.cluster import ConstrainedUnionFind, cluster_records


def test_constrained_union_find_supplier_a_conflict():
    """Test that two rows from supplier A are never merged into the same cluster."""
    supplier_map = {"A-01": "A", "A-02": "A", "B-01": "B"}
    elements = ["A-01", "A-02", "B-01"]
    cuf = ConstrainedUnionFind(elements, supplier_map)

    # Merge A-01 and B-01 (allowed)
    assert cuf.union("A-01", "B-01") is True
    # Merge B-01 and A-02 (would put A-01 and A-02 in same cluster -> rejected)
    assert cuf.union("B-01", "A-02") is False

    assert cuf.find("A-01") == cuf.find("B-01")
    assert cuf.find("A-01") != cuf.find("A-02")


def test_constrained_union_find_supplier_c_conflict():
    """Test that two rows from supplier C are never merged into the same cluster."""
    supplier_map = {"C-01": "C", "C-02": "C", "B-01": "B"}
    elements = ["C-01", "C-02", "B-01"]
    cuf = ConstrainedUnionFind(elements, supplier_map)

    assert cuf.union("C-01", "B-01") is True
    assert cuf.union("B-01", "C-02") is False

    assert cuf.find("C-01") != cuf.find("C-02")


def test_constrained_union_find_supplier_b_duplicate_allowed():
    """Test that supplier B rows CAN be merged together."""
    supplier_map = {"B-01": "B", "B-02": "B", "A-01": "A"}
    elements = ["B-01", "B-02", "A-01"]
    cuf = ConstrainedUnionFind(elements, supplier_map)

    # B-01 and B-02 merged
    assert cuf.union("B-01", "B-02") is True
    # Then merged with A-01
    assert cuf.union("B-01", "A-01") is True

    assert cuf.find("B-01") == cuf.find("B-02") == cuf.find("A-01")


def test_cluster_records_output_mapping():
    """Test cluster_records generates formatted cluster IDs for all input rows."""
    supplier_map = {"A-01": "A", "B-01": "B", "C-01": "C", "A-02": "A"}
    row_ids = ["A-01", "B-01", "C-01", "A-02"]
    edges = [("A-01", "B-01"), ("B-01", "C-01")]

    clusters = cluster_records(row_ids, supplier_map, edges)
    assert len(clusters) == 4
    # A-01, B-01, C-01 share one cluster
    assert clusters["A-01"] == clusters["B-01"] == clusters["C-01"]
    # A-02 is in its own singleton cluster
    assert clusters["A-02"] != clusters["A-01"]

