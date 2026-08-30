# Hackathon iteration log

## Baseline — single-pass lexical review

Why: represent a simple assistant reviewing questionnaire text, a captured row, and transcript text without structured planning or verification.

Result: precision 0.875, recall 0.350, F1 0.500. It missed most cross-source administration and audio issues.

Decision: retain as the reproducible comparison, not as product logic.

## Iteration 1 — restore deterministic engine

Why: the inherited repository had a strong dashboard/database layer, but a clean checkout lacked the referenced `core`, `checks`, and job-store modules and did not mount the frontend's upload/QC/AI routes.

Result: restored objective checks, async jobs, reports, EDA, compare, interviewer risk, and AI endpoints. Existing backend suite returned to green: 108/108 at this stage.

Decision: keep. Numeric/routing facts should not consume LLM calls.

## Iteration 2 — structured questionnaire + data semantics

Result: precision 1.000, recall 0.350, F1 0.519. Precision improved, but data alone could not reveal what was actually said or asked.

Decision: keep as one evidence stream; insufficient as the final system.

## Iteration 3 — multimodal alignment and broad detector

Result: precision 0.909, recall 1.000, F1 0.952. Recall rose sharply, but two clean paraphrases became false-positive candidates.

Decision: keep the recall-biased detector and add a separate evidence threshold.

## Iteration 4 — independent verifier

Result: the verifier rejected both broad-detector false positives. Final precision 1.000, recall 1.000, F1 1.000 on the submitted 20 cases.

Decision: keep. The verifier sees original evidence and the claim, not hidden detector reasoning.

## Iteration 5 — human checkpoint and evidence report

Result: three-way verdicts, reviewer decisions, timestamp evidence, full rule spec, and Excel export are now in the end-to-end UI.

Decision: keep. No finding triggers an external action.

## Hot take supported by the experiment

More agents were not the key improvement. **Asymmetric evidence thresholds were.** The recall-biased detector found every benchmark issue but created two false positives. A separately calibrated verifier removed them. An extra agent with the same context and threshold would have added latency without changing the decision boundary.
