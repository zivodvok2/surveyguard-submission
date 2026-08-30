from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from .alignment import tokens
from .detector import coded_direction, direction
from .models import CandidateFinding, QuestionSpec


TOPIC_NOISE = {"answer", "change", "changed", "compared", "decrease", "decreased", "explain", "increase", "increased", "last", "month", "no", "reason", "remain", "same", "say", "unchanged"}


def _id(respondent: str, question: str, category: str) -> str:
    return hashlib.sha256(f"data|{respondent}|{question}|{category}".encode()).hexdigest()[:16]


def semantic_data_findings(frame: pd.DataFrame, questions: list[QuestionSpec], mapping: dict[str, Any], respondent_column: str | None) -> list[CandidateFinding]:
    findings: list[CandidateFinding] = []
    question_map = mapping.get("questions", {}) if isinstance(mapping.get("questions"), dict) else {}
    for row_index, row in frame.iterrows():
        respondent = str(row.get(respondent_column, row_index + 1)) if respondent_column else str(row_index + 1)
        row_dict = row.to_dict()
        for question in questions:
            configured = question_map.get(question.question_id, {}) if isinstance(question_map.get(question.question_id), dict) else {}
            value_column = configured.get("value") or (question.variable if question.variable in frame.columns else question.question_id if question.question_id in frame.columns else None)
            verbatim_column = configured.get("verbatim") or (question.reason_variable if question.reason_variable in frame.columns else None)
            if not value_column:
                continue
            captured = row_dict.get(value_column)
            raw_code = str(captured).strip()
            if raw_code.endswith(".0"):
                raw_code = raw_code[:-2]
            if question.codes and pd.notna(captured) and raw_code not in question.codes:
                findings.append(CandidateFinding(finding_id=_id(respondent, question.question_id, "invalid_code"), respondent_id=respondent, question_id=question.question_id, category="invalid_code", severity="critical", claim="Captured value is not a valid questionnaire code", evidence={"column": value_column, "captured_value": captured, "allowed_codes": question.codes}, detector_confidence=1.0))
            if not verbatim_column:
                continue
            reason = str(row_dict.get(verbatim_column, "") or "").strip()
            if not reason:
                continue
            expected, observed = coded_direction(question, captured), direction(reason)
            if expected and observed and expected != observed:
                findings.append(CandidateFinding(finding_id=_id(respondent, question.question_id, "direction_verbatim_mismatch"), respondent_id=respondent, question_id=question.question_id, category="audio_data_mismatch", severity="critical", claim="The captured code conflicts with the direction stated in the verbatim", evidence={"captured_column": value_column, "captured_value": captured, "captured_direction": expected, "verbatim_column": verbatim_column, "verbatim": reason, "spoken_direction": observed}, detector_confidence=0.97))
            if len(reason.split()) <= 2:
                findings.append(CandidateFinding(finding_id=_id(respondent, question.question_id, "low_information_verbatim"), respondent_id=respondent, question_id=question.question_id, category="low_information_verbatim", severity="warning", claim="The verbatim may be too short to explain the response", evidence={"verbatim_column": verbatim_column, "verbatim": reason, "word_count": len(reason.split())}, detector_confidence=0.75))
            question_topic = tokens(question.text) - TOPIC_NOISE
            reason_tokens = tokens(reason)
            if len(reason.split()) >= 4 and len(question_topic) >= 1 and not (question_topic & reason_tokens):
                findings.append(CandidateFinding(finding_id=_id(respondent, question.question_id, "off_topic_verbatim"), respondent_id=respondent, question_id=question.question_id, category="off_topic_verbatim", severity="warning", claim="The verbatim may refer to a different survey variable", evidence={"question_topic_terms": sorted(question_topic), "verbatim_column": verbatim_column, "verbatim": reason}, detector_confidence=0.68))
    return findings
