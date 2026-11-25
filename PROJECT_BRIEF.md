# PROJECT_BRIEF.md - StayMerge (Prasunex Innovathon 2026, Round 3)

## One line
Turn messy hotel listings from several suppliers into one clean catalogue, with the best offer for each hotel and a reason for every decision. Wrongly merging two different hotels is worse than missing a duplicate.

## Judge experience (non-negotiable)
- A judge opens the public link with no sign-in and understands the product in under 3 minutes.
- The first screen has one obvious start: 'See the catalogue'.
- Never a blank screen. Every failure shows a readable message and a next step.

## Core workflow (must work end to end)
1. Load three supplier feeds (bundled synthetic Indian hotel data).
2. Clean names, addresses, cities and phones.
3. Pair rows in the same city and score each pair with transparent rules.
4. Sort pairs into match, no match or unsure. Send only unsure pairs to the LLM judge (Groq), with answers cached.
5. Cluster matches into one hotel each, with a safety rule: never put two rows of supplier A, or two rows of supplier C, in one hotel.
6. Build the catalogue: one record per hotel, all supplier offers, and a best offer with a plain-language reason.
7. Show it in a web app: catalogue, hotel detail (why merged, similar hotels kept separate) and an accuracy page.
8. Prove it: score against the hidden answer key with evaluate.py, next to the naive baseline from baseline.py.

## Hard rules
- Code under src/, api/ and web/ never reads answer_key.csv, masters.csv or trap_pairs.csv. Only evaluate.py, baseline.py and src/analysis.py may.
- Every Groq call goes through judge_pair in src/llm_judge.py. No other file imports groq.
- No secrets in code. Keys live in .env (Python) or environment variables (web).
- All thresholds and weights live in src/config.py.
- Results are deterministic: temperature 0, fixed seeds.
- Every function has a pytest test, run before a task is called done.
- The web app talks to the engine only through the FastAPI endpoints.
- Tune on data/dev only. Run data/test once, at the end.

## Tech stack
Python 3.11, pandas, rapidfuzz, Groq API (fast model first, strong model when unsure), SQLite for the LLM cache, FastAPI, Next.js with TypeScript and Tailwind CSS, pytest. Hosting: Vercel (web), Render or Railway (API).

## Out of scope
Login or accounts, billing, live supplier integrations, vector databases, agent frameworks, room-type mapping, sightseeing matching, real personal data.

## Targets (goals, not guarantees)
On data/test: F1 0.88 or more, 2 or fewer of 18 look-alike hotels wrongly merged, hard-row recall 0.70 or more, LLM calls on under 25% of candidate pairs. The naive baseline scores F1 0.69, 8 of 18 wrong merges and hard-row recall 0.30.

## How the agent should work
- Show a short plan before big changes. Do not add features, files or dependencies that the brief does not mention without asking.
- Make the smallest change that meets the prompt. Do not rewrite unrelated files.
- End every task with a test checklist and the results of running it.