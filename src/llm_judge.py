"""LLM judge interface via Groq."""
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
import groq

from src.config import (
    GROQ_MODEL_FAST,
    GROQ_MODEL_STRONG,
    LLM_CACHE_DB_PATH,
    LLM_CONFIDENCE_THRESHOLD,
    LLM_MAX_RETRIES,
    LLM_TEMPERATURE,
)

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You decide whether two supplier listings describe the same physical hotel. "
    "Names may be misspelled, reordered or have extra words. "
    "GPS can be off by up to 600 metres for the same hotel. "
    "Phone numbers beginning with 1800 are chain-wide numbers and prove nothing. "
    "Two hotels of the same chain in different areas are different hotels. "
    "A sub-brand such as Ibis and Ibis Styles is a different hotel. "
    "Different building or plot numbers on the same street, or different star ratings, "
    "suggest different hotels. If the evidence is weak, say same is false with low confidence."
)

ALLOWED_FIELDS = ["name", "address", "city", "pincode", "lat", "lon", "phone", "stars"]

# Global client cache and call counters
_GROQ_CLIENT: Optional[groq.Groq] = None
API_CALL_COUNT: int = 0


def get_groq_client() -> groq.Groq:
    """Get or initialize the Groq client from environment."""
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None:
        api_key = os.getenv("GROQ_API_KEY")
        _GROQ_CLIENT = groq.Groq(api_key=api_key)
    return _GROQ_CLIENT


def init_cache_db(db_path: str = LLM_CACHE_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database for caching LLM judge decisions."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS judge_cache (
                pair_hash TEXT PRIMARY KEY,
                same INTEGER,
                confidence REAL,
                reason TEXT,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    return conn


def extract_allowed_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the allowed fields from a row, ignoring price, supplier, ids."""
    res = {}
    for f in ALLOWED_FIELDS:
        val = row.get(f)
        if val is not None and not (isinstance(val, float) and str(val).lower() == "nan"):
            res[f] = val
        else:
            res[f] = None
    return res


def compute_pair_hash(
    row_a: Dict[str, Any],
    row_b: Dict[str, Any],
    model: str = "",
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    """Compute deterministic, order-independent SHA-256 hash of rows, model, and system prompt."""
    if not model:
        model = GROQ_MODEL_FAST

    fa = extract_allowed_fields(row_a)
    fb = extract_allowed_fields(row_b)

    sa = json.dumps(fa, sort_keys=True, default=str)
    sb = json.dumps(fb, sort_keys=True, default=str)

    ordered = sorted([sa, sb])
    combined = "||".join(ordered) + f"||prompt:{system_prompt}||model:{model}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_cached_decision(pair_hash: str, db_path: str = LLM_CACHE_DB_PATH) -> Optional[Tuple[Optional[bool], float, str]]:
    """Retrieve decision from SQLite cache if present."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT same, confidence, reason FROM judge_cache WHERE pair_hash = ?", (pair_hash,))
            row = cursor.fetchone()
            if row:
                same = bool(row[0]) if row[0] is not None else None
                return same, float(row[1]), str(row[2])
    except Exception as e:
        logger.warning("Cache read failed: %s", e)
    return None


def store_cached_decision(
    pair_hash: str,
    same: Optional[bool],
    confidence: float,
    reason: str,
    model: str,
    db_path: str = LLM_CACHE_DB_PATH,
) -> None:
    """Store decision into SQLite cache."""
    try:
        conn = init_cache_db(db_path)
        with conn:
            same_val = int(same) if same is not None else None
            conn.execute(
                """
                INSERT OR REPLACE INTO judge_cache (pair_hash, same, confidence, reason, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pair_hash, same_val, confidence, reason, model),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


def parse_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Defensively parse JSON from LLM response, stripping markdown code fences."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "same" in data:
            same = bool(data["same"])
            conf = float(data.get("confidence", 0.5))
            reason = str(data.get("reason", ""))
            return {"same": same, "confidence": conf, "reason": reason}
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "same" in data:
                    return {
                        "same": bool(data["same"]),
                        "confidence": float(data.get("confidence", 0.5)),
                        "reason": str(data.get("reason", "")),
                    }
            except Exception:
                pass
    return None


def call_groq_model(
    client: groq.Groq,
    model: str,
    row_a: Dict[str, Any],
    row_b: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Call Groq chat completion with exponential backoff on errors."""
    fa = extract_allowed_fields(row_a)
    fb = extract_allowed_fields(row_b)

    user_prompt = (
        f"Hotel 1:\n{json.dumps(fa, indent=2)}\n\n"
        f"Hotel 2:\n{json.dumps(fb, indent=2)}\n\n"
        "Return a JSON object with keys:\n"
        '{"same": true or false, "confidence": float between 0 and 1, "reason": "one sentence explanation"}'
    )

    backoff = 1.0
    global API_CALL_COUNT
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            API_CALL_COUNT += 1
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_TEMPERATURE,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            parsed = parse_llm_json(content)
            if parsed:
                return parsed
            else:
                logger.warning("Unparseable JSON from model %s: %s", model, content)
                return None
        except Exception as e:
            err_str = str(e).lower()
            logger.warning("Groq API error on attempt %d for model %s: %s", attempt, model, e)
            if attempt < LLM_MAX_RETRIES:
                time.sleep(backoff)
                backoff *= 2.0
            else:
                logger.error("Max retries exceeded for model %s: %s", model, e)
                return None
    return None


def judge_pair(
    row_a: Dict[str, Any],
    row_b: Dict[str, Any],
    client: Optional[groq.Groq] = None,
    db_path: str = LLM_CACHE_DB_PATH,
    system_prompt: str = SYSTEM_PROMPT,
) -> Tuple[Optional[bool], float, str]:
    """Judge whether two hotel records describe the same physical hotel.

    Returns:
        (same, confidence, reason)
        where same is True, False, or None on persistent failure.
    """
    fast_model = GROQ_MODEL_FAST
    strong_model = GROQ_MODEL_STRONG

    pair_hash = compute_pair_hash(row_a, row_b, model=fast_model, system_prompt=system_prompt)

    cached = get_cached_decision(pair_hash, db_path=db_path)
    if cached is not None:
        return cached

    if client is None:
        client = get_groq_client()

    # 1. Ask fast model
    fast_result = call_groq_model(client, fast_model, row_a, row_b)
    used_model = fast_model
    final_result = fast_result

    # 2. If confidence is below threshold (and fast model didn't fail with network error), ask strong model
    if fast_result is not None and fast_result.get("confidence", 0.0) < LLM_CONFIDENCE_THRESHOLD:
        strong_result = call_groq_model(client, strong_model, row_a, row_b)
        if strong_result is not None:
            final_result = strong_result
            used_model = strong_model

    if final_result is None:
        # Persistent failure: fall back to None
        return None, 0.0, "llm_error_fallback"

    same = final_result["same"]
    confidence = final_result["confidence"]
    reason = final_result["reason"]

    store_cached_decision(pair_hash, same, confidence, reason, used_model, db_path=db_path)
    return same, confidence, reason
