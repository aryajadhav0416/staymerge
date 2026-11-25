"""Unit tests for offer selection and catalogue building in src/offers.py."""
import pandas as pd
import pytest

from src.offers import best_offer, build_catalogue, value_score


def test_dearer_free_cancellation_beats_cheapest_non_refundable():
    """Case 1: A slightly dearer free-cancellation offer beats the cheapest non-refundable one."""
    offer_cheap_non_refundable = {
        "row_id": "B-001",
        "supplier": "B",
        "price_inr": 4000.0,
        "cancellation_policy": "non-refundable",
        "payment_terms": "pay now",
        "reliability": 0.90,
    }
    offer_dearer_free_canc = {
        "row_id": "A-001",
        "supplier": "A",
        "price_inr": 4200.0,
        "cancellation_policy": "free cancellation till 48h",
        "payment_terms": "pay at hotel",
        "reliability": 0.95,
    }

    offers = [offer_cheap_non_refundable, offer_dearer_free_canc]

    score_cheap = value_score(offer_cheap_non_refundable, offers)
    score_dearer = value_score(offer_dearer_free_canc, offers)

    # Verify score of dearer offer is higher
    assert score_dearer > score_cheap

    top_offer, reason = best_offer(offers)
    assert top_offer["row_id"] == "A-001"
    assert "above the cheapest" in reason
    assert "free cancellation till 48h" in reason


def test_equal_price_and_terms_higher_reliability_wins():
    """Case 2: With equal price and terms, the more reliable supplier wins."""
    offer_sup_c = {
        "row_id": "C-001",
        "supplier": "C",
        "price_inr": 5000.0,
        "cancellation_policy": "free cancellation till 24h",
        "payment_terms": "pay at hotel",
        "reliability": 0.80,
    }
    offer_sup_a = {
        "row_id": "A-001",
        "supplier": "A",
        "price_inr": 5000.0,
        "cancellation_policy": "free cancellation till 24h",
        "payment_terms": "pay at hotel",
        "reliability": 0.95,
    }

    offers = [offer_sup_c, offer_sup_a]

    score_c = value_score(offer_sup_c, offers)
    score_a = value_score(offer_sup_a, offers)

    assert score_a > score_c

    top_offer, reason = best_offer(offers)
    assert top_offer["row_id"] == "A-001"
    assert "cheapest available" in reason
    assert "0.95" in reason


def test_single_offer_returned_as_best_with_valid_reason():
    """Case 3: A single offer is returned as the best with a valid reason."""
    single_offer = {
        "row_id": "A-005",
        "supplier": "A",
        "price_inr": 3500.0,
        "cancellation_policy": "free cancellation till 48h",
        "payment_terms": "pay later (deposit)",
        "reliability": 0.95,
    }
    offers = [single_offer]

    top_offer, reason = best_offer(offers)
    assert top_offer["row_id"] == "A-005"
    assert "Rs 3,500" in reason
    assert "only available offer" in reason
    assert "free cancellation till 48h" in reason
    assert "supplier reliability 0.95" in reason


def test_build_catalogue_aggregation():
    """Test build_catalogue produces accurate canonical fields and tie-breaking."""
    df = pd.DataFrame(
        [
            {
                "row_id": "A-001",
                "supplier": "A",
                "name": "The Grand Palace Hotel",
                "address": "12 MG Road",
                "pincode": "560001",
                "city": "Bengaluru",
                "lat": 12.9716,
                "lon": 77.5946,
                "stars": 5,
                "price_inr": 6000.0,
                "cancellation_policy": "free cancellation till 48h",
                "payment_terms": "pay at hotel",
            },
            {
                "row_id": "B-001",
                "supplier": "B",
                "name": "Grand Palace Hotel",  # Tie in frequency (1 vs 1), but shorter than A-001
                "address": "12 MG Road",
                "pincode": "560001",
                "city": "Bengaluru",
                "lat": 12.9720,
                "lon": 77.5950,
                "stars": 5,
                "price_inr": 5800.0,
                "cancellation_policy": "non-refundable",
                "payment_terms": "pay now",
            },
        ]
    )

    clusters = {"A-001": "C0001", "B-001": "C0001"}
    suppliers_df = pd.DataFrame([{"supplier": "A", "reliability": 0.95}, {"supplier": "B", "reliability": 0.88}])

    cat = build_catalogue(df, clusters, suppliers_df)
    assert len(cat) == 1
    hotel = cat[0]
    assert hotel["cluster_id"] == "C0001"
    # Longest clean name should win tie
    assert hotel["name"] == "The Grand Palace Hotel"
    assert hotel["city"] == "Bengaluru"
    assert len(hotel["offers"]) == 2
    assert pytest.approx(hotel["lat"], 0.0001) == 12.9718
    assert pytest.approx(hotel["lon"], 0.0001) == 77.5948

