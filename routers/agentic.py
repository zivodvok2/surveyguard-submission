from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pydantic import BaseModel

from agentic.orchestrator import SurveyGuardOrchestrator
from core.loader import DataLoader
from job_store import job_store

router = APIRouter(prefix="/agentic")
QUESTIONNAIRE_SUFFIXES = {".txt", ".md", ".json", ".pdf", ".docx"}
RECORDING_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".json", ".txt", ".srt", ".vtt"}
MAX_FILE_BYTES = 150 * 1024 * 1024


class ReviewDecision(BaseModel):
    decision: Literal["confirmed", "rejected", "investigate"]


async def _save_upload(upload: UploadFile, directory: Path, allowed: set[str]) -> Path:
    name = Path(upload.filename or "upload").name
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported file format: {suffix or 'unknown'}")
    content = await upload.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"{name} exceeds the 150 MB limit")
    target = directory / name
    target.write_bytes(content)
    return target


async def _execute_audit(job_id: str, questionnaire: Path, dataset: Path, recordings: list[Path], mapping: dict[str, Any], key: str | None, directory: Path) -> None:
    try:
        await job_store.update(job_id, status="running", progress=5)
        report = await SurveyGuardOrchestrator(job_id).run(questionnaire, dataset, recordings, mapping, key)
        await job_store.update(job_id, status="complete", progress=100, results=report.model_dump(mode="json"))
    except Exception as exc:
        await job_store.update(job_id, status="failed", progress=100, error=str(exc))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@router.post("/audits")
async def create_audit(
    background_tasks: BackgroundTasks,
    questionnaire: UploadFile = File(...),
    dataset: UploadFile = File(...),
    recordings: list[UploadFile] = File(...),
    column_mapping: str = Form("{}"),
    groq_api_key: str | None = Form(None),
):
    if not recordings:
        raise HTTPException(status_code=422, detail="At least one recording or timestamped transcript is required")
    if len(recordings) > 50:
        raise HTTPException(status_code=413, detail="A single audit supports up to 50 recordings")
    try:
        mapping = json.loads(column_mapping or "{}")
        if not isinstance(mapping, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="column_mapping must be a JSON object") from exc
    directory = Path(tempfile.mkdtemp(prefix="surveyguard-audit-"))
    try:
        questionnaire_path = await _save_upload(questionnaire, directory, QUESTIONNAIRE_SUFFIXES)
        dataset_path = await _save_upload(dataset, directory, DataLoader.SUPPORTED)
        recording_paths = [await _save_upload(recording, directory, RECORDING_SUFFIXES) for recording in recordings]
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    job = await job_store.create({"kind": "agentic_audit", "questionnaire": questionnaire_path.name, "dataset": dataset_path.name, "recordings": len(recording_paths)})
    background_tasks.add_task(_execute_audit, job.id, questionnaire_path, dataset_path, recording_paths, mapping, groq_api_key, directory)
    return {"audit_id": job.id, "status": job.status, "recordings": len(recording_paths)}


@router.get("/audits/{audit_id}/status")
async def audit_status(audit_id: str):
    job = await job_store.get(audit_id)
    if not job or job.metadata.get("kind") != "agentic_audit":
        raise HTTPException(status_code=404, detail="Audit not found")
    return {"audit_id": job.id, "status": job.status, "progress": job.progress, "error": job.error}


@router.get("/audits/{audit_id}")
async def audit_results(audit_id: str):
    job = await job_store.get(audit_id)
    if not job or job.metadata.get("kind") != "agentic_audit":
        raise HTTPException(status_code=404, detail="Audit not found")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail=f"Audit is {job.status}")
    return job.results


def _iter_findings(report: dict[str, Any]):
    for finding in report.get("dataset_findings", []):
        yield finding
    for interview in report.get("interviews", []):
        for finding in interview.get("findings", []):
            yield finding


@router.post("/audits/{audit_id}/findings/{finding_id}/decision")
async def review_finding(audit_id: str, finding_id: str, req: ReviewDecision):
    job = await job_store.get(audit_id)
    if not job or job.status != "complete" or not job.results:
        raise HTTPException(status_code=404, detail="Completed audit not found")
    for finding in _iter_findings(job.results):
        if finding.get("finding_id") == finding_id:
            finding["reviewer_decision"] = req.decision
            return {"status": "ok", "finding_id": finding_id, "reviewer_decision": req.decision}
    raise HTTPException(status_code=404, detail="Finding not found")


def _excel(report: dict[str, Any]) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["SurveyGuard Multimodal QC Audit"])
    summary["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    summary["A1"].fill = PatternFill("solid", fgColor="13263D")
    for key, value in report.get("summary", {}).items():
        summary.append([key.replace("_", " ").title(), value])
    findings = workbook.create_sheet("Findings")
    headers = ["respondent_id", "question_id", "category", "severity", "verdict", "confidence", "claim", "verifier_reason", "reviewer_decision", "evidence"]
    findings.append(headers)
    for cell in findings[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="007F73")
    for finding in _iter_findings(report):
        findings.append([finding.get(key) if key != "evidence" else json.dumps(finding.get("evidence", {}), ensure_ascii=False, default=str) for key in headers])
    findings.freeze_panes = "A2"
    findings.auto_filter.ref = findings.dimensions
    transcript_sheet = workbook.create_sheet("Transcript evidence")
    transcript_sheet.append(["Respondent", "Recording", "Start", "End", "Speaker", "Transcript"])
    for interview in report.get("interviews", []):
        for segment in interview.get("transcript", []):
            transcript_sheet.append([interview.get("respondent_id"), interview.get("recording_name"), segment.get("start"), segment.get("end"), segment.get("speaker"), segment.get("text")])
    rules = workbook.create_sheet("Questionnaire rules")
    rules.append(["Question", "Text", "Codes", "Reason variable", "Read exactly", "Read options", "Probe", "Consent", "Routing"])
    for question in report.get("rule_spec", []):
        rules.append([question.get("question_id"), question.get("text"), json.dumps(question.get("codes", {}), ensure_ascii=False), question.get("reason_variable"), question.get("read_exactly"), question.get("read_options"), question.get("probe"), question.get("consent"), json.dumps(question.get("routing", []), ensure_ascii=False)])
    for sheet in workbook.worksheets:
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(55, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


@router.get("/audits/{audit_id}/export")
async def export_audit(audit_id: str):
    job = await job_store.get(audit_id)
    if not job or job.status != "complete" or not job.results:
        raise HTTPException(status_code=404, detail="Completed audit not found")
    content = _excel(job.results)
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="surveyguard-audit-{audit_id[:8]}.xlsx"'})
