"""Offer selection and catalogue record building."""
from collections import Counter
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from src.config import (
    CANCELLATION_SCORES,
    OFFER_WEIGHT_CANCELLATION,
    OFFER_WEIGHT_PAYMENT_TERMS,
    OFFER_WEIGHT_PRICE,
    OFFER_WEIGHT_RELIABILITY,
    PAYMENT_TERMS_SCORES,
)
from src.normalize import load_rows, prepare

logger = logging.getLogger(__name__)


def value_score(offer: Dict[str, Any], all_offers: List[Dict[str, Any]]) -> float:
    """Calculate the value score of an offer based on configured weights.

    Weights:
    - price 0.45 (the lowest price scores 1, scaled down for higher prices: min_price / price)
    - cancellation 0.25 (free 48h = 1.0, free 24h = 0.8, partial refund = 0.5, non-refundable = 0.1)
    - payment terms 0.10 (pay at hotel = 1.0, pay later = 0.7, pay now = 0.4)
    - supplier reliability 0.20
    """
    if not all_offers:
        return 0.0

    valid_prices = [
        float(o["price_inr"])
        for o in all_offers
        if o.get("price_inr") is not None and str(o.get("price_inr")).lower() not in ("nan", "none", "")
    ]
    min_price = min(valid_prices) if valid_prices else 0.0

    # 1. Price score
    curr_price = float(offer.get("price_inr", 0.0) or 0.0)
    if curr_price > 0 and min_price > 0:
        price_score = min_price / curr_price
    else:
        price_score = 1.0 if curr_price == 0 else 0.0

    # 2. Cancellation score
    canc_raw = str(offer.get("cancellation_policy", "")).strip().lower()
    canc_score = CANCELLATION_SCORES.get(canc_raw)
    if canc_score is None:
        if "48" in canc_raw:
            canc_score = 1.0
        elif "24" in canc_raw:
            canc_score = 0.8
        elif "partial" in canc_raw:
            canc_score = 0.5
        elif "non" in canc_raw:
            canc_score = 0.1
        else:
            canc_score = 0.5

    # 3. Payment terms score
    pay_raw = str(offer.get("payment_terms", "")).strip().lower()
    pay_score = PAYMENT_TERMS_SCORES.get(pay_raw)
    if pay_score is None:
        if "hotel" in pay_raw:
            pay_score = 1.0
        elif "later" in pay_raw or "deposit" in pay_raw:
            pay_score = 0.7
        else:
            pay_score = 0.4

    # 4. Supplier reliability
    rel_raw = offer.get("reliability", 1.0)
    try:
        rel_score = float(rel_raw) if rel_raw is not None else 1.0
    except (ValueError, TypeError):
        rel_score = 1.0

    total = (
        OFFER_WEIGHT_PRICE * price_score
        + OFFER_WEIGHT_CANCELLATION * canc_score
        + OFFER_WEIGHT_PAYMENT_TERMS * pay_score
        + OFFER_WEIGHT_RELIABILITY * rel_score
    )
    return total


def best_offer(offers: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], str]:
    """Select the best offer and build an explanatory reason string.

    Returns:
        (top_offer, reason_string)
    """
    if not offers:
        return {}, "No offers available"

    scored_offers = [(value_score(o, offers), o) for o in offers]
    # Sort descending by score; ties broken by lowest price, then higher reliability
    scored_offers.sort(
        key=lambda item: (
            item[0],
            -float(item[1].get("price_inr") or 0.0),
            float(item[1].get("reliability") or 0.0),
        ),
        reverse=True,
    )
    top_score, top_offer = scored_offers[0]

    valid_prices = [
        float(o["price_inr"])
        for o in offers
        if o.get("price_inr") is not None and str(o.get("price_inr")).lower() not in ("nan", "none", "")
    ]
    min_price = min(valid_prices) if valid_prices else 0.0
    top_price = float(top_offer.get("price_inr") or 0.0)

    price_diff = int(round(top_price - min_price))
    top_canc = str(top_offer.get("cancellation_policy", "")).strip().lower()
    top_rel = float(top_offer.get("reliability", 1.0) or 1.0)

    # Format price with commas e.g. Rs 4,400
    top_price_str = f"Rs {int(top_price):,}"

    if len(offers) == 1:
        reason = (
            f"Best value: {top_price_str}, only available offer, {top_canc}, "
            f"supplier reliability {top_rel:.2f}"
        )
    elif price_diff == 0:
        reason = (
            f"Best value: {top_price_str}, cheapest available, {top_canc}, "
            f"supplier reliability {top_rel:.2f}"
        )
    else:
        diff_str = f"Rs {price_diff:,}"
        reason = (
            f"Best value: {top_price_str}, {diff_str} above the cheapest, {top_canc}, "
            f"supplier reliability {top_rel:.2f}"
        )

    return top_offer, reason


def _most_common(items: List[Any], fallback: Any = "") -> Any:
    """Find the most common item in a list."""
    valid = [x for x in items if x is not None and str(x).strip() != "" and str(x).lower() not in ("nan", "none")]
    if not valid:
        return fallback
    counts = Counter(valid)
    return counts.most_common(1)[0][0]


def _pick_cluster_name(names: List[str]) -> str:
    """Select the most common name, breaking ties with the longest clean one."""
    clean_names = [
        str(n).strip()
        for n in names
        if n is not None and str(n).strip() != "" and str(n).lower() not in ("nan", "none")
    ]
    if not clean_names:
        return ""

    counts = Counter(clean_names)
    max_freq = max(counts.values())
    candidates = [name for name, freq in counts.items() if freq == max_freq]
    # Break ties by longest clean name
    candidates.sort(key=lambda s: len(s), reverse=True)
    return candidates[0]


