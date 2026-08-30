# micro1 Agentic Workflows Hackathon submission

## Project

**SurveyGuard — Agentic multimodal survey quality control**

## User and bottleneck

Research data-quality analysts must interpret a questionnaire, inspect captured survey data, and manually listen to completed recordings. The evidence is fragmented, semantic contradictions pass ordinary range checks, and manual listening does not scale.

## Solution

SurveyGuard creates a structured rule specification from the questionnaire, delegates objective checks to Python, aligns completed recordings to questions, then uses LLM calls (minimax/minimax-m3:free via OpenRouter) to classify direction/leading-question/vague-answer from audio transcripts and to independently verify each candidate finding before surfacing it.

## Component design — LLM vs deterministic

| Component | Implementation | Reason |
|---|---|---|
| Questionnaire parser | Deterministic (regex) | Questionnaire format is controlled structure |
| Alignment (timestamps) | Deterministic (token overlap + SequenceMatcher) | Matching question text to audio is a recall task with a fixed reference string |
| Data QC — invalid code, range, missing | Deterministic (lookup) | Code validity is exact by definition |
| Data QC — verbatim direction vs code | Hybrid: deterministic fast path (exact DIRECTION_WORDS match) + LLM fallback (synonyms like "plummeted", "contracted") | Code labels are controlled vocabulary — exact matching covers the common case; LLM fallback handles natural-language synonyms that keyword lists miss |
| Audio direction classification | **LLM (minimax/minimax-m3:free via OpenRouter)** | Natural speech uses synonyms ("shot up", "climbed", "plummeted") that keyword lists miss |
| Leading-question detection | **LLM (minimax/minimax-m3:free via OpenRouter)** | Identifying assumptive framing requires language understanding, not keyword lookup |
| Vague-answer detection | **LLM (minimax/minimax-m3:free via OpenRouter)** | Insufficient probing requires semantic judgment ("various factors", "hard to say") |
| Independent verification | **LLM (minimax/minimax-m3:free via OpenRouter)** | Deciding whether evidence supports a claim requires reasoning, not threshold comparison |
| Baseline (evaluation only) | **LLM (minimax/minimax-m3:free via OpenRouter)** | Fair comparison: single prompt, no rule spec, no verifier |
| Transcription | Tool (Groq Whisper) | Deterministic conversion — not reasoning |
| Report assembly | Deterministic | Evidence collection, formatting |

## Measured improvement — real numbers from `python -m evaluation.run_eval`

All numbers below use **minimax/minimax-m3:free via OpenRouter** (OPENROUTER_API_KEY required) for both baseline and final in both eval runs — a single `MODEL` constant in `agentic/llm_client.py` is shared by every call site (`baseline_predict`, `detector.py`, `verifier.py`), so there is no per-component model variation. Groq's free-tier daily token limit was exhausted during evaluation, so OpenRouter was used for the final reported run; both are free-tier options and the same prompts/logic were used throughout. Run the commands yourself to reproduce exactly.

### Main evaluation set (20 cases, `cases.py`)

| Metric | Baseline (single LLM prompt, no scaffolding) | Final (SurveyGuard) |
|---|---|---|
| F1 | **0.1923** | **0.7143** |
| Precision | 0.1562 | 0.5556 |
| Recall | 0.2500 | 1.0000 |
| TP / FP / FN | 5 / 27 / 15 | 20 / 16 / 0 |
| Audio review seconds | 491.0 (full recordings) | 375.0 (flag windows only) |
| Review reduction | — | 23.6% |

### Generalization set (10 new cases, `generalization_cases.py`)

This test deliberately uses different synonyms, different leading-question phrasings, and
different vague-answer phrasings than anything in `cases.py`. No tuning was done against
this file after seeing results.

| Metric | Baseline (single LLM prompt, no scaffolding) | Final (SurveyGuard) |
|---|---|---|
| F1 | **0.3226** | **0.6452** |
| Precision | 0.2500 | 0.5000 |
| Recall | 0.4545 | 0.9091 |
| TP / FP / FN | 5 / 15 / 6 | 10 / 10 / 1 |
| Audio review seconds | 227.0 (full recordings) | 178.0 (flag windows only) |
| Review reduction | — | 21.6% |

**The generalization final F1 (0.6452) is slightly below the main eval F1 (0.7143).**
The drop comes primarily from precision: the system catches nearly all issues (recall 0.9091,
FN=1) but over-flags on novel phrasings (FP=10 vs FP=16 at twice the case count). The most
deterministic issue categories (question_not_detected, consent_not_detected) generalize
cleanly; the LLM-based issue categories (verbatim_audio_mismatch, insufficient_probing)
produce more false positives on unseen phrasing variants.

## Reproducibility

```bash
# Install
pip install -r requirements.txt

# Run main evaluation (requires OPENROUTER_API_KEY)
OPENROUTER_API_KEY=your_key python -m evaluation.run_eval

# Run generalization test (requires OPENROUTER_API_KEY)
OPENROUTER_API_KEY=your_key python -m evaluation.run_eval --generalization

# Run test suite (does not require OPENROUTER_API_KEY for the non-LLM tests)
BOOTSTRAP_ADMIN_PASSWORD=your_pw pytest tests/

# Run API server
OPENROUTER_API_KEY=your_key BOOTSTRAP_ADMIN_PASSWORD=your_pw uvicorn api:app

# Docker
docker build -t surveyguard .
docker run --rm -p 8000:8000 \
  -e OPENROUTER_API_KEY=... \
  -e BOOTSTRAP_ADMIN_PASSWORD=... \
  surveyguard
```

Use the three files in `demo/`. No audio file required for the eval — transcripts are
provided as JSON.

## Insight

Agent count is a poor proxy for reliability. The measurable gain over the baseline (F1
0.1923 → 0.7143 on the main eval) came from **structured multi-stage analysis with an
independent verifier** rather than a single prompt. The generalization result (F1 0.6452
on 10 held-out novel cases, vs baseline 0.3226) confirms the gain is not specific to the
training-adjacent cases: recall remains high (0.9091) and the remaining gap is in
precision, reflecting over-flagging on novel issue-category phrasings rather than a
fundamental structural failure.
