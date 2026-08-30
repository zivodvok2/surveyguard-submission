from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuestionSpec(BaseModel):
    question_id: str
    text: str
    variable: str | None = None
    reason_variable: str | None = None
    codes: dict[str, str] = Field(default_factory=dict)
    read_exactly: bool = False
    read_options: bool | None = None
    probe: bool = False
    consent: bool = False
    routing: list[dict[str, Any]] = Field(default_factory=list)


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str = "unknown"


class Alignment(BaseModel):
    question_id: str
    score: float
    segment_start: int | None = None
    segment_end: int | None = None
    start: float | None = None
    end: float | None = None
    transcript: str = ""


class CandidateFinding(BaseModel):
    finding_id: str
    respondent_id: str
    question_id: str | None = None
    category: str
    severity: Literal["critical", "warning", "info"]
    claim: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    detector_confidence: float = 0.0


class VerifiedFinding(CandidateFinding):
    verdict: Literal["confirmed", "rejected", "review"]
    confidence: float
    verifier_reason: str
    reviewer_decision: Literal["pending", "confirmed", "rejected", "investigate"] = "pending"


class InterviewAudit(BaseModel):
    respondent_id: str
    recording_name: str
    duration_seconds: float | None = None
    speech_coverage: float | None = None
    transcript: list[TranscriptSegment]
    alignments: list[Alignment]
    findings: list[VerifiedFinding]


class AuditReport(BaseModel):
    audit_id: str
    generated_at: str
    questionnaire_name: str
    dataset_name: str
    questions_extracted: int
    interviews_reviewed: int
    summary: dict[str, Any]
    rule_spec: list[QuestionSpec]
    dataset_checks: list[dict[str, Any]] = Field(default_factory=list)
    dataset_findings: list[VerifiedFinding] = Field(default_factory=list)
    interviews: list[InterviewAudit]
    trajectory: list[dict[str, Any]]
