# Five-minute demo script

## 0:00–0:35 — Problem

“Survey QC is not only checking whether a code is valid. The questionnaire may say code 1 means increase while the respondent clearly says decrease. A QC analyst currently compares the questionnaire, dataset, and recording manually.”

## 0:35–1:15 — Inputs

Open **Agentic Audit**. Upload the three files in `demo/`. Explain that JSON is a timestamped completed-interview transcript so the demo is reproducible without a key; real audio uses Whisper through the same contract.

## 1:15–2:20 — Run and trajectory

Click **Run multimodal audit**. Point to rule extraction, deterministic checks, transcription evidence, question alignment, independent verification, and report assembly. Mention transcription is a tool rather than an unnecessary agent.

## 2:20–3:35 — Evidence

Open the confirmed Q1 audio–data mismatch. Show code `1 = Increase`, captured value `1`, timestamped spoken decrease, and verifier reason. Open a review-only finding and explain why it is not an automatic failure. Save a reviewer decision.

## 3:35–4:15 — Export

Export the Excel report and show Summary, Findings, Transcript evidence, and Questionnaire rules.

## 4:15–4:50 — Measured result

Show the README table: baseline F1 0.500; data-only 0.519; multimodal without verifier 0.952 with two false positives; final 1.000 with zero false positives. State this is a scoped synthetic benchmark.

## 4:50–5:00 — Insight

“The main lesson was not that more agents are better. A broad detector and an independently calibrated verifier were better. Different evidence thresholds mattered more than agent count.”
