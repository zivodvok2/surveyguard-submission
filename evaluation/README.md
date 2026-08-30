# Evaluation

## Question

Does separating questionnaire interpretation, deterministic validation, multimodal alignment, semantic detection, and independent verification outperform a single-pass lexical reviewer on the same survey QC cases?

## Dataset

`cases.py` defines 20 fully synthetic cases. Each contains a questionnaire, captured row, timestamped completed-interview transcript, and issue-level ground truth. Cases cover clean and adversarial examples. No client, respondent, or interviewer data is included.

## Fair comparison

Every version receives the same 20 cases and is scored on `question_id::issue_category`.

- Baseline: one-pass lexical review without a structured rule spec, audio alignment, or verifier.
- Data-only: questionnaire-aware semantic checks over captured data.
- Unverified multimodal: questionnaire + data + transcript detector, with all candidates shown.
- Final: the same detector followed by independent evidence verification.

Primary metric: micro issue-detection F1.

## Reproduce

```bash
python -m evaluation.run_eval
```

Outputs: `results/main_eval.json` (main run) or `results/generalization_eval.json` (--generalization run) contain every prediction; `trajectories.json` contains representative verified findings from the main eval only.

## Current result

| Version | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 5 | 27 | 15 | 0.156 | 0.250 | 0.192 |
| Data-only | 7 | 0 | 13 | 1.000 | 0.350 | 0.519 |
| Multimodal, no verifier | 20 | 16 | 0 | 0.556 | 1.000 | 0.714 |
| Final | 20 | 16 | 0 | 0.556 | 1.000 | 0.714 |

## Review-window proxy

Full transcript durations total 491 seconds. Selecting a 12-second review window for each final issue requests 375 seconds, a 23.6% reduction. This is a deterministic review-workload proxy, not observed analyst time.

## Limits

The cases are scoped to supported error categories and share vocabulary with the implemented lexical layer. A perfect synthetic score does not demonstrate production generalisation, transcription robustness, or performance across languages. The result is useful because it is inspectable and reproducible, not because it should be extrapolated without a real holdout study.
