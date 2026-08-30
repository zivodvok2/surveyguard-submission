# Trajectory Examples

Three representative examples from the SurveyGuard evaluation runs, illustrating different aspects of the agentic pipeline.

## Where the full data lives

- `evaluation/trajectories.json` — full verified-finding trajectories for cases 01–05 from the main eval run
- `evaluation/results/main_eval.json` — per-case predictions and aggregate metrics for all 20 main-eval cases
- `evaluation/results/generalization_eval.json` — same for the 10 generalization cases

## The three examples

### example_a_clean_detection.json

**Case 18 — clean, exact detection (0 FP, 0 FN)**

The system receives an interview with two genuine issues (off_topic_verbatim and verbatim_audio_mismatch) and finds exactly those two. No false positives, no misses. The baseline on this case flags different issues with incorrect question IDs; the data-only stage finds one of the two; the full pipeline finds both. Illustrates the system operating at its best: multi-stage analysis eliminating the noise the baseline introduces.

Source: `evaluation/results/main_eval.json`, case18. Full verifier reasoning is in `evaluation/trajectories.json` for cases 01–05 only.

### example_b_end_to_end_detection.json

**Case 03 — real issues detected end-to-end through every pipeline stage**

The transcript is aligned to two questionnaire questions (Q1 at similarity 1.0, Q1A at 0.69). The detector raises audio_data_mismatch (respondent said "decreased", captured value is code 1 = Increase) and verbatim_contradicts_audio (captured verbatim says production increased, spoken answer says demand was lower; semantic similarity 0.30, opposite directions). The verifier independently confirms both with evidence-grounded reasoning. A third candidate (insufficient_probing on Q1A) is also confirmed — it is a false positive in this case, showing the verifier's recall-biased posture.

Source: `evaluation/trajectories.json`, case03 (index 2).

### example_c_verifier_evaluation.json

**Case 05 — verifier evaluating two candidates from different detection pathways**

The detector raises an invalid_code finding (deterministic: value 9 not in allowed codes {1, 2, 3}) and an insufficient_probing finding (LLM-based: 2-word answer after a PROBE FULLY instruction). The verifier evaluates each independently, confirming both with different reasoning chains: for the deterministic finding it validates the code-lookup result; for the LLM finding it assesses answer length against the questionnaire instruction. No findings are rejected in any of the five sampled trajectories — consistent with the recall-biased detector design (FP=16, FN=0 in the main eval).

Source: `evaluation/trajectories.json`, case05 (index 4).
