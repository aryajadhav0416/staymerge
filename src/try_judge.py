"""Run five hand-written pairs through judge_pair and report decisions and API calls."""
from typing import Any, Dict, List, Tuple
from src import llm_judge

# Five hand-written pairs: two true matches, three look-alikes
HANDWRITTEN_PAIRS: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = [
    (
        "Match 1: Same hotel, minor name difference & slight GPS jitter",
        {
            "name": "Taj Lands End, Mumbai",
            "address": "BJ Road, Bandra West",
            "city": "Mumbai",
            "pincode": "400050",
            "lat": 19.0435,
            "lon": 72.8194,
            "phone": "022-66681234",
            "stars": 5,
        },
        {
            "name": "The Taj Lands End Hotel - Best Price",
            "address": "B.J. Road, Bandra (W)",
            "city": "Mumbai",
            "pincode": "400050",
            "lat": 19.0440,
            "lon": 72.8198,
            "phone": "022-66681234",
            "stars": 5,
        },
    ),
    (
        "Match 2: Same hotel, reordered words and missing pincode",
        {
            "name": "ITC Grand Chola Chennai",
            "address": "63 Mount Road, Guindy",
            "city": "Chennai",
            "pincode": "600032",
            "lat": 13.0105,
            "lon": 80.2207,
            "phone": "044-22200000",
            "stars": 5,
        },
        {
            "name": "Grand Chola ITC Hotel",
            "address": "Mount Rd, Guindy",
            "city": "Chennai",
            "pincode": None,
            "lat": 13.0110,
            "lon": 80.2212,
            "phone": "044-22200000",
            "stars": 5,
        },
    ),
    (
        "Look-alike 1: Same chain sub-brands (Ibis vs Ibis Styles)",
        {
            "name": "Ibis Bengaluru Hosur Road",
            "address": "Plot 24, Hosur Road, Bommanahalli",
            "city": "Bengaluru",
            "pincode": "560068",
            "lat": 12.8980,
            "lon": 77.6320,
            "phone": "080-40001234",
            "stars": 3,
        },
        {
            "name": "Ibis Styles Bengaluru",
            "address": "Plot 24, Hosur Road, Bommanahalli",
            "city": "Bengaluru",
            "pincode": "560068",
            "lat": 12.8982,
            "lon": 77.6322,
            "phone": "080-40001234",
            "stars": 3,
        },
    ),
    (
        "Look-alike 2: Different areas of the same chain in same city",
        {
            "name": "Radisson Blu Marina Connaught Place",
            "address": "G-59 Connaught Circus",
            "city": "Delhi",
            "pincode": "110001",
            "lat": 28.6315,
            "lon": 77.2185,
            "phone": "011-46909000",
            "stars": 5,
        },
        {
            "name": "Radisson Blu Hotel New Delhi Paschim Vihar",
            "address": "Plot No. D, District Centre, Outer Ring Road",
            "city": "Delhi",
            "pincode": "110063",
            "lat": 28.6678,
            "lon": 77.0945,
            "phone": "011-46399999",
            "stars": 5,
        },
    ),
    (
        "Look-alike 3: Different plot numbers and star ratings on same street",
        {
            "name": "Royal Residency Inn",
            "address": "Plot 12, Station Road",
            "city": "Jaipur",
            "pincode": "302001",
            "lat": 26.9190,
            "lon": 75.7950,
            "phone": "0141-2371234",
            "stars": 2,
        },
        {
            "name": "Royal Palace Residency",
            "address": "Plot 88, Station Road",
            "city": "Jaipur",
            "pincode": "302001",
            "lat": 26.9240,
            "lon": 75.8010,
            "phone": "0141-2375678",
            "stars": 4,
        },
    ),
]


def run_try_judge() -> None:
    """Run the 5 pairs through judge_pair and monitor API calls."""
    print("=== Testing Groq LLM Judge with 5 Hand-Written Pairs ===\n")

    for idx, (label, row_a, row_b) in enumerate(HANDWRITTEN_PAIRS, 1):
        calls_before = llm_judge.API_CALL_COUNT
        same, conf, reason = llm_judge.judge_pair(row_a, row_b)
        calls_for_pair = llm_judge.API_CALL_COUNT - calls_before

        print(f"[{idx}/5] {label}")
        print(f"      Decision:   same={same} (confidence: {conf:.2f})")
        print(f"      Reason:     {reason}")
        print(f"      API calls:  {calls_for_pair}\n")

    print(f"Total API calls made across 5 pairs: {llm_judge.API_CALL_COUNT}")


if __name__ == "__main__":
    run_try_judge()
