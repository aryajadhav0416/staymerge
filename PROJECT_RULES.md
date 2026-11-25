# Project Rules: hotel-merge (StayMerge)

These rules apply to all development in this project and must be strictly followed in every task:

1. **Answer Key Protection**: Code under `src/`, `api/`, and `web/` must NEVER read `answer_key.csv`, `masters.csv`, or `trap_pairs.csv`. Only `evaluate.py`, `baseline.py`, and `src/analysis.py` may read them.
2. **Centralized LLM Access**: Every Groq call goes through one function, `judge_pair` in `src/llm_judge.py`. No other file imports `groq`.
3. **No Hardcoded Secrets**: Never hardcode secrets. Read them from `.env` (Python) or environment variables (web).
4. **Centralized Configuration**: All thresholds and weights live in `src/config.py`.
5. **Determinism**: Results must be deterministic (temperature 0, fixed seeds).
6. **Test Discipline**: Write or update tests for every function you add, and run them before saying a task is done.
7. **Code Quality**: Keep functions small and add short docstrings.
8. **Decoupled Architecture**: The web app talks to the engine only through the FastAPI endpoints, never through files.

