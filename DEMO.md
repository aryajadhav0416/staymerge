# StayMerge — 4-Minute Demo Script

## Order of Pages
1. **Home (`/`)** — 0:00 to 0:45
2. **Catalogue (`/catalogue`)** — 0:45 to 1:30
3. **Hotel Detail (`/hotels/[id]`)** — 1:30 to 2:30
4. **Review Queue (`/review`)** — 2:30 to 3:15
5. **Accuracy (`/accuracy`)** — 3:15 to 4:00

---

## Click-by-Click Script

### 1. Home (`/`) — 0:00 to 0:45
- **Click**: Open `/` in the browser.
- **Say**:
  > "This is StayMerge. Hotel aggregators get messy, duplicated feeds from multiple suppliers—missing pincodes, typos, and jittered GPS—and naive matchers either miss duplicates or wrongly merge look-alike hotels. StayMerge cleans, scores, routes only the unsure 3.2% of pairs to an LLM judge, and publishes one clean catalogue with a reason for every decision."
- **Click**: Point to the before-and-after strip and headline numbers, then click **Open the catalogue**.

### 2. Catalogue (`/catalogue`) — 0:45 to 1:30
- **Click**: Show the grid of merged hotels. Use the **City** filter or **Search** box, and point out the **Best Value** badge on a card.
- **Say**:
  > "Here is the deduplicated master catalogue. Each card consolidates multiple supplier offers and highlights the best-value offer—balancing price, cancellation policy, payment terms, and supplier reliability."
- **Click**: Click any hotel card with multiple offers to open `/hotels/[id]`.

### 3. Hotel Detail (`/hotels/[id]`) — 1:30 to 2:30
- **Click**: Scroll through:
  1. **Offers Table** (sorted by value score, best row highlighted).
  2. **Why these listings were merged** (raw messy supplier names, rule score band, and LLM reasoning).
  3. **Similar hotels kept separate** (look-alike properties that were NOT merged).
- **Say**:
  > "On the hotel page, you can see every supplier offer ranked by value score. Below that, we show the exact messy raw listings and why they were merged—including the rule score band and the LLM's explanation. And at the bottom, we show look-alike hotels in the same city that were intentionally kept separate."

### 4. Review Queue (`/review`) — 2:30 to 3:15
- **Click**: Click **Review** in the top navigation bar.
- **Click**: Show a pair in **Pending**, point out the highlighted differing fields, and click **Approve Merge** or **Reject**. Switch to the **Decided** tab.
- **Say**:
  > "For borderline pairs, operators can inspect the two listings side-by-side with differing fields highlighted, review the rule score and LLM verdict, and approve or reject the merge. Decisions persist across refreshes."

### 5. Accuracy (`/accuracy`) — 3:15 to 4:00
- **Click**: Click **Accuracy** in the top navigation bar.
- **Say**:
  > "Finally, on the Accuracy page, we compare StayMerge against three naive baselines on the frozen synthetic test set of 771 listings. Fuzzy name plus GPS scores 0.69 F1 and wrongly merges 8 of 18 look-alike trap pairs. StayMerge achieves 0.977 F1, 0.886 hard-row recall, and 0 of 18 wrong merges—while sending only 3.2% of pairs to the LLM."

---

## Fallback Plan (If Live Site Is Slow)

1. **Local Run**: Start the backend (`uvicorn api.main:app --port 8000`) and frontend (`cd web && npm run dev`) locally before the session.
2. **Recorded Video**: Keep a pre-recorded 4-minute walkthrough video ready to play if network or API cold-start delays occur.

---

## 5 Likely Judge Questions & Honest Answers

1. **Q: Why is the benchmark synthetic?**
   **A**: Real OTA supplier contracts and guest-facing feeds are proprietary. The synthetic Indian hotel dataset lets us inject controlled typos, missing fields, and 18 look-alike trap pairs to measure precision and recall against a known answer key.
2. **Q: Do human review decisions automatically re-cluster the catalogue?**
   **A**: Not automatically—decisions are persisted to `outputs/review_decisions.csv` for audit and UI state, and re-clustering requires re-running the clustering step.
3. **Q: What happens if the Groq API is down or rate-limited?**
   **A**: All previous LLM judgements are cached in SQLite (`outputs/llm_cache.db`). For uncached pairs, the engine falls back to deterministic rule thresholds.
4. **Q: How do you prevent two different hotels in the same chain from merging?**
   **A**: We combine negative rule weights for mismatched plot numbers, pincodes, or far GPS with a strict supplier-exclusivity constraint during Union-Find clustering (never merging two rows from Supplier A or two from Supplier C).
5. **Q: Why did the test run take ~618 seconds?**
   **A**: Most of that time is live Groq API latency across the 172 uncached `unsure` pairs; the remaining 448 `unsure` pairs hit the SQLite cache.

