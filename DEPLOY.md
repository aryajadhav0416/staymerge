# Deployment Guide — StayMerge

This guide covers deploying the FastAPI backend to Render or Railway and the Next.js frontend to Vercel.

---

## 1. Deploy the API (Render or Railway)

- **Root Directory**: Project root (`.`)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**:
  ```bash
  uvicorn api.main:app --host 0.0.0.0 --port $PORT
  ```
- **Environment Variables**:
  - `WEB_ORIGIN`: Set to your deployed Vercel URL (e.g., `https://staymerge.vercel.app`)
  - `DATA_DIR`: Path to the supplier feed directory to serve (e.g., `data/test` or `data/dev`)
  - `USE_MOCK`: Set to `0` to serve real pipeline outputs (or `1` for mock mode)

> [!NOTE]
> Free API hosts (such as Render free tier) sleep after inactivity. Open the API URL (e.g. `/health`) a few minutes before your live demo to wake the service.

---

## 2. Deploy the Web App (Vercel)

- **Root Directory**: `web`
- **Framework Preset**: Next.js
- **Build Command**: `npm run build`
- **Environment Variables**:
  - `NEXT_PUBLIC_API_URL`: Set to your deployed Render/Railway API URL
  - `NEXT_PUBLIC_USE_MOCK`: Set to `0` (off)

---

## 3. Data & Outputs Files Required by the API

`api/main.py` reads from:
- `OUTPUTS_DIR = "outputs"`
- `DATA_DIR = os.getenv("DATA_DIR", "data/dev")`

To serve `/feeds` and `/catalogue` in production **without** exposing `answer_key.csv`, `masters.csv`, or `trap_pairs.csv`, ensure only the following files are committed or copied to the API host:

### `outputs/`
- `outputs/catalogue.json`
- `outputs/decisions.csv`
- `outputs/predictions.csv`
- `outputs/metrics.json`
- `outputs/review_decisions.csv` (optional; created automatically when a review decision is submitted)

### `data/<split>/` (e.g., `data/test/` or `data/dev/`)
- `supplier_a.csv`
- `supplier_b.csv`
- `supplier_c.csv`
- `suppliers.csv`

Do **not** deploy `answer_key.csv`, `masters.csv`, or `trap_pairs.csv` to the API host.

> [!IMPORTANT]
> `.gitignore` currently excludes `outputs/`. Before deploying from Git, you must either force-add the required `outputs/` files (`git add -f outputs/catalogue.json ...`), remove `outputs/` from `.gitignore`, or copy those files into the container/host during your build/deploy step.

