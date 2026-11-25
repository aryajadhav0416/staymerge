"""Unit tests for rule-based feature extraction, scoring, bands, and explanations."""
import pytest
from src.rules import band, explain, haversine_distance, pair_features, score_pair


def test_haversine_distance_known_points():
    """Test haversine distance calculation between known coordinates."""
    # Approx distance between two Mumbai points ~ 1.1 km
    p1 = (19.0760, 72.8777)
    p2 = (19.0860, 72.8777)
    dist = haversine_distance(p1, p2)
    assert 1100 <= dist <= 1120


def test_pair_features_exact_match():
    """Test features for identical hotel records."""
    rec_a = {
        "norm_name": "taj mahal palace",
        "phone_last8": "22001122",
        "phone_is_central": False,
        "pincode": "400001",
        "plot_number": "12",
        "gps": (18.9217, 72.8332),
        "stars": 5,
    }
    rec_b = {
        "norm_name": "taj mahal palace",
        "phone_last8": "22001122",
        "phone_is_central": False,
        "pincode": "400001",
        "plot_number": "12",
        "gps": (18.9217, 72.8332),
        "stars": 5,
    }
    feats = pair_features(rec_a, rec_b)
    assert feats["name_sim"] == 1.0
    assert feats["phone_state"] == "match"
    assert feats["pincode_state"] == "match"
    assert feats["plot_state"] == "match"
    assert feats["stars_state"] == "match"
    assert feats["gps_distance_m"] == pytest.approx(0.0, abs=1.0)

    score = score_pair(feats)
    # 3.0*1.0 + 1.5 + 0.5 + 1.0 + 1.0 + 0.2 = 7.2
    assert pytest.approx(score, 0.01) == 7.2
    assert band(score) == "match"


def test_pair_features_central_phone_ignored():
    """Test 1800 central numbers are ignored and classified as unknown phone state."""
    rec_a = {
        "norm_name": "marriott",
        "phone_last8": "01112222",
        "phone_is_central": True,
        "pincode": "400001",
    }
    rec_b = {
        "norm_name": "marriott",
        "phone_last8": "01112222",
        "phone_is_central": True,
        "pincode": "400001",
    }
    feats = pair_features(rec_a, rec_b)
    assert feats["phone_state"] == "unknown"


def test_pair_features_token_sort():
    """Test token sort similarity picks highest ratio for rearranged words."""
    rec_a = {"norm_name": "grand hyatt hotel"}
    rec_b = {"norm_name": "hotel hyatt grand"}
    feats = pair_features(rec_a, rec_b)
    assert feats["name_sim"] == 1.0


def test_band_classification():
    """Test score thresholds for bands: match (>= 3.8), unsure, and no_match (<= 2.0)."""
    assert band(4.0) == "match"
    assert band(3.8) == "match"
    assert band(3.5) == "unsure"
    assert band(2.5) == "unsure"
    assert band(2.0) == "no_match"
    assert band(1.0) == "no_match"


def test_explain_string():
    """Test human-readable explain string generation."""
    feats = {
        "name_sim": 0.93,
        "phone_state": "unknown",
        "pincode_state": "match",
        "plot_state": "mismatch",
        "gps_distance_m": 380.0,
        "stars_state": "match",
    }
    exp = explain(feats)
    assert "name 0.93" in exp
    assert "same pincode" in exp
    assert "plot differs" in exp
    assert "380 m apart" in exp
    assert "same stars" in exp