def build_catalogue(
    df: pd.DataFrame,
    clusters: Union[Dict[str, str], pd.DataFrame],
    suppliers_df: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """Build one master hotel record per cluster.

    Each master record includes:
    - cluster_id
    - name: most common name (ties: longest clean one)
    - address: most common clean address
    - pincode: most common clean pincode
    - city: most common clean city
    - lat, lon: mean GPS of rows that have it
    - stars: most common star rating
    - offers: list of offers from rows in this cluster
    - best_offer: top offer selected by value_score
    - best_offer_reason: explanation string
    """
    # 1. Resolve cluster mapping: row_id -> cluster_id
    if isinstance(clusters, pd.DataFrame):
        row_to_cluster = dict(zip(clusters["row_id"].astype(str), clusters["cluster_id"].astype(str)))
    else:
        row_to_cluster = {str(k): str(v) for k, v in clusters.items()}

    # 2. Resolve supplier reliability mapping
    supplier_rel: Dict[str, float] = {}
    if suppliers_df is not None and not suppliers_df.empty:
        for _, srow in suppliers_df.iterrows():
            sup_code = str(srow.get("supplier", "")).strip()
            try:
                rel_val = float(srow.get("reliability", 1.0))
            except (ValueError, TypeError):
                rel_val = 1.0
            supplier_rel[sup_code] = rel_val

    # Group dataframe records by cluster
    rows = df.to_dict("records")
    cluster_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        rid = str(r["row_id"])
        cid = row_to_cluster.get(rid, f"C_{rid}")
        cluster_groups.setdefault(cid, []).append(r)

    catalogue: List[Dict[str, Any]] = []

    for cid in sorted(cluster_groups.keys()):
        group = cluster_groups[cid]

        # Name: most common, ties: longest clean one
        names = [r.get("name") for r in group]
        canonical_name = _pick_cluster_name(names)

        # Address, pincode, city, stars: most common
        canonical_address = _most_common([r.get("address") for r in group], fallback="")
        canonical_pincode = _most_common([r.get("pincode") for r in group], fallback="")
        canonical_city = _most_common([r.get("city") for r in group], fallback="")
        canonical_stars = _most_common([r.get("stars") for r in group], fallback=None)

        # Mean GPS
        lats: List[float] = []
        lons: List[float] = []
        for r in group:
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is not None and lon is not None:
                try:
                    flat, flon = float(lat), float(lon)
                    if not (pd.isna(flat) or pd.isna(flon)):
                        lats.append(flat)
                        lons.append(flon)
                except (ValueError, TypeError):
                    pass

        mean_lat = sum(lats) / len(lats) if lats else None
        mean_lon = sum(lons) / len(lons) if lons else None

        # Build list of offers
        offers: List[Dict[str, Any]] = []
        for r in group:
            sup = str(r.get("supplier", "")).strip()
            rel = supplier_rel.get(sup)
            if rel is None:
                r_rel = r.get("reliability")
                try:
                    rel = float(r_rel) if r_rel is not None and not pd.isna(r_rel) else 1.0
                except (ValueError, TypeError):
                    rel = 1.0

            price_raw = r.get("price_inr")
            try:
                price_val = float(price_raw) if price_raw is not None and not pd.isna(price_raw) else 0.0
            except (ValueError, TypeError):
                price_val = 0.0

            offer = {
                "row_id": str(r.get("row_id", "")),
                "supplier": sup,
                "price_inr": price_val,
                "cancellation_policy": str(r.get("cancellation_policy", "")).strip(),
                "payment_terms": str(r.get("payment_terms", "")).strip(),
                "reliability": rel,
            }
            offers.append(offer)

        top_offer, reason = best_offer(offers)

        record = {
            "cluster_id": cid,
            "name": canonical_name,
            "address": canonical_address,
            "pincode": canonical_pincode,
            "city": canonical_city,
            "lat": mean_lat,
            "lon": mean_lon,
            "stars": canonical_stars,
            "offers": offers,
            "best_offer": top_offer,
            "best_offer_reason": reason,
        }
        catalogue.append(record)

    return catalogue


def main():
    """Build outputs/catalogue.json from target data directory and predictions."""
    target_data = sys.argv[1] if len(sys.argv) > 1 else "data/dev"
    pred_path = sys.argv[2] if len(sys.argv) > 2 else "outputs/predictions.csv"
    out_path = "outputs/catalogue.json"

    logger.info("Building catalogue for data dir %s using %s", target_data, pred_path)

    raw_df = load_rows(target_data)
    prep_df = prepare(raw_df)

    # Read predictions
    if not os.path.exists(pred_path):
        from src.pipeline import run_pipeline

        logger.info("Running pipeline to generate %s first...", pred_path)
        run_pipeline(data_dir=target_data, mode="rules-only", pred_path=pred_path)

    clusters_df = pd.read_csv(pred_path)

    suppliers_path = os.path.join(target_data, "suppliers.csv")
    suppliers_df = pd.read_csv(suppliers_path) if os.path.exists(suppliers_path) else None

    catalogue = build_catalogue(prep_df, clusters_df, suppliers_df)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, indent=2)

    print(f"\nSuccessfully built catalogue with {len(catalogue)} master records.")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
