# Reproduction guide

Step-by-step instructions to reproduce the evaluation results from a fresh clone. Tested on Python 3.11+.

## Prerequisites

- Python 3.11 or later
- An `OPENROUTER_API_KEY` with access to `minimax/minimax-m3:free` (free tier). Sign up at openrouter.ai.
- No other keys are required for the evaluation. `GROQ_API_KEY` is accepted as a fallback but OpenRouter is the recommended path.

## 1. Clone

```bash
git clone https://github.com/zivodvok2/surveyguard-submission.git
cd surveyguard-submission
```

## 2. Create a virtual environment and install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` includes all runtime and test dependencies. No separate install step is needed for the evaluation harness.

## 3. Run the test suite

```bash
BOOTSTRAP_ADMIN_PASSWORD=any_password pytest tests/ -q
```

`BOOTSTRAP_ADMIN_PASSWORD` can be any non-empty string for the test run; it seeds the local test database admin account. Expected: 110 passed, 2 skipped (the skipped tests require a live database connection beyond sqlite).

## 4. Run the main evaluation

```bash
OPENROUTER_API_KEY=your_key python -m evaluation.run_eval
```

This runs 20 synthetic cases through the full pipeline (baseline → data-only → multimodal detector → verifier) and writes results to `evaluation/results/main_eval.json`. The run takes roughly 5–10 minutes on the free tier due to rate-limit back-off. Output is printed to stdout at completion.

Committed result (F1, committed JSON):

| Version | Precision | Recall | F1 |
|---|---:|---:|---:|
| Baseline | 0.156 | 0.250 | 0.192 |
| Dataset-only | 1.000 | 0.350 | 0.519 |
| Multimodal, no verifier | 0.556 | 1.000 | 0.714 |
| Final (SurveyGuard) | 0.556 | 1.000 | **0.714** |

LLM non-determinism means exact numbers will vary slightly between runs. The final F1 should be in the range 0.68–0.73; the main claim (large improvement over the 0.19 baseline) should hold.

## 5. Run the generalization evaluation

```bash
OPENROUTER_API_KEY=your_key python -m evaluation.run_eval --generalization
```

Runs 10 held-out cases with novel phrasing not present in `cases.py`. Writes to `evaluation/results/generalization_eval.json`.

Committed result:

| Version | Precision | Recall | F1 |
|---|---:|---:|---:|
| Baseline | 0.250 | 0.455 | 0.323 |
| Final (SurveyGuard) | 0.500 | 0.909 | **0.645** |

## 6. Inspect trajectories

`evaluation/trajectories.json` contains full verified-finding trajectories for a representative sample of cases from the main eval. See `docs/trajectory_examples/` for annotated examples and `evaluation/results/main_eval.json` for per-case predictions across all 20 cases.

## Notes

- No audio files are required. The evaluation uses pre-supplied JSON transcripts.
- Model and API key are never written to result files or trajectories.
- The same `OPENROUTER_API_KEY` and model (`minimax/minimax-m3:free`) are used for baseline and final, so the comparison is fair.
