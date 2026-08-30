from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .alignment import answer_after, text_similarity, tokens
from .llm_client import call_llm
from .models import Alignment, CandidateFinding, QuestionSpec, TranscriptSegment


# --- Deterministic helpers (used by data_qc.py for structured-code comparison) ---
# Deterministic-by-design: code labels are controlled vocabulary from the
# questionnaire spec, so keyword matching is exact and appropriate here.

DIRECTION_WORDS = {
    "increase": {"increase", "increased", "increasing", "rise", "rose", "rising", "grew", "growth", "higher", "up", "expanded", "more"},
    "decrease": {"decrease", "decreased", "decreasing", "fall", "fell", "falling", "decline", "declined", "lower", "down", "reduced", "less"},
    "same": {"same", "unchanged", "stable", "constant", "steady", "equal", "maintained"},
}


def direction(text: str) -> str | None:
    # Fast deterministic path — exact DIRECTION_WORDS match on controlled
    # vocabulary (code labels like "Increase", "Remain unchanged") and clear
    # common words.  Returns immediately when exactly one label matches, which
    # covers the vast majority of coded-value calls from coded_direction().
    found = []
    word_set = tokens(text) | set(re.findall(r"[a-z]+", text.lower()))
    for label, words in DIRECTION_WORDS.items():
        if word_set & words:
            found.append(label)
    if len(found) == 1:
        return found[0]

    # LLM-based-because-it-needs-language-understanding: synonyms like
    # "plummeted", "shot up", "contracted", "stayed flat" fall through here.
    # Uses the same Groq wrapper as the rest of the pipeline.
    try:
        prompt = (
            "Classify the direction expressed in the following text.\n"
            "Reply with exactly one word — increase, decrease, same, or unclear — "
            "and nothing else.\n\n"
            f"Text: {text}"
        )
        raw = call_llm(prompt, max_tokens=16, expect_json=False).lower()
        label = raw.split()[0] if raw.split() else "unclear"
        return label if label in {"increase", "decrease", "same"} else None
    except Exception:
        return None


