"""Configuration parameters, thresholds, and weights for hotel-merge."""

import os
from dotenv import load_dotenv

load_dotenv()

# Random seed for determinism
RANDOM_SEED = 42

# Geodesic constants
EARTH_RADIUS_M = 6371000.0

# Candidate generation blocking thresholds
CANDIDATE_NAME_SIMILARITY_MIN = 50.0

# Rule weights and feature scoring constants
WEIGHT_NAME_SIM = 3.0

PHONE_MATCH_SCORE = 1.5
PHONE_MISMATCH_SCORE = -0.3

PINCODE_MATCH_SCORE = 0.5
PINCODE_MISMATCH_SCORE = -1.0

PLOT_MATCH_SCORE = 1.0
PLOT_MISMATCH_SCORE = -0.8

GPS_NEAR_METERS = 200.0
GPS_MID_METERS = 450.0

GPS_NEAR_200_SCORE = 1.0
GPS_MID_450_SCORE = 0.3
GPS_FAR_SCORE = -1.5

STARS_MATCH_SCORE = 0.2
STARS_MISMATCH_SCORE = -0.8

# Band classification thresholds
BAND_HIGH_THRESHOLD = 3.8
BAND_LOW_THRESHOLD = 2.0

# Rules-only clustering threshold
RULES_ONLY_MATCH_THRESHOLD = 3.0

# LLM settings
LLM_CACHE_DB_PATH = "outputs/llm_cache.db"

GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST")
if not GROQ_MODEL_FAST:
    raise ValueError("Missing required environment variable: GROQ_MODEL_FAST")

GROQ_MODEL_STRONG = os.getenv("GROQ_MODEL_STRONG")
if not GROQ_MODEL_STRONG:
    raise ValueError("Missing required environment variable: GROQ_MODEL_STRONG")

LLM_TEMPERATURE = 0.0
LLM_CONFIDENCE_THRESHOLD = 0.7
LLM_MAX_RETRIES = 4

# Offer value scoring weights
OFFER_WEIGHT_PRICE = 0.45
OFFER_WEIGHT_CANCELLATION = 0.25
OFFER_WEIGHT_PAYMENT_TERMS = 0.10
OFFER_WEIGHT_RELIABILITY = 0.20

# Offer cancellation policy scores
CANCELLATION_SCORES = {
    "free cancellation till 48h": 1.0,
    "free cancellation till 24h": 0.8,
    "partial refund": 0.5,
    "non-refundable": 0.1,
}

# Offer payment terms scores
PAYMENT_TERMS_SCORES = {
    "pay at hotel": 1.0,
    "pay later": 0.7,
    "pay later (deposit)": 0.7,
    "pay now": 0.4,
}
