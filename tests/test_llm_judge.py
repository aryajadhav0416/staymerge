"""Unit tests for Groq LLM judge (mocked client, no network)."""
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from src.llm_judge import (
    ALLOWED_FIELDS,
    call_groq_model,
    compute_pair_hash,
    extract_allowed_fields,
    get_cached_decision,
    init_cache_db,
    judge_pair,
    parse_llm_json,
    store_cached_decision,
)


def test_extract_allowed_fields():
    """Ensure price, supplier, ids and unallowed fields are stripped."""
    row = {
        "row_id": "A-001",
        "supplier": "A",
        "supplier_hotel_id": "SUP123",
        "price_inr": 4500,
        "name": "Taj Lands End",
        "address": "BJ Road, Bandra",
        "city": "Mumbai",
        "pincode": "400050",
        "lat": 19.043,
        "lon": 72.819,
        "phone": "2266681234",
        "stars": 5,
        "cancellation_policy": "Free",
    }
    extracted = extract_allowed_fields(row)
    assert set(extracted.keys()) == set(ALLOWED_FIELDS)
    assert "price_inr" not in extracted
    assert "supplier" not in extracted
    assert "row_id" not in extracted
    assert extracted["name"] == "Taj Lands End"


def test_compute_pair_hash_order_independent():
    """Ensure pair hash is identical regardless of pair order."""
    row_a = {"name": "Hotel Alpha", "city": "Delhi"}
    row_b = {"name": "Hotel Beta", "city": "Delhi"}
    hash1 = compute_pair_hash(row_a, row_b)
    hash2 = compute_pair_hash(row_b, row_a)
    assert hash1 == hash2


def test_parse_llm_json_clean_and_fenced():
    """Test parsing clean json and markdown-fenced json."""
    raw1 = '{"same": true, "confidence": 0.95, "reason": "Identical hotel"}'
    res1 = parse_llm_json(raw1)
    assert res1 == {"same": True, "confidence": 0.95, "reason": "Identical hotel"}

    raw2 = '```json\n{"same": false, "confidence": 0.8, "reason": "Different address"}\n```'
    res2 = parse_llm_json(raw2)
    assert res2 == {"same": False, "confidence": 0.8, "reason": "Different address"}

    raw3 = "Some conversational preface\n```\n{\"same\": true, \"confidence\": 0.75, \"reason\": \"Same hotel\"}\n```"
    res3 = parse_llm_json(raw3)
    assert res3 == {"same": True, "confidence": 0.75, "reason": "Same hotel"}


def test_init_cache_db_schema():
    """Verify that init_cache_db creates the expected table and columns."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name
        conn = init_cache_db(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(judge_cache);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected = {"pair_hash", "same", "confidence", "reason", "model", "created_at"}
        assert expected.issubset(set(columns.keys()))


def test_cache_hit_and_system_prompt_change_miss():
    """Verify same pair hits cache, while modified system prompt results in a cache miss."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name
        row_a = {"name": "Grand Hotel", "city": "Bengaluru"}
        row_b = {"name": "Grand Hotel & Suites", "city": "Bengaluru"}

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content='{"same": true, "confidence": 0.95, "reason": "Match"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_resp

        # 1. First invocation: populates cache
        same1, conf1, reason1 = judge_pair(
            row_a, row_b, client=mock_client, db_path=db_path, system_prompt="System Prompt V1"
        )
        assert same1 is True
        assert mock_client.chat.completions.create.call_count == 1

        # 2. Second invocation with same system prompt: cache HIT (client create NOT called again)
        same2, conf2, reason2 = judge_pair(
            row_a, row_b, client=mock_client, db_path=db_path, system_prompt="System Prompt V1"
        )
        assert same2 is True
        assert mock_client.chat.completions.create.call_count == 1

        # 3. Third invocation with changed system prompt: cache MISS (client create called again)
        same3, conf3, reason3 = judge_pair(
            row_a, row_b, client=mock_client, db_path=db_path, system_prompt="System Prompt V2 (Changed)"
        )
        assert same3 is True
        assert mock_client.chat.completions.create.call_count == 2



def test_judge_pair_fast_model_high_confidence():
    """Test that if fast model has high confidence, strong model is not called."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content='{"same": true, "confidence": 0.95, "reason": "Matched"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_resp

        row_a = {"name": "Oberoi", "city": "Mumbai"}
        row_b = {"name": "The Oberoi", "city": "Mumbai"}

        same, conf, reason = judge_pair(row_a, row_b, client=mock_client, db_path=db_path)
        assert same is True
        assert conf == 0.95
        assert reason == "Matched"
        # Verify chat.completions.create was called exactly once (no strong model call)
        assert mock_client.chat.completions.create.call_count == 1


def test_judge_pair_escalate_to_strong_model():
    """Test that if fast model confidence is below 0.7, strong model is called."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name
        mock_client = MagicMock()
        fast_resp = MagicMock()
        fast_resp.choices = [
            MagicMock(message=MagicMock(content='{"same": true, "confidence": 0.55, "reason": "Unsure"}'))
        ]
        strong_resp = MagicMock()
        strong_resp.choices = [
            MagicMock(message=MagicMock(content='{"same": false, "confidence": 0.85, "reason": "Different hotels"}'))
        ]
        mock_client.chat.completions.create.side_effect = [fast_resp, strong_resp]

        row_a = {"name": "Ibis Bengaluru City", "city": "Bengaluru"}
        row_b = {"name": "Ibis Styles Bengaluru", "city": "Bengaluru"}

        same, conf, reason = judge_pair(row_a, row_b, client=mock_client, db_path=db_path)
        assert same is False
        assert conf == 0.85
        assert reason == "Different hotels"
        assert mock_client.chat.completions.create.call_count == 2


@patch("time.sleep", return_value=None)
def test_judge_pair_retry_and_fallback_on_error(mock_sleep):
    """Test retry with exponential backoff on network/rate-limit error and fallback to None."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = tmp.name
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("429 Too Many Requests")

        row_a = {"name": "Hotel A", "city": "Delhi"}
        row_b = {"name": "Hotel B", "city": "Delhi"}

        same, conf, reason = judge_pair(row_a, row_b, client=mock_client, db_path=db_path)
        assert same is None
        assert conf == 0.0
        assert reason == "llm_error_fallback"
        # Should have retried 4 times on fast model
        assert mock_client.chat.completions.create.call_count == 4

