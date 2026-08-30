from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

# Support both ``python -m evaluation.run_eval`` and direct script execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agentic.alignment import align_questions, text_similarity
from agentic.data_qc import semantic_data_findings
from agentic.detector import detect_interview_issues
from agentic.models import TranscriptSegment
from agentic.questionnaire import parse_questionnaire
from agentic.verifier import verify_finding
from evaluation.cases import CASES


ROOT = Path(__file__).resolve().parent


def key(question_id: str | None, category: str) -> str:
    return f"{question_id or '-'}::{category}"


def baseline_predict(case: dict[str, Any]) -> set[str]:
    """Single unstructured LLM prompt — the fair hackathon baseline.
    Receives raw questionnaire text, captured data row, and transcript with no
    additional scaffolding, and asks the model to find quality issues.

    Raises on API errors rather than silently returning an empty set — a failed
    call must never be scored as "correctly found nothing."
    """
    from agentic.llm_client import call_llm

    transcript_text = " | ".join(
        f"[{seg['speaker']}] {seg['text']}" for seg in case["segments"]
    )
    prompt = (
        "You are a survey quality-control reviewer. Given a questionnaire, "
        "a captured data row, and an interview transcript, identify any quality issues.\n\n"
        f"QUESTIONNAIRE:\n{case['questionnaire']}\n\n"
        f"CAPTURED DATA ROW:\n{json.dumps(case['row'])}\n\n"
        f"INTERVIEW TRANSCRIPT:\n{transcript_text}\n\n"
        "List each issue as a JSON array of objects with:\n"
        '  {"question_id": "<id or null>", "category": "<category>"}\n\n'
        "Use these category names where appropriate:\n"
        "  audio_data_mismatch, verbatim_contradicts_audio, verbatim_audio_mismatch,\n"
        "  insufficient_probing, possible_leading_question, question_not_detected,\n"
        "  consent_not_detected, required_wording_changed, invalid_code,\n"
        "  low_information_verbatim, off_topic_verbatim\n\n"
        "Respond with the JSON array only. Use [] if no issues found."
    )
    raw = call_llm(prompt, max_tokens=2048, expect_json=True)
    print(f"[baseline_predict] {case['id']} raw response ({len(raw)} chars): {raw[:200]!r}", flush=True)
    issues = json.loads(raw)
    if not isinstance(issues, list):
        raise RuntimeError(
            f"baseline_predict: model returned a non-list JSON value for case {case['id']!r} "
            f"(got {type(issues).__name__}). Raw response: {raw!r}"
        )
    return {key(item.get("question_id"), item["category"]) for item in issues if "category" in item}


def final_predict(case: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]], set[str], set[str]]:
    questions = parse_questionnaire(case["questionnaire"])
    frame = pd.DataFrame([case["row"]])
    transcript = [TranscriptSegment(**segment) for segment in case["segments"]]
    alignments = align_questions(questions, transcript)
    data_candidates = semantic_data_findings(frame, questions, {}, "respondent_id")
    candidates = data_candidates + detect_interview_issues(str(case["row"]["respondent_id"]), questions, transcript, alignments, case["row"], {}, {"duration_seconds": transcript[-1].end, "status": "transcript_provided"})
    verified = [verify_finding(candidate) for candidate in candidates]
    predictions = {key(finding.question_id, finding.category) for finding in verified if finding.verdict != "rejected"}
    unverified = {key(finding.question_id, finding.category) for finding in candidates}
    data_only = {key(finding.question_id, finding.category) for finding in data_candidates}
    return predictions, [finding.model_dump(mode="json") for finding in verified], unverified, data_only


def metrics(records: list[dict[str, Any]], prediction_field: str) -> dict[str, float | int]:
    tp = fp = fn = 0
    for record in records:
        truth, predicted = set(record["ground_truth"]), set(record[prediction_field])
        tp += len(truth & predicted)
        fp += len(predicted - truth)
        fn += len(truth - predicted)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def run(cases=None, output_path: Path | None = None, trajectories_path: Path | None = None) -> dict[str, Any]:
    if cases is None:
        cases = CASES
    records: list[dict[str, Any]] = []
    trajectory_examples: list[dict[str, Any]] = []
    baseline_ms = final_ms = 0.0
    baseline_audio = final_audio = 0.0
    for i, case in enumerate(cases):
        if i > 0:
            # 2-second gap between cases keeps burst rate well under Groq's 30 req/min limit.
            time.sleep(2)
        ground_truth = {key(item["question_id"], item["category"]) for item in case["ground_truth"]}
        started = time.perf_counter()
        baseline = baseline_predict(case)
        baseline_ms += (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        final, verified, unverified, data_only = final_predict(case)
        final_ms += (time.perf_counter() - started) * 1000
        duration = float(case["segments"][-1]["end"])
        baseline_audio += duration
        final_audio += min(duration, 12 * len(final))
        records.append({"case_id": case["id"], "ground_truth": sorted(ground_truth), "baseline_predictions": sorted(baseline), "data_only_predictions": sorted(data_only), "unverified_predictions": sorted(unverified), "final_predictions": sorted(final)})
        if len(trajectory_examples) < 5 and (ground_truth or final):
            trajectory_examples.append({"case_id": case["id"], "ground_truth": sorted(ground_truth), "verified_findings": verified})
    output = {
        "evaluation_version": "1.0",
        "cases": len(cases),
        "primary_metric": "issue-detection F1",
        "baseline": metrics(records, "baseline_predictions"),
        "data_only": metrics(records, "data_only_predictions"),
        "multimodal_without_verifier": metrics(records, "unverified_predictions"),
        "final": metrics(records, "final_predictions"),
        "runtime_ms": {"baseline_total": round(baseline_ms, 2), "final_total": round(final_ms, 2)},
        "review_audio_seconds_requested": {"baseline_full_recordings": round(baseline_audio, 1), "surveyguard_flag_windows": round(final_audio, 1), "reduction_pct": round((1 - final_audio / baseline_audio) * 100, 1) if baseline_audio else 0},
        "records": records,
    }
    # Callers pass explicit paths — run() never touches the filesystem on its own,
    # so the main eval and generalization eval cannot clobber each other's files.
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    if trajectories_path is not None:
        trajectories_path.parent.mkdir(parents=True, exist_ok=True)
        trajectories_path.write_text(json.dumps(trajectory_examples, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the reproducible SurveyGuard baseline/final evaluation")
    parser.add_argument("--generalization", action="store_true", help="Run against generalization_cases.py instead of cases.py")
    args = parser.parse_args()
    results_dir = ROOT / "results"
    if args.generalization:
        from evaluation.generalization_cases import GENERALIZATION_CASES
        out_path = results_dir / "generalization_eval.json"
        result = run(GENERALIZATION_CASES, output_path=out_path)
        print(f"[generalization] written to {out_path}")
    else:
        out_path = results_dir / "main_eval.json"
        result = run(output_path=out_path, trajectories_path=ROOT / "trajectories.json")
        print(f"[main] written to {out_path}")
    print(json.dumps({"cases": result["cases"], "baseline": result["baseline"], "final": result["final"], "review_audio_seconds_requested": result["review_audio_seconds_requested"]}, indent=2))
