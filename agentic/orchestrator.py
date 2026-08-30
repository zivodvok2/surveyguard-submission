from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from core.cleaner import DataCleaner
from core.loader import DataLoader
from core.rule_engine import RuleEngine

from .alignment import align_questions
from .data_qc import semantic_data_findings
from .detector import detect_interview_issues
from .models import AuditReport, InterviewAudit
from .questionnaire import extract_questionnaire_text, parse_questionnaire
from .transcription import audio_technical_metrics, transcribe_audio
from .verifier import verify_finding


ID_ALIASES = ("respondent_id", "respondent id", "instance_id", "instance id", "serial", "id")


class SurveyGuardOrchestrator:
    def __init__(self, audit_id: str | None = None):
        self.audit_id = audit_id or uuid.uuid4().hex
        self.trajectory: list[dict[str, Any]] = []

    def _trace(self, component: str, action: str, output: dict[str, Any], started: float) -> None:
        self.trajectory.append({"component": component, "action": action, "output": output, "duration_ms": round((time.perf_counter() - started) * 1000, 1)})

    @staticmethod
    def _respondent_column(frame: pd.DataFrame, mapping: dict[str, Any]) -> str | None:
        configured = mapping.get("respondent_id")
        if configured in frame.columns:
            return str(configured)
        lookup = {str(column).strip().lower(): str(column) for column in frame.columns}
        return next((lookup[alias] for alias in ID_ALIASES if alias in lookup), None)

    @staticmethod
    def _row_for_recording(frame: pd.DataFrame, respondent_column: str | None, recording: Path, index: int) -> tuple[str, dict[str, Any]]:
        if respondent_column:
            stem = recording.stem.lower()
            for _, row in frame.iterrows():
                respondent = str(row[respondent_column]).strip()
                if respondent and respondent.lower() in stem:
                    return respondent, row.to_dict()
        if index < len(frame):
            row = frame.iloc[index]
            respondent = str(row.get(respondent_column, index + 1)) if respondent_column else str(index + 1)
            return respondent, row.to_dict()
        return recording.stem, {}

    async def run(self, questionnaire_path: str | Path, dataset_path: str | Path, recording_paths: list[str | Path], column_mapping: dict[str, Any] | None = None, groq_api_key: str | None = None) -> AuditReport:
        mapping = column_mapping or {}
        started = time.perf_counter()
        questionnaire_text = extract_questionnaire_text(questionnaire_path)
        questions = parse_questionnaire(questionnaire_text)
        if not questions:
            raise ValueError("No questionnaire questions could be extracted")
        self._trace("questionnaire_agent", "extract_structured_rules", {"questions": len(questions), "coded_questions": sum(bool(question.codes) for question in questions), "routing_rules": sum(len(question.routing) for question in questions)}, started)

        started = time.perf_counter()
        frame = DataCleaner().clean(DataLoader().load(dataset_path))
        respondent_column = self._respondent_column(frame, mapping)
        deterministic_config = {"missing_threshold": 1.0, "missing_columns": mapping.get("required_columns", []), "duplicate_check": {"enabled": True, "subset_columns": [respondent_column] if respondent_column else []}, "logic_rules": mapping.get("logic_rules", []), "range_rules": mapping.get("range_rules", [])}
        deterministic = RuleEngine(deterministic_config).run(frame)
        semantic_candidates = semantic_data_findings(frame, questions, mapping, respondent_column)
        semantic_verified = [verify_finding(candidate) for candidate in semantic_candidates]
        self._trace("data_qc_engine", "run_deterministic_and_semantic_checks", {"rows": len(frame), "deterministic_flags": deterministic["total_flags"], "semantic_candidates": len(semantic_candidates)}, started)

        audits: list[InterviewAudit] = []
        for index, recording_value in enumerate(recording_paths):
            recording = Path(recording_value)
            respondent_id, row = self._row_for_recording(frame, respondent_column, recording, index)
            started = time.perf_counter()
            transcript = await transcribe_audio(recording, groq_api_key)
            if recording.suffix.lower() in {".json", ".txt", ".srt", ".vtt"}:
                duration = max((segment.end for segment in transcript), default=0)
                technical = {"duration_seconds": duration, "status": "transcript_provided"}
            else:
                technical = audio_technical_metrics(recording)
            self._trace("transcription_engine", "transcribe_recording", {"recording": recording.name, "segments": len(transcript), "duration_seconds": technical.get("duration_seconds")}, started)

            started = time.perf_counter()
            alignments = align_questions(questions, transcript)
            self._trace("alignment_agent", "align_questions_to_timestamps", {"respondent_id": respondent_id, "aligned": sum(alignment.score >= 0.28 for alignment in alignments), "questions": len(questions)}, started)

            started = time.perf_counter()
            candidates = detect_interview_issues(respondent_id, questions, transcript, alignments, row, mapping, technical)
            verified = [verify_finding(candidate) for candidate in candidates]
            self._trace("verification_agent", "independently_verify_candidates", {"respondent_id": respondent_id, "candidates": len(candidates), "confirmed": sum(finding.verdict == "confirmed" for finding in verified), "review": sum(finding.verdict == "review" for finding in verified), "rejected": sum(finding.verdict == "rejected" for finding in verified)}, started)
            audits.append(InterviewAudit(respondent_id=respondent_id, recording_name=recording.name, duration_seconds=technical.get("duration_seconds"), speech_coverage=None, transcript=transcript, alignments=alignments, findings=verified))

        all_findings = [finding for audit in audits for finding in audit.findings] + semantic_verified
        confirmed = sum(finding.verdict == "confirmed" for finding in all_findings)
        review = sum(finding.verdict == "review" for finding in all_findings)
        rejected = sum(finding.verdict == "rejected" for finding in all_findings)
        summary = {"rows_checked": len(frame), "recordings_checked": len(audits), "candidate_findings": len(all_findings), "confirmed_findings": confirmed, "needs_human_review": review, "rejected_by_verifier": rejected, "critical_confirmed": sum(finding.verdict == "confirmed" and finding.severity == "critical" for finding in all_findings), "deterministic_flags": deterministic["total_flags"]}
        self._trace("report_agent", "assemble_evidence_report", summary, time.perf_counter())
        return AuditReport(audit_id=self.audit_id, generated_at=datetime.now(timezone.utc).isoformat(), questionnaire_name=Path(questionnaire_path).name, dataset_name=Path(dataset_path).name, questions_extracted=len(questions), interviews_reviewed=len(audits), summary=summary, rule_spec=questions, dataset_checks=deterministic["checks"], dataset_findings=semantic_verified, interviews=audits, trajectory=self.trajectory)
