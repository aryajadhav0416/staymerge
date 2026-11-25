"""Tests for the StayMerge FastAPI backend."""
import json
import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from api.main import (
    CATALOGUE_PATH,
    DECISIONS_PATH,
    METRICS_PATH,
    app,
)

client = TestClient(app)


def test_health():
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_hotels():
    """Test /hotels endpoint returns list of hotels."""
    response = client.get("/hotels")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "cluster_id" in first
    assert "name" in first
    assert "offers" in first
    assert "best_offer" in first


def test_get_hotels_filter():
    """Test /hotels with city and search query filter."""
    response = client.get("/hotels?city=Pune")
    assert response.status_code == 200
    data = response.json()
    for h in data:
        assert h["city"].lower() == "pune"


def test_get_hotel_detail_success():
    """Test /hotels/{id} returns hotel details and similar_hotels."""
    response = client.get("/hotels/C0001")
    assert response.status_code == 200
    data = response.json()
    assert data["cluster_id"] == "C0001"
    assert "similar_hotels" in data
    assert isinstance(data["similar_hotels"], list)


def test_get_hotel_detail_not_found():
    """Test /hotels/{id} returns 404 for unknown hotel."""
    response = client.get("/hotels/UNKNOWN_HOTEL_ID_9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_decisions():
    """Test /decisions returns candidate pairs with scoring explanations."""
    response = client.get("/decisions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "row_a" in first
    assert "row_b" in first
    assert "score" in first
    assert "final_decision" in first
    assert "explanation" in first


def test_get_metrics():
    """Test /metrics returns matcher accuracy metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "f1" in data
    assert "precision" in data
    assert "recall" in data
    assert "trap_false_merges" in data


def test_get_feeds():
    """Test /feeds returns raw supplier stats."""
    response = client.get("/feeds")
    assert response.status_code == 200
    data = response.json()
    assert "suppliers" in data
    assert len(data["suppliers"]) == 3
    sups = {s["supplier"]: s for s in data["suppliers"]}
    assert "A" in sups
    assert "B" in sups
    assert "C" in sups
    assert sups["A"]["row_count"] == 111


def test_submit_review_decision_success():
    """Test POST /reviews successfully records a human review decision."""
    payload = {
        "row_a": "A-0001",
        "row_b": "B-0004",
        "action": "split",
        "notes": "Verified different addresses",
    }
    response = client.post("/reviews", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["recorded"]["action"] == "split"


def test_submit_review_decision_bad_action():
    """Test POST /reviews returns 422 for bad review decision."""
    payload = {
        "row_a": "A-0001",
        "row_b": "B-0004",
        "action": "invalid_action",
    }
    response = client.post("/reviews", json=payload)
    assert response.status_code == 422
    assert "invalid action" in response.json()["detail"].lower()


def test_missing_catalogue_returns_503(tmp_path):
    """Test 503 error with friendly message when an outputs file is missing."""
    with patch("api.main.CATALOGUE_PATH", str(tmp_path / "nonexistent.json")):
        response = client.get("/hotels")
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "not available yet" in detail.lower()


def test_use_mock_mode():
    """Test USE_MOCK=1 serves mock example data."""
    with patch.dict(os.environ, {"USE_MOCK": "1"}):
        response = client.get("/hotels")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["cluster_id"] == "C0001"

        response_metrics = client.get("/metrics")
        assert response_metrics.status_code == 200
        assert response_metrics.json()["f1"] == 0.969

