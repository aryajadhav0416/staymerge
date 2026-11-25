"""FastAPI backend service for StayMerge hotel catalogue and matching engine."""
import csv
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StayMerge API",
    description="Backend API serving merged hotel catalogue, matching decisions, and feed statistics.",
    version="1.0.0",
)

# ---------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------
web_origin = os.getenv("WEB_ORIGIN", "http://localhost:3000")
allowed_origins = list({web_origin, "http://localhost:3000"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# File Paths
# ---------------------------------------------------------
OUTPUTS_DIR = "outputs"
DATA_DIR = os.getenv("DATA_DIR", "data/test")
CATALOGUE_PATH = os.path.join(OUTPUTS_DIR, "catalogue.json")
DECISIONS_PATH = os.path.join(OUTPUTS_DIR, "decisions.csv")
PREDICTIONS_PATH = os.path.join(OUTPUTS_DIR, "predictions.csv")
METRICS_PATH = os.path.join(OUTPUTS_DIR, "metrics.json")
REVIEW_DECISIONS_PATH = os.path.join(OUTPUTS_DIR, "review_decisions.csv")

MOCK_DIR = os.path.join("api", "mock")


def is_mock_enabled() -> bool:
    """Check if USE_MOCK environment variable is set."""
    return os.getenv("USE_MOCK", "0").strip() in ("1", "true", "True")


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class OfferModel(BaseModel):
    row_id: str
    supplier: str
    price_inr: float
    cancellation_policy: str
    payment_terms: str
    reliability: float


class SimilarHotelModel(BaseModel):
    hotel_id: str
    name: str
    similarity: float
    reason: str
    area: Optional[str] = None
    city: Optional[str] = None


class HotelSummary(BaseModel):
    cluster_id: str
    name: str
    address: str
    pincode: str
    city: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    stars: Optional[str] = None
    offers: List[OfferModel]
    best_offer: OfferModel
    best_offer_reason: str


class HotelDetail(HotelSummary):
    similar_hotels: List[SimilarHotelModel] = []


class DecisionModel(BaseModel):
    row_a: str
    row_b: str
    hotel_a_id: Optional[str] = None
    hotel_b_id: Optional[str] = None
    score: float
    band: str
    llm_same: Optional[str] = None
    llm_confidence: Optional[str] = None
    llm_reason: str = ""
    final_decision: str
    explanation: str


class MetricsModel(BaseModel):
    precision: float
    recall: float
    f1: float
    hard_row_recall: float
    trap_false_merges: int
    total_trap_pairs: int
    predicted_hotels: int
    true_hotels: int
    rows_scored: int


class SupplierRowModel(BaseModel):
    row_id: str
    supplier: str
    supplier_hotel_id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    stars: Optional[Union[float, int, str]] = None
    price_inr: Optional[Union[float, int]] = None
    cancellation_policy: Optional[str] = None
    payment_terms: Optional[str] = None


class SupplierFeedModel(BaseModel):
    supplier: str
    name: str
    row_count: int
    reliability: float
    rows: Optional[List[Dict[str, Any]]] = None


class FeedsResponse(BaseModel):
    suppliers: List[SupplierFeedModel]


class ReviewDecisionRequest(BaseModel):
    pair_id: Optional[str] = None
    row_a: str
    row_b: str
    action: str  # "merge" or "split"
    notes: Optional[str] = ""


class ReviewDecisionResponse(BaseModel):
    status: str
    message: str
    recorded: ReviewDecisionRequest


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def load_json_or_503(file_path: str, resource_name: str) -> Any:
    """Read a JSON file or raise 503 if missing."""
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{resource_name} is not available yet. Please run the pipeline or use mock mode.",
        )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to read {resource_name}: {str(e)}",
        )


def load_predictions_map() -> Dict[str, str]:
    """Load row_id -> cluster_id from predictions.csv."""
    if not os.path.exists(PREDICTIONS_PATH):
        return {}
    mapping = {}
    with open(PREDICTIONS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            mapping[r["row_id"]] = r["cluster_id"]
    return mapping


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "mock_mode": is_mock_enabled()}


@app.get("/hotels", response_model=List[HotelSummary])
@app.get("/catalogue", response_model=List[HotelSummary])
def get_hotels(city: Optional[str] = None, q: Optional[str] = None):
    """Get list of master hotels in catalogue."""
    if is_mock_enabled():
        data = load_json_or_503(os.path.join(MOCK_DIR, "hotels.json"), "Mock hotels")
    else:
        data = load_json_or_503(CATALOGUE_PATH, "Catalogue")

    results = []
    for h in data:
        if city and str(h.get("city", "")).lower() != city.lower():
            continue
        if q and q.lower() not in str(h.get("name", "")).lower() and q.lower() not in str(h.get("address", "")).lower():
            continue
        results.append(h)
    return results


