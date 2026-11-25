"""Hotel data loading, cleaning, and normalization functions."""
import os
import re
import sys
from typing import Any, Optional, Tuple
import pandas as pd


CITY_ALIASES = {
    "bombay": "Mumbai",
    "new delhi": "Delhi",
    "delhi": "Delhi",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "madras": "Chennai",
    "chennai": "Chennai",
    "calcutta": "Kolkata",
    "kolkata": "Kolkata",
    "cochin": "Kochi",
    "kochi": "Kochi",
    "mumbai": "Mumbai",
}


def load_rows(data_dir: str) -> pd.DataFrame:
    """Read supplier_a.csv, supplier_b.csv, supplier_c.csv and suppliers.csv into one DataFrame."""
    files = ["supplier_a.csv", "supplier_b.csv", "supplier_c.csv"]
    dfs = []
    for fname in files:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            df_curr = pd.read_csv(fpath, dtype=str)
            dfs.append(df_curr)
        else:
            raise FileNotFoundError(f"Expected supplier file not found: {fpath}")

    combined = pd.concat(dfs, ignore_index=True)

    suppliers_path = os.path.join(data_dir, "suppliers.csv")
    if os.path.exists(suppliers_path):
        suppliers_df = pd.read_csv(suppliers_path)
        combined = combined.merge(suppliers_df, on="supplier", how="left")

    return combined


def canonical_city(city: Optional[str]) -> str:
    """Map city aliases to canonical names case-insensitively."""
    if not city or pd.isna(city):
        return ""
    normalized = str(city).strip().lower()
    if normalized in CITY_ALIASES:
        return CITY_ALIASES[normalized]
    return str(city).strip().title()


def normalize_name(name: Optional[str]) -> str:
    """Lowercase; drop text after ' - ' or in brackets; replace & with and; remove punctuation and stopwords."""
    if not name or pd.isna(name):
        return ""
    s = str(name).strip()
    s = re.split(r"\s+-\s+", s, maxsplit=1)[0]
    s = re.sub(r"\[.*?\]|\(.*?\)", " ", s)
    s = s.replace("&", " and ")
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = s.split()
    stopwords = {"hotel", "the", "and"}
    filtered = [t for t in tokens if t not in stopwords]
    return " ".join(filtered)


def normalize_address(addr: Optional[str]) -> Tuple[str, Optional[str]]:
    """Expand abbreviations, lowercase, and extract leading plot number."""
    if not addr or pd.isna(addr):
        return "", None

    raw_str = str(addr).strip()
    plot_match = re.match(r"^([0-9]+(?:[/-][0-9a-zA-Z]+)?)", raw_str)
    plot_number = plot_match.group(1) if plot_match else None

    s = raw_str.lower()
    s = re.sub(r"\brd\.?\b", "road", s)
    s = re.sub(r"\bst\.?\b", "street", s)
    s = re.sub(r"\bnr\.?\b", "near", s)
    s = re.sub(r"\bopp\.?\b", "opposite", s)
    s = re.sub(r"\bbhd\.?\b", "behind", s)

    s = re.sub(r"[^\w\s/,-]", " ", s)
    s = " ".join(s.split())
    return s, plot_number


def normalize_phone(p: Optional[str]) -> Tuple[str, bool]:
    """Keep digits, return last 8 digits and flag is_central (starts with 1800)."""
    if p is None or pd.isna(p):
        return "", False
    p_str = str(p).strip()
    if p_str.endswith(".0"):
        p_str = p_str[:-2]
    digits = re.sub(r"\D", "", p_str)
    if not digits:
        return "", False
    is_central = digits.startswith("1800")
    last_8 = digits[-8:] if len(digits) >= 8 else digits
    return last_8, is_central


def parse_gps(lat: Any, lon: Any) -> Optional[Tuple[float, float]]:
    """Parse lat/lon coordinates into a float pair or return None if missing/invalid."""
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return None
    try:
        f_lat = float(lat)
        f_lon = float(lon)
        return (f_lat, f_lon)
    except (ValueError, TypeError):
        return None


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived normalized columns to supplier DataFrame."""
    df = df.copy()

    df["norm_city"] = df["city"].apply(canonical_city)
    df["norm_name"] = df["name"].apply(normalize_name)

    addr_res = df["address"].apply(normalize_address)
    df["norm_address"] = [r[0] for r in addr_res]
    df["plot_number"] = [r[1] for r in addr_res]

    phone_res = df["phone"].apply(normalize_phone)
    df["phone_last8"] = [r[0] for r in phone_res]
    df["phone_is_central"] = [r[1] for r in phone_res]

    df["gps"] = [parse_gps(row["lat"], row["lon"]) for _, row in df.iterrows()]

    return df


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "data/dev"
    loaded = load_rows(target_dir)
    prepared = prepare(loaded)
    print(f"Shape: {prepared.shape}")
    print(f"Columns: {list(prepared.columns)}")
