"""Unit tests for hotel data normalization functions."""
import os
import pandas as pd
import pytest

from src.normalize import (
    canonical_city,
    load_rows,
    normalize_address,
    normalize_name,
    normalize_phone,
    parse_gps,
    prepare,
)


def test_normalize_name_strip_suffix():
    """Test dropping promotional text after ' - '."""
    assert normalize_name("IBIS BENGALURU KORAMANGALA - Best Price") == "ibis bengaluru koramangala"


def test_normalize_name_stopwords_order():
    """Test removing 'hotel' and 'the' from names."""
    assert normalize_name("Hotel The Royal Palace") == normalize_name("Royal Palace Hotel")
    assert normalize_name("Hotel The Royal Palace") == "royal palace"


def test_normalize_name_brackets_and_ampersand():
    """Test brackets and ampersand handling in name."""
    assert normalize_name("Bed & Breakfast [Book Now]") == "bed breakfast"


def test_canonical_city_mapping():
    """Test city alias mapping case-insensitively."""
    assert canonical_city("Bangalore") == "Bengaluru"
    assert canonical_city("bangalore") == "Bengaluru"
    assert canonical_city("Bombay") == "Mumbai"
    assert canonical_city("New Delhi") == "Delhi"
    assert canonical_city("Cochin") == "Kochi"
    assert canonical_city("Calcutta") == "Kolkata"
    assert canonical_city("Madras") == "Chennai"


def test_normalize_address_expansions():
    """Test abbreviation expansions for Nr. and Opp. and St. and Rd."""
    addr, plot = normalize_address("152/A, STATION RD, NR. CENTRAL MARKET, C-SCHEME")
    assert "road" in addr
    assert "near" in addr
    assert plot == "152/A"

    addr2, plot2 = normalize_address("37, MG Road, Opp. Metro Station")
    assert "opposite" in addr2
    assert plot2 == "37"

    addr3, plot3 = normalize_address("Behind Bhd. Temple, St. Marks Road")
    assert "behind" in addr3
    assert "street" in addr3
    assert plot3 is None


def test_normalize_phone_last8():
    """Test extracting last 8 digits from phone numbers."""
    last8, is_central = normalize_phone("+91-40-74019136")
    assert last8 == "74019136"
    assert not is_central


def test_normalize_phone_trailing_dot_zero():
    """Test that float-like trailing .0 and formatted phone give the same last 8 digits."""
    last8_a, _ = normalize_phone("4026733967.0")
    last8_b, _ = normalize_phone("+91-40-26733967")
    assert last8_a == "26733967"
    assert last8_b == "26733967"
    assert last8_a == last8_b


def test_normalize_phone_central_1800():
    """Test identifying 1800 central toll-free numbers."""
    last8, is_central = normalize_phone("1800-111-2222")
    assert is_central is True
    assert last8 == "01112222"


def test_parse_gps_valid():
    """Test parsing valid coordinates."""
    coords = parse_gps("17.439994", "78.498045")
    assert coords is not None
    assert pytest.approx(coords[0], 0.0001) == 17.439994
    assert pytest.approx(coords[1], 0.0001) == 78.498045


def test_parse_gps_missing():
    """Test missing or invalid GPS coordinates return None."""
    assert parse_gps(None, None) is None
    assert parse_gps(float("nan"), 78.498) is None
    assert parse_gps("", "") is None
    assert parse_gps("invalid", 78.498) is None


def test_prepare_dataframe():
    """Test preparing a dataframe with derived columns."""
    sample_df = pd.DataFrame([
        {
            "row_id": "T-01",
            "supplier": "A",
            "name": "Hotel The Royal Palace - Book Now",
            "address": "66/B, Residency Rd, Opp. Mall",
            "city": "Bangalore",
            "phone": "1800 200 3000",
            "lat": 12.9716,
            "lon": 77.5946,
        }
    ])
    prep = prepare(sample_df)
    assert prep["norm_name"].iloc[0] == "royal palace"
    assert prep["norm_city"].iloc[0] == "Bengaluru"
    assert prep["plot_number"].iloc[0] == "66/B"
    assert "opposite" in prep["norm_address"].iloc[0]
    assert bool(prep["phone_is_central"].iloc[0]) is True
    assert prep["gps"].iloc[0] == (12.9716, 77.5946)


def test_load_rows_dev():
    """Test loading rows from data/dev directory."""
    df = load_rows("data/dev")
    assert not df.empty
    assert "supplier" in df.columns
    assert "reliability" in df.columns
    assert set(df["supplier"].unique()) == {"A", "B", "C"}
