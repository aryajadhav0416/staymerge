# StayMerge Web Frontend

The Next.js web application for **StayMerge** (Prasunex Innovathon 2026, Round 3). It communicates exclusively with the FastAPI backend over HTTP to display supplier listings, master hotel catalogues, deduplication decisions, human review workflows, and benchmark metrics.

---

## 1. Tech Stack

- **Framework**: Next.js 14 (App Router, React 18, TypeScript)
- **Styling**: Tailwind CSS with custom design tokens (Teal primary accent, neutral slate greys, 8-pixel spacing, rounded cards)
- **Icons**: Lucide React
- **Testing**: Vitest, React Testing Library, jsdom
- **Accessibility**: WCAG 2.1 AA compliant, visible focus rings, high-contrast badges, keyboard skip-link, and ARIA labels

---

## 2. Environment Variables

Create `.env.local` in `web/` or provide environment variables at runtime:

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend service |
| `NEXT_PUBLIC_USE_MOCK` | `0` (off) | Set to `1` to run in mock mode using bundled JSON mock fixtures in `web/mock/` |

---

## 3. Setup and Run Scripts

Run from the `web/` directory:

```bash
# 1. Install dependencies
npm install

# 2. Run local development server (http://localhost:3000)
npm run dev

# 3. Type-check with TypeScript compiler
npx tsc --noEmit

# 4. Run ESLint
npm run lint

# 5. Run test suite (Vitest + React Testing Library)
npm test

# 6. Build optimized production bundle
npm run build

# 7. Start production server
npm run start
```

---

## 4. Pages and Routes

| Route | Page | Description |
|---|---|---|
| `/` | **Home** | Product hero, interactive before-and-after strip, 3 headline metrics (F1, 0 trap merges, LLM call rate), and 4-step pipeline overview. |
| `/feeds` | **Supplier Feeds** | Side-by-side feed inspection across 3 suppliers (A, B, C) with search, supplier filters, pagination, and subtle missing value dashes. |
| `/catalogue` | **Hotel Catalogue** | Consolidated hotel cards with star ratings, supplier count, best offer badge with value reasoning, filters (city, stars), and sorting. |
| `/hotels/[id]` | **Hotel Detail** | Full hotel dossier: consolidated offers table sorted by value score, why listings were merged with score bands & LLM reasons, and similar hotels kept separate. |
| `/review` | **Review Queue** | Human-in-the-loop review queue for unsure pairs with side-by-side diff highlighting, Approve/Reject action buttons, and localStorage persistence. |
| `/accuracy` | **Accuracy & Benchmark** | Comprehensive evaluation table against naive baselines with target notes, SVG F1 bar chart, dev/test toggle, and synthetic benchmark disclaimer. |
| `404` | **Custom 404** | Accessible fallback page with quick links back to Home and the Hotel Catalogue. |

---

## 5. Architecture & Hard Rules

- **Zero Direct Data File Access**: The web application never reads CSVs or outputs directly from disk; it consumes only JSON from the FastAPI backend or local mock files when `NEXT_PUBLIC_USE_MOCK=1`.
- **Typed API Client**: All endpoints go through `web/lib/api.ts` with explicit TypeScript return types matching backend schemas.
- **Graceful States**: Every page contains three distinct states: Loading (skeleton placeholders), Empty state with guidance, and Error state with an active Retry button.

