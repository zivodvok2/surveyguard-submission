import json
import os

import asyncio

import pytest

from agentic.alignment import align_questions
from agentic.models import TranscriptSegment
from agentic.orchestrator import SurveyGuardOrchestrator
from agentic.questionnaire import parse_questionnaire

# Detector and verifier make real LLM calls via Groq — skip when key is absent.
requires_api_key = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — LLM-based detector/verifier cannot run",
)


QUESTIONNAIRE = """
Q1. Compared with last month, did production increase, remain unchanged, or decrease?
1 = Increase
2 = Remain unchanged
3 = Decrease
Q1a. Why did production change? PROBE FULLY
""".strip()


def test_questionnaire_parser_extracts_codes_and_reason_link():
    questions = parse_questionnaire(QUESTIONNAIRE)
    assert [item.question_id for item in questions] == ["Q1", "Q1A"]
    assert questions[0].codes == {"1": "Increase", "2": "Remain unchanged", "3": "Decrease"}
    assert questions[0].reason_variable == "Q1A"
    assert questions[1].probe is True


def test_alignment_finds_paraphrased_question():
    question = parse_questionnaire(QUESTIONNAIRE)[0]
    transcript = [
        TranscriptSegment(start=0, end=4, speaker="interviewer", text="Did your production go up, stay the same, or go down compared with last month?"),
        TranscriptSegment(start=4, end=8, speaker="respondent", text="It went down."),
    ]
    alignment = align_questions([question], transcript)[0]
    assert alignment.segment_start == 0
    assert alignment.score >= 0.28


@requires_api_key
def test_orchestrator_confirms_spoken_answer_mismatch(tmp_path):
    questionnaire = tmp_path / "questionnaire.txt"
    questionnaire.write_text(QUESTIONNAIRE)
    dataset = tmp_path / "data.csv"
    dataset.write_text("respondent_id,Q1,Q1A\nR001,1,Production increased due to demand\n")
    transcript = tmp_path / "R001.json"
    transcript.write_text(json.dumps({"segments": [
        {"start": 0, "end": 5, "speaker": "interviewer", "text": "Compared with last month, did production increase, remain unchanged, or decrease?"},
        {"start": 5, "end": 9, "speaker": "respondent", "text": "Production decreased."},
        {"start": 9, "end": 12, "speaker": "interviewer", "text": "Why did production change?"},
        {"start": 12, "end": 18, "speaker": "respondent", "text": "Customer orders were lower."},
    ]}))
    report = asyncio.run(SurveyGuardOrchestrator("test-audit").run(questionnaire, dataset, [transcript]))
    findings = report.interviews[0].findings
    mismatch = next(item for item in findings if item.category == "audio_data_mismatch")
    assert mismatch.verdict == "confirmed"
    assert mismatch.evidence["captured_direction"] == "increase"
    assert mismatch.evidence["spoken_direction"] == "decrease"


@requires_api_key
def test_agentic_api_end_to_end(client):
    data = {"respondent_id": "R001", "Q1": 1, "Q1A": "Production increased due to demand"}
    transcript = {"segments": [
        {"start": 0, "end": 4, "text": "Compared with last month, did production increase, remain unchanged, or decrease?"},
        {"start": 4, "end": 8, "text": "Production decreased."},
    ]}
    response = client.post(
        "/api/agentic/audits",
        files=[
            ("questionnaire", ("questionnaire.txt", QUESTIONNAIRE, "text/plain")),
            ("dataset", ("survey.csv", "respondent_id,Q1,Q1A\nR001,1,Production increased due to demand\n", "text/csv")),
            ("recordings", ("R001.json", json.dumps(transcript), "application/json")),
        ],
        data={"column_mapping": json.dumps({"respondent_id": "respondent_id"})},
    )
    assert response.status_code == 200
    audit_id = response.json()["audit_id"]
    status = client.get(f"/api/agentic/audits/{audit_id}/status").json()
    assert status["status"] == "complete"
    report = client.get(f"/api/agentic/audits/{audit_id}")
    assert report.status_code == 200
    assert report.json()["summary"]["confirmed_findings"] >= 1