@app.get("/hotels/{hotel_id}", response_model=HotelDetail)
def get_hotel_detail(hotel_id: str):
    """Get detail for a specific hotel including similar hotels kept separate."""
    if is_mock_enabled():
        mock_file = os.path.join(MOCK_DIR, "hotel_detail.json")
        data = load_json_or_503(mock_file, "Mock hotel detail")
        if data.get("cluster_id") == hotel_id or hotel_id == "C0001":
            data["cluster_id"] = hotel_id
            return data
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hotel {hotel_id} not found")

    catalogue = load_json_or_503(CATALOGUE_PATH, "Catalogue")
    hotel = next((h for h in catalogue if h.get("cluster_id") == hotel_id), None)
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hotel {hotel_id} not found")

    # Build similar_hotels from decisions.csv:
    # pairs whose name similarity is 0.8 or more but were decided different.
    similar_hotels: List[Dict[str, Any]] = []
    if os.path.exists(DECISIONS_PATH):
        pred_map = load_predictions_map()
        cat_by_id = {h["cluster_id"]: h for h in catalogue}

        # Cluster's own rows
        cluster_rows = {o["row_id"] for o in hotel.get("offers", [])}

        seen_partner_hotels = set()
        with open(DECISIONS_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ra, rb = r.get("row_a", ""), r.get("row_b", "")
                final_dec = str(r.get("final_decision", "")).lower()

                # Looking for pairs involving this hotel decided different
                if final_dec != "false":
                    continue

                partner_row = None
                if ra in cluster_rows and rb not in cluster_rows:
                    partner_row = rb
                elif rb in cluster_rows and ra not in cluster_rows:
                    partner_row = ra

                if not partner_row:
                    continue

                # Check name similarity in explanation
                expl = r.get("explanation", "")
                m = re.search(r"name\s+([\d\.]+)", expl)
                if not m:
                    continue
                try:
                    sim = float(m.group(1))
                except ValueError:
                    continue

                if sim < 0.8:
                    continue

                partner_cid = pred_map.get(partner_row)
                if not partner_cid or partner_cid == hotel_id or partner_cid in seen_partner_hotels:
                    continue

                partner_hotel = cat_by_id.get(partner_cid)
                if partner_hotel:
                    seen_partner_hotels.add(partner_cid)
                    similar_hotels.append(
                        {
                            "hotel_id": partner_cid,
                            "name": partner_hotel.get("name", ""),
                            "similarity": sim,
                            "reason": expl,
                            "area": partner_hotel.get("address") or partner_hotel.get("city") or "",
                            "city": partner_hotel.get("city") or "",
                        }
                    )

    # Sort by similarity descending
    similar_hotels.sort(key=lambda x: x["similarity"], reverse=True)

    result = dict(hotel)
    result["similar_hotels"] = similar_hotels
    return result


@app.get("/decisions", response_model=List[DecisionModel])
def get_decisions(band: Optional[str] = None, final_decision: Optional[str] = None):
    """Get candidate pair decisions."""
    if is_mock_enabled():
        data = load_json_or_503(os.path.join(MOCK_DIR, "decisions.json"), "Mock decisions")
        return data

    if not os.path.exists(DECISIONS_PATH):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Decisions file is not available yet. Please run the pipeline first.",
        )

    pred_map = load_predictions_map()
    decisions = []
    with open(DECISIONS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            b = r.get("band", "")
            fd = str(r.get("final_decision", "")).lower()

            if band and b != band:
                continue
            if final_decision and fd != final_decision.lower():
                continue

            ra, rb = r.get("row_a", ""), r.get("row_b", "")
            try:
                sc = float(r.get("score", 0.0))
            except ValueError:
                sc = 0.0

            decisions.append(
                {
                    "row_a": ra,
                    "row_b": rb,
                    "hotel_a_id": pred_map.get(ra),
                    "hotel_b_id": pred_map.get(rb),
                    "score": sc,
                    "band": b,
                    "llm_same": r.get("llm_same") or None,
                    "llm_confidence": r.get("llm_confidence") or None,
                    "llm_reason": r.get("llm_reason") or "",
                    "final_decision": fd,
                    "explanation": r.get("explanation") or "",
                }
            )
    return decisions


@app.get("/metrics", response_model=MetricsModel)
def get_metrics():
    """Get matcher accuracy metrics against ground truth."""
    if is_mock_enabled():
        return load_json_or_503(os.path.join(MOCK_DIR, "metrics.json"), "Mock metrics")

    return load_json_or_503(METRICS_PATH, "Metrics")


@app.get("/feeds", response_model=FeedsResponse)
def get_feeds():
    """Get raw supplier feeds metadata and counts."""
    if is_mock_enabled():
        return load_json_or_503(os.path.join(MOCK_DIR, "feeds.json"), "Mock feeds")

    suppliers = [
        {"supplier": "A", "name": "Supplier A", "file": "supplier_a.csv"},
        {"supplier": "B", "name": "Supplier B", "file": "supplier_b.csv"},
        {"supplier": "C", "name": "Supplier C", "file": "supplier_c.csv"},
    ]

    suppliers_info_path = os.path.join(DATA_DIR, "suppliers.csv")
    reliabilities = {}
    if os.path.exists(suppliers_info_path):
        with open(suppliers_info_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    reliabilities[r["supplier"]] = float(r["reliability"])
                except Exception:
                    pass

    feed_results = []
    for s in suppliers:
        feed_path = os.path.join(DATA_DIR, s["file"])
        if not os.path.exists(feed_path):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Supplier feed {s['file']} not found in {DATA_DIR}",
            )
        # Read records
        rows = []
        with open(feed_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                # Convert null/empty strings to None where applicable
                cleaned = {k: (v if v != "" and str(v).lower() != "nan" else None) for k, v in r.items()}
                rows.append(cleaned)

        feed_results.append(
            {
                "supplier": s["supplier"],
                "name": s["name"],
                "row_count": len(rows),
                "reliability": reliabilities.get(s["supplier"], 1.0),
                "rows": rows,
            }
        )

    return {"suppliers": feed_results}


@app.post("/reviews", response_model=ReviewDecisionResponse)
@app.post("/review-decision", response_model=ReviewDecisionResponse)
def submit_review_decision(req: ReviewDecisionRequest):
    """Submit a human-in-the-loop review decision for a pair."""
    action = req.action.strip().lower()
    if action not in ("merge", "split"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid action '{req.action}'. Action must be 'merge' or 'split'.",
        )
    if not req.row_a or not req.row_b:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both 'row_a' and 'row_b' must be provided.",
        )

    os.makedirs(os.path.dirname(REVIEW_DECISIONS_PATH), exist_ok=True)
    file_exists = os.path.exists(REVIEW_DECISIONS_PATH)

    with open(REVIEW_DECISIONS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["pair_id", "row_a", "row_b", "action", "notes"])
        writer.writerow([req.pair_id or f"{req.row_a}_{req.row_b}", req.row_a, req.row_b, action, req.notes or ""])

    return {
        "status": "success",
        "message": f"Review decision recorded: {action} pair ({req.row_a}, {req.row_b})",
        "recorded": req,
    }


@app.get("/review-queue")
def get_review_queue():
    """Get review queue pairs (unsure pairs and review decisions)."""
    if is_mock_enabled():
        data = load_json_or_503(os.path.join(MOCK_DIR, "decisions.json"), "Mock decisions")
        return data

    if not os.path.exists(DECISIONS_PATH):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Decisions file is not available yet. Please run the pipeline first.",
        )

    pred_map = load_predictions_map()
    decisions = []
    with open(DECISIONS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            b = r.get("band", "")
            if b == "unsure":
                ra, rb = r.get("row_a", ""), r.get("row_b", "")
                try:
                    sc = float(r.get("score", 0.0))
                except ValueError:
                    sc = 0.0

                decisions.append(
                    {
                        "row_a": ra,
                        "row_b": rb,
                        "hotel_a_id": pred_map.get(ra),
                        "hotel_b_id": pred_map.get(rb),
                        "score": sc,
                        "band": b,
                        "llm_same": r.get("llm_same") or None,
                        "llm_confidence": r.get("llm_confidence") or None,
                        "llm_reason": r.get("llm_reason") or "",
                        "final_decision": str(r.get("final_decision", "")).lower(),
                        "explanation": r.get("explanation") or "",
                    }
                )
    return decisions


@app.get("/review-decisions")
def get_recorded_review_decisions():
    """Get all saved human review decisions."""
    if not os.path.exists(REVIEW_DECISIONS_PATH):
        return []
    records = []
    with open(REVIEW_DECISIONS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append(
                {
                    "pair_id": r.get("pair_id") or f"{r.get('row_a')}_{r.get('row_b')}",
                    "row_a": r.get("row_a", ""),
                    "row_b": r.get("row_b", ""),
                    "action": r.get("action", ""),
                    "notes": r.get("notes", ""),
                }
            )
    return records

