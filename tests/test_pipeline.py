"""Unit tests for the end-to-end hotel deduplication and catalogue merging pipeline."""
import csv
import os
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.pipeline import run_pipeline


@pytest.fixture
def tiny_synthetic_data(tmp_path):
    """Create a tiny synthetic data directory with 3 suppliers."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Supplier A
    supp_a = pd.DataFrame(
        [
            {
                "row_id": "A-0001",
                "supplier": "A",
                "supplier_hotel_id": "SUPA1",
                "name": "Taj Lands End, Mumbai",
                "address": "BJ Road, Bandra West",
                "city": "Mumbai",
                "pincode": "400050",
                "lat": 19.0435,
                "lon": 72.8194,
                "phone": "+91-22-66681234",
                "stars": 5,
                "price_inr": 15000,
                "cancellation_policy": "Free",
                "payment_terms": "Pay now",
            },
            {
                "row_id": "A-0002",
                "supplier": "A",
                "supplier_hotel_id": "SUPA2",
                "name": "Trident Hotel Nariman Point",
                "address": "CR 2, Nariman Point",
                "city": "Mumbai",
                "pincode": "400021",
                "lat": 18.9272,
                "lon": 72.8205,
                "phone": "+91-22-66324343",
                "stars": 5,
                "price_inr": 12000,
                "cancellation_policy": "Free",
                "payment_terms": "Pay at hotel",
            },
        ]
    )
    supp_a.to_csv(data_dir / "supplier_a.csv", index=False)

    # Supplier B
    supp_b = pd.DataFrame(
        [
            {
                "row_id": "B-0001",
                "supplier": "B",
                "supplier_hotel_id": "SUPB1",
                "name": "The Taj Lands End Hotel",
                "address": "BJ Road, Bandra (W)",
                "city": "Mumbai",
                "pincode": "400050",
                "lat": 19.0438,
                "lon": 72.8196,
                "phone": "+91-22-66681234",
                "stars": 5,
                "price_inr": 14500,
                "cancellation_policy": "Free",
                "payment_terms": "Pay now",
            }
        ]
    )
    supp_b.to_csv(data_dir / "supplier_b.csv", index=False)

    # Supplier C
    supp_c = pd.DataFrame(
        [
            {
                "row_id": "C-0001",
                "supplier": "C",
                "supplier_hotel_id": "SUPC1",
                "name": "Trident Nariman Point Mumbai",
                "address": "Nariman Point",
                "city": "Mumbai",
                "pincode": "400021",
                "lat": 18.9275,
                "lon": 72.8208,
                "phone": "+91-22-66324343",
                "stars": 5,
                "price_inr": 12500,
                "cancellation_policy": "Non-refundable",
                "payment_terms": "Pay now",
            }
        ]
    )
    supp_c.to_csv(data_dir / "supplier_c.csv", index=False)

    return str(data_dir)


def test_pipeline_rules_only(tiny_synthetic_data, tmp_path):
    """Test rules-only pipeline run creates predictions.csv and clusters identically named hotels."""
    pred_path = str(tmp_path / "predictions.csv")
    decisions_path = str(tmp_path / "decisions.csv")

    summary = run_pipeline(
        data_dir=tiny_synthetic_data,
        mode="rules-only",
        pred_path=pred_path,
        decisions_path=decisions_path,
    )

    assert os.path.exists(pred_path)
    assert os.path.exists(decisions_path)

    # Read predictions
    preds = {}
    with open(pred_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            preds[r["row_id"]] = r["cluster_id"]

    assert len(preds) == 4
    # A-0001 and B-0001 (Taj Lands End) should be clustered together
    assert preds["A-0001"] == preds["B-0001"]
    # A-0002 and C-0001 (Trident Nariman Point) should be clustered together
    assert preds["A-0002"] == preds["C-0001"]
    # Taj and Trident should be in different clusters
    assert preds["A-0001"] != preds["A-0002"]


def test_pipeline_hybrid_with_mock_judge(tiny_synthetic_data, tmp_path):
    """Test hybrid pipeline run with mocked judge_pair."""
    pred_path = str(tmp_path / "predictions.csv")
    decisions_path = str(tmp_path / "decisions.csv")

    # Mock judge_pair to return same=True for any unsure pairs
    with patch("src.pipeline.llm_judge.judge_pair") as mock_judge:
        mock_judge.return_value = (True, 0.95, "Mocked match")

        summary = run_pipeline(
            data_dir=tiny_synthetic_data,
            mode="hybrid",
            pred_path=pred_path,
            decisions_path=decisions_path,
        )

        assert os.path.exists(pred_path)
        assert os.path.exists(decisions_path)

        with open(pred_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            preds = {r["row_id"]: r["cluster_id"] for r in reader}

        assert len(preds) == 4
        assert preds["A-0001"] == preds["B-0001"]
        assert preds["A-0002"] == preds["C-0001"]

