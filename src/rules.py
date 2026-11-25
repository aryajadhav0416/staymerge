"""Rule-based feature extraction and scoring for hotel record pairs."""
import math
from typing import Any, Dict, Optional, Tuple
import rapidfuzz.fuzz as fuzz

from src.config import (
    BAND_HIGH_THRESHOLD,
    BAND_LOW_THRESHOLD,
    EARTH_RADIUS_M,
    GPS_FAR_SCORE,
    GPS_MID_450_SCORE,
    GPS_MID_METERS,
    GPS_NEAR_200_SCORE,
    GPS_NEAR_METERS,
    PHONE_MATCH_SCORE,
    PHONE_MISMATCH_SCORE,
    PINCODE_MATCH_SCORE,
    PINCODE_MISMATCH_SCORE,
    PLOT_MATCH_SCORE,
    PLOT_MISMATCH_SCORE,
    STARS_MATCH_SCORE,
    STARS_MISMATCH_SCORE,
    WEIGHT_NAME_SIM,
)


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate the great circle distance between two points in meters."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    r = EARTH_RADIUS_M

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def pair_features(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compute pairwise similarity signals and categorical states between two hotel records."""
    name_a = a.get("norm_name") or ""
    name_b = b.get("norm_name") or ""

    ratio_standard = fuzz.ratio(name_a, name_b) / 100.0
    ratio_token_sort = fuzz.token_sort_ratio(name_a, name_b) / 100.0
    name_sim = max(ratio_standard, ratio_token_sort)

    # Phone state: ignore if either is central 1800
    phone_a = a.get("phone_last8") or ""
    phone_b = b.get("phone_last8") or ""
    central_a = bool(a.get("phone_is_central", False))
    central_b = bool(b.get("phone_is_central", False))

    if central_a or central_b or not phone_a or not phone_b:
        phone_state = "unknown"
    elif phone_a == phone_b:
        phone_state = "match"
    else:
        phone_state = "mismatch"

    # Pincode state
    pin_a = str(a.get("pincode") or "").strip()
    pin_b = str(b.get("pincode") or "").strip()
    if not pin_a or not pin_b or pin_a.lower() in ("nan", "none") or pin_b.lower() in ("nan", "none"):
        pincode_state = "unknown"
    elif pin_a == pin_b:
        pincode_state = "match"
    else:
        pincode_state = "mismatch"

    # Plot state
    plot_a = a.get("plot_number")
    plot_b = b.get("plot_number")
    if not plot_a or not plot_b or str(plot_a).lower() in ("nan", "none") or str(plot_b).lower() in ("nan", "none"):
        plot_state = "unknown"
    elif str(plot_a).strip().lower() == str(plot_b).strip().lower():
        plot_state = "match"
    else:
        plot_state = "mismatch"

    # GPS distance
    gps_a = a.get("gps")
    gps_b = b.get("gps")
    if gps_a and gps_b and isinstance(gps_a, tuple) and isinstance(gps_b, tuple):
        gps_distance_m: Optional[float] = haversine_distance(gps_a, gps_b)
    else:
        gps_distance_m = None

    # Stars state
    stars_a = a.get("stars")
    stars_b = b.get("stars")
    if (
        stars_a is None
        or stars_b is None
        or str(stars_a).lower() in ("nan", "none", "")
        or str(stars_b).lower() in ("nan", "none", "")
    ):
        stars_state = "unknown"
    elif float(stars_a) == float(stars_b):
        stars_state = "match"
    else:
        stars_state = "mismatch"

    return {
        "name_sim": name_sim,
        "phone_state": phone_state,
        "pincode_state": pincode_state,
        "plot_state": plot_state,
        "gps_distance_m": gps_distance_m,
        "stars_state": stars_state,
    }


def score_pair(features: Dict[str, Any]) -> float:
    """Score pair features according to configured weights and adjustments."""
    total_score = WEIGHT_NAME_SIM * features["name_sim"]

    # Phone
    phone = features.get("phone_state")
    if phone == "match":
        total_score += PHONE_MATCH_SCORE
    elif phone == "mismatch":
        total_score += PHONE_MISMATCH_SCORE

    # Pincode
    pin = features.get("pincode_state")
    if pin == "match":
        total_score += PINCODE_MATCH_SCORE
    elif pin == "mismatch":
        total_score += PINCODE_MISMATCH_SCORE

    # Plot
    plot = features.get("plot_state")
    if plot == "match":
        total_score += PLOT_MATCH_SCORE
    elif plot == "mismatch":
        total_score += PLOT_MISMATCH_SCORE

    # GPS
    dist = features.get("gps_distance_m")
    if dist is not None:
        if dist < GPS_NEAR_METERS:
            total_score += GPS_NEAR_200_SCORE
        elif dist < GPS_MID_METERS:
            total_score += GPS_MID_450_SCORE
        else:
            total_score += GPS_FAR_SCORE

    # Stars
    stars = features.get("stars_state")
    if stars == "match":
        total_score += STARS_MATCH_SCORE
    elif stars == "mismatch":
        total_score += STARS_MISMATCH_SCORE

    return total_score


def band(score: float) -> str:
    """Classify total rule score into match, no_match, or unsure."""
    if score >= BAND_HIGH_THRESHOLD:
        return "match"
    if score <= BAND_LOW_THRESHOLD:
        return "no_match"
    return "unsure"


def explain(features: Dict[str, Any]) -> str:
    """Generate a concise, human-readable reason for pair signals."""
    parts = [f"name {features['name_sim']:.2f}"]

    # Phone explanation
    phone = features.get("phone_state")
    if phone == "match":
        parts.append("same phone")
    elif phone == "mismatch":
        parts.append("phone differs")

    # Pincode explanation
    pin = features.get("pincode_state")
    if pin == "match":
        parts.append("same pincode")
    elif pin == "mismatch":
        parts.append("pincode differs")

    # Plot explanation
    plot = features.get("plot_state")
    if plot == "match":
        parts.append("same plot")
    elif plot == "mismatch":
        parts.append("plot differs")

    # GPS explanation
    dist = features.get("gps_distance_m")
    if dist is not None:
        parts.append(f"{dist:.0f} m apart")

    # Stars explanation
    stars = features.get("stars_state")
    if stars == "match":
        parts.append("same stars")
    elif stars == "mismatch":
        parts.append("stars differ")

    return ", ".join(parts)