def coded_direction(question: QuestionSpec, value: Any) -> str | None:
    # Deterministic-by-design: translates a numeric survey code to its label
    # string, then uses the keyword matcher above on that controlled label.
    if value is None or not question.codes:
        return None
    raw = str(value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    label = question.codes.get(raw, raw)
    return direction(label)


# --- LLM-based audio analysis ---
# LLM-based-because-it-needs-language-understanding: natural speech uses
# synonyms, hedges, and rhetorical structures that keyword lists miss.

def _llm_classify_audio(question_text: str, audio_question: str, spoken_answer: str, probe: bool) -> dict[str, Any]:
    """Call claude-sonnet-4-6 to classify direction, leading-question, and vague-answer
    from raw audio transcript text.  Returns a dict with keys:
      direction (str|None): "increase" | "decrease" | "same" | null
      is_leading_question (bool)
      is_vague_answer (bool)
    Falls back to empty-signal defaults if the API key is absent or the call fails.
    """
    try:
        prompt = (
            f"You are a survey quality-control auditor reviewing a recorded interview.\n\n"
            f"Survey question: {question_text}\n"
            f"Interviewer said: {audio_question}\n"
            f"Respondent said: {spoken_answer}\n"
            f"This question requires follow-up probing: {probe}\n\n"
            "Respond with a JSON object and nothing else:\n"
            "{\n"
            '  "direction": "increase" | "decrease" | "same" | null,\n'
            '  "is_leading_question": true | false,\n'
            '  "is_vague_answer": true | false\n'
            "}\n\n"
            "Rules:\n"
            '- "direction": the directional trend in the respondent\'s spoken answer '
            "(increase/decrease/same); null if unclear or not applicable.\n"
            '- "is_leading_question": true if the interviewer\'s wording suggests the '
            "expected answer (tag questions, implied answers, assumptive framing).\n"
            '- "is_vague_answer": true if the respondent\'s answer is too short or '
            "uninformative to represent a genuine response (single words unrelated to "
            "the question, \"don't know\", \"various reasons\", etc.)."
        )
        raw = call_llm(prompt, max_tokens=256, expect_json=True)
        result = json.loads(raw)
        return {
            "direction": result.get("direction"),
            "is_leading_question": bool(result.get("is_leading_question", False)),
            "is_vague_answer": bool(result.get("is_vague_answer", False)),
        }
    except Exception:
        # Any failure (network, JSON parse, etc.) is silent — caller treats
        # missing signal as "no issue found" which is the safe direction.
        return {"direction": None, "is_leading_question": False, "is_vague_answer": False}


def _finding_id(respondent_id: str, question_id: str | None, category: str) -> str:
    value = f"{respondent_id}|{question_id or '-'}|{category}".encode()
    return hashlib.sha256(value).hexdigest()[:16]


def _candidate(respondent_id: str, question_id: str | None, category: str, severity: str, claim: str, evidence: dict[str, Any], confidence: float) -> CandidateFinding:
    return CandidateFinding(finding_id=_finding_id(respondent_id, question_id, category), respondent_id=respondent_id, question_id=question_id, category=category, severity=severity, claim=claim, evidence=evidence, detector_confidence=round(confidence, 3))


def detect_interview_issues(respondent_id: str, questions: list[QuestionSpec], transcript: list[TranscriptSegment], alignments: list[Alignment], row: dict[str, Any], column_mapping: dict[str, Any], technical: dict[str, Any]) -> list[CandidateFinding]:
    findings: list[CandidateFinding] = []
    if technical.get("status") == "unreadable":
        findings.append(_candidate(respondent_id, None, "audio_unreadable", "critical", "The recording could not be read", technical, 0.99))
    elif technical.get("duration_seconds") is not None and float(technical["duration_seconds"]) < 10:
        findings.append(_candidate(respondent_id, None, "recording_too_short", "warning", "The recording is unusually short", technical, 0.88))

    alignment_by_id = {alignment.question_id: alignment for alignment in alignments}
    question_map = column_mapping.get("questions", {}) if isinstance(column_mapping.get("questions"), dict) else {}
    for question in questions:
        alignment = alignment_by_id[question.question_id]
        evidence = {"expected_question": question.text, "audio_question": alignment.transcript, "similarity": alignment.score, "timestamp": {"start": alignment.start, "end": alignment.end}}
        # Detector is intentionally recall-biased; the verifier applies a
        # stricter evidentiary threshold and can reject plausible paraphrases.
        if alignment.score < 0.38:
            severity = "critical" if question.consent else "warning"
            category = "consent_not_detected" if question.consent else "question_not_detected"
            findings.append(_candidate(respondent_id, question.question_id, category, severity, f"{question.question_id} was not reliably detected in the recording", evidence, 1 - alignment.score))
            continue
        if question.read_exactly and alignment.score < 0.70:
            findings.append(_candidate(respondent_id, question.question_id, "required_wording_changed", "warning", "Required question wording may have been changed", evidence, 0.75 - alignment.score / 2))

        answer_segments = answer_after(alignment, transcript)
        spoken_answer = " ".join(segment.text for segment in answer_segments).strip()

        # LLM-based classification of direction, leading question, and vague answer
        # from the audio transcript — language understanding required here.
        llm = _llm_classify_audio(question.text, alignment.transcript, spoken_answer, question.probe)

        if llm["is_leading_question"]:
            findings.append(_candidate(respondent_id, question.question_id, "possible_leading_question", "warning", "The interviewer may have led or inferred the response", evidence, 0.76))

        configured = question_map.get(question.question_id, {}) if isinstance(question_map.get(question.question_id), dict) else {}
        value_column = configured.get("value") or (question.variable if question.variable in row else question.question_id if question.question_id in row else None)
        verbatim_column = configured.get("verbatim") or (question.reason_variable if question.reason_variable in row else None)
        captured_value = row.get(value_column) if value_column else None

        # LLM-classified spoken direction vs deterministic coded direction
        spoken_direction = llm["direction"]
        expected_direction = coded_direction(question, captured_value)
        if spoken_direction and expected_direction and spoken_direction != expected_direction:
            findings.append(_candidate(respondent_id, question.question_id, "audio_data_mismatch", "critical", "The spoken answer conflicts with the captured survey value", {**evidence, "spoken_answer": spoken_answer, "spoken_direction": spoken_direction, "captured_column": value_column, "captured_value": captured_value, "captured_direction": expected_direction}, 0.97))

        captured_verbatim = str(row.get(verbatim_column, "") or "").strip() if verbatim_column else ""
        verbatim_audio = spoken_answer
        if question.reason_variable and question.reason_variable in alignment_by_id:
            reason_alignment = alignment_by_id[question.reason_variable]
            reason_segments = answer_after(reason_alignment, transcript)
            if reason_segments:
                verbatim_audio = " ".join(segment.text for segment in reason_segments).strip()
        if captured_verbatim and spoken_answer:
            semantic_score = text_similarity(captured_verbatim, verbatim_audio)
            verbatim_direction = direction(captured_verbatim)
            audio_verbatim_direction = direction(verbatim_audio)
            if verbatim_direction and audio_verbatim_direction and verbatim_direction != audio_verbatim_direction:
                findings.append(_candidate(respondent_id, question.question_id, "verbatim_contradicts_audio", "critical", "The captured verbatim reverses the meaning of the spoken answer", {**evidence, "spoken_answer": verbatim_audio, "captured_verbatim": captured_verbatim, "verbatim_column": verbatim_column, "semantic_similarity": semantic_score, "spoken_direction": audio_verbatim_direction, "verbatim_direction": verbatim_direction}, 0.97))
            elif len(captured_verbatim.split()) >= 4 and len(verbatim_audio.split()) >= 4 and semantic_score < 0.30:
                findings.append(_candidate(respondent_id, question.question_id, "verbatim_audio_mismatch", "warning", "The captured verbatim may not represent the respondent's spoken explanation", {**evidence, "spoken_answer": verbatim_audio, "captured_verbatim": captured_verbatim, "verbatim_column": verbatim_column, "semantic_similarity": semantic_score}, 0.72))

        if question.probe and llm["is_vague_answer"]:
            findings.append(_candidate(respondent_id, question.question_id, "insufficient_probing", "warning", "The open-ended response may not have been probed sufficiently", {**evidence, "spoken_answer": spoken_answer, "answer_word_count": len(spoken_answer.split())}, 0.7))
    return findings
