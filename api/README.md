# StayMerge API

FastAPI backend service serving the deduplicated hotel catalogue, matching decisions, accuracy metrics, and raw supplier feeds.

## Run Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start API Server
Using `uvicorn`:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Or from Python:
```bash
python -m uvicorn api.main:app --port 8000
```

### 3. Environment Variables
- `WEB_ORIGIN`: Allowed CORS origin for frontend (default: `http://localhost:3000`).
- `USE_MOCK`: Set to `1` to serve example mock responses without requiring pipeline outputs.
- `DATA_DIR`: Path to raw supplier CSV feeds (default: `data/dev`).

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status |
| `GET` | `/hotels` | List master hotels with best offers and supplier options (supports `city` and `q` search) |
| `GET` | `/hotels/{id}` | Detail of a master hotel including similar look-alike hotels kept separate |
| `GET` | `/decisions` | All candidate pair decisions with transparent scoring explanations |
| `GET` | `/metrics` | Matcher accuracy metrics (F1, precision, recall, trap false merges) |
| `GET` | `/feeds` | Raw supplier feed statistics and reliability |
| `POST` | `/reviews` | Record human review feedback (`merge` / `split`) to `outputs/review_decisions.csv` |

## Interactive Docs
When the server is running, visit:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

