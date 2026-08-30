from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.cleaner import DataCleaner
from core.loader import DataLoader
from job_store import file_store

router = APIRouter(prefix="/ai")


class AIRequest(BaseModel):
    groq_api_key: str | None = None
    model: str = "llama-3.1-8b-instant"


class NLRuleRequest(AIRequest):
    description: str


class FeedbackRequest(AIRequest):
    interviewer_id: str
    stats: dict[str, Any]


class DataQuestionRequest(AIRequest):
    file_id: str
    question: str


class ExplainRequest(AIRequest):
    check_name: str
    severity: str
    flag_count: int
    total_rows: int
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SummaryRequest(AIRequest):
    total_flags: int
    total_rows: int
    checks: list[dict[str, Any]]


async def _chat(request: AIRequest, system: str, prompt: str) -> str:
    key = request.groq_api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=422, detail="A Groq API key is required for this AI action")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": request.model, "temperature": 0, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The configured AI provider rejected the request")
    return response.json()["choices"][0]["message"]["content"].strip()


@router.post("/nl-to-rule")
async def natural_language_rule(req: NLRuleRequest):
    raw = await _chat(req, "Convert survey QC instructions to JSON only. Return if_conditions and then_conditions arrays with column, operator, and value.", req.description)
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise HTTPException(status_code=502, detail="AI provider did not return a valid rule")
    try:
        rule = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI provider returned invalid JSON") from exc
    return {"rule": rule, "raw": raw}


@router.post("/feedback-letter")
async def feedback_letter(req: FeedbackRequest):
    prompt = f"Interviewer: {req.interviewer_id}\nEvidence: {json.dumps(req.stats, default=str)}\nWrite a concise, factual coaching note. Do not accuse the interviewer of fraud; distinguish facts from review signals."
    return {"letter": await _chat(req, "You are a fair survey quality coach.", prompt)}


@router.post("/data-question")
async def data_question(req: DataQuestionRequest):
    path = await file_store.get(req.file_id)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    frame = DataCleaner().clean(DataLoader().load(path))
    context = {"rows": len(frame), "columns": list(map(str, frame.columns)), "sample": frame.head(8).where(frame.notna(), None).to_dict(orient="records"), "summary": frame.describe(include="all").fillna("").astype(str).to_dict()}
    answer = await _chat(req, "Answer only from the supplied aggregate and sample. State when the evidence is insufficient.", f"Data context: {json.dumps(context, default=str)}\nQuestion: {req.question}")
    return {"answer": answer}


@router.post("/explain-flags")
async def explain_flags(req: ExplainRequest):
    prompt = json.dumps(req.model_dump(exclude={"groq_api_key", "model"}), default=str)
    return {"explanation": await _chat(req, "Explain survey QC evidence in plain language. Do not infer misconduct.", prompt)}


@router.post("/qc-summary")
async def qc_summary(req: SummaryRequest):
    prompt = json.dumps(req.model_dump(exclude={"groq_api_key", "model"}), default=str)
    return {"summary": await _chat(req, "Write a concise survey QC executive summary. Prioritise verified critical issues and recommended human review.", prompt)}
