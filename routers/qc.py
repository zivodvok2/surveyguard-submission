from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from checks.deterministic import evaluate_conditions
from core.cleaner import DataCleaner
from core.loader import DataLoader
from core.reporter import build_excel_report
from core.rule_engine import RuleEngine
from job_store import file_store, job_store

router = APIRouter()
MAX_UPLOAD_BYTES = 150 * 1024 * 1024


class RunRequest(BaseModel):
    file_id: str
    config: dict[str, Any] = Field(default_factory=dict)


class SupplementalRequest(BaseModel):
    check: dict[str, Any] | None = None
    check_name: str | None = None
    issue_type: str | None = None
    severity: str = "warning"
    flagged_rows: list[dict[str, Any]] = Field(default_factory=list)


class LogicRequest(BaseModel):
    file_id: str
    rules: list[dict[str, Any]]


class EDARequest(BaseModel):
    file_id: str
    x_col: str
    y_cols: list[str] = Field(default_factory=list)
    color_col: str | None = None
    chart_type: str = "bar"
    agg_func: str = "count"


async def _load_frame(file_id: str) -> pd.DataFrame:
    path = await file_store.get(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="File not found or expired")
    return await asyncio.to_thread(lambda: DataCleaner().clean(DataLoader().load(path)))


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in DataLoader.SUPPORTED:
        raise HTTPException(status_code=415, detail=f"Unsupported dataset format: {suffix or 'unknown'}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dataset exceeds the 150 MB upload limit")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        df = await asyncio.to_thread(lambda: DataCleaner().clean(DataLoader().load(temporary)))
        file_id = await file_store.put(temporary, file.filename or f"dataset{suffix}")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read dataset: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return {"file_id": file_id, "filename": Path(file.filename or "dataset").name, "rows": len(df), "columns": len(df.columns), "column_names": list(map(str, df.columns))}


@router.get("/columns/{file_id}")
async def get_columns(file_id: str):
    df = await _load_frame(file_id)
    sample = df.head(25).where(pd.notna(df), None).to_dict(orient="records")
    return {"columns": list(map(str, df.columns)), "dtypes": {str(column): str(dtype) for column, dtype in df.dtypes.items()}, "sample": sample}


async def _execute_qc(job_id: str, file_id: str, config: dict[str, Any]) -> None:
    try:
        await job_store.update(job_id, status="running", progress=10)
        frame = await _load_frame(file_id)
        await job_store.update(job_id, progress=35)
        results = await asyncio.to_thread(RuleEngine(config).run, frame)
        await job_store.update(job_id, status="complete", progress=100, results=results)
    except Exception as exc:
        await job_store.update(job_id, status="failed", progress=100, error=str(exc))


@router.post("/run")
async def run_qc(req: RunRequest, background_tasks: BackgroundTasks):
    if not await file_store.get(req.file_id):
        raise HTTPException(status_code=404, detail="File not found or expired")
    job = await job_store.create({"file_id": req.file_id})
    background_tasks.add_task(_execute_qc, job.id, req.file_id, req.config)
    return {"job_id": job.id, "status": job.status}


@router.get("/status/{job_id}")
async def job_status(job_id: str):
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.id, "status": job.status, "progress": job.progress, "error": job.error}


@router.get("/results/{job_id}")
async def job_results(job_id: str):
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail=f"Job is {job.status}")
    return {"job_id": job.id, **(job.results or {})}


@router.get("/report/{job_id}")
async def download_report(job_id: str):
    job = await job_store.get(job_id)
    if not job or job.status != "complete" or not job.results:
        raise HTTPException(status_code=404, detail="Completed job not found")
    data = await asyncio.to_thread(build_excel_report, job.results)
    return StreamingResponse(io.BytesIO(data), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="servallab-qc-{job_id[:8]}.xlsx"'})


@router.post("/job/{job_id}/supplemental")
async def add_supplemental(job_id: str, req: SupplementalRequest):
    job = await job_store.get(job_id)
    if not job or job.status != "complete" or job.results is None:
        raise HTTPException(status_code=404, detail="Completed job not found")
    check = req.check or {"check_name": req.check_name or "Supplemental check", "issue_type": req.issue_type or "supplemental", "severity": req.severity, "flag_count": len(req.flagged_rows), "flagged_rows": req.flagged_rows}
    checks = [existing for existing in job.results.get("checks", []) if existing.get("check_name") != check.get("check_name")]
    checks.append(check)
    job.results["checks"] = checks
    job.results["total_flags"] = sum(int(item.get("flag_count", 0)) for item in checks)
    return {"status": "ok"}


@router.post("/logic/validate")
async def validate_logic(req: LogicRequest):
    df = await _load_frame(req.file_id)
    masks = []
    for rule in req.rules:
        trigger = evaluate_conditions(df, rule.get("if_conditions", []), rule.get("if_connector", "AND"))
        expected = evaluate_conditions(df, rule.get("then_conditions", []), rule.get("then_connector", "AND"))
        masks.append(trigger & ~expected)
    mask = pd.Series(False, index=df.index)
    for item in masks:
        mask |= item
    rows = df.loc[mask].head(500).where(pd.notna(df.loc[mask].head(500)), None).to_dict(orient="records")
    return {"violation_count": int(mask.sum()), "flagged_rows": rows}


def _aggregate(frame: pd.DataFrame, request: EDARequest) -> dict[str, Any]:
    if request.x_col not in frame.columns:
        raise ValueError(f"Column not found: {request.x_col}")
    chart = request.chart_type
    if chart == "histogram":
        values = pd.to_numeric(frame[request.x_col], errors="coerce").dropna()
        counts, edges = __import__("numpy").histogram(values, bins=min(20, max(5, int(len(values) ** 0.5))))
        return {"chart_type": chart, "data": [{"bin": f"{edges[i]:.2g}–{edges[i + 1]:.2g}", "count": int(count)} for i, count in enumerate(counts)], "metadata": {"rows": len(values)}}
    if chart == "heatmap":
        columns = [column for column in [request.x_col, *request.y_cols] if column in frame.columns]
        corr = frame[columns].apply(pd.to_numeric, errors="coerce").corr()
        return {"chart_type": chart, "data": {"columns": columns, "matrix": corr.where(pd.notna(corr), None).values.tolist()}, "metadata": {"rows": len(frame)}}
    if chart == "scatter" and request.y_cols:
        y = request.y_cols[0]
        subset = frame[[request.x_col, y]].dropna().head(2000)
        return {"chart_type": chart, "data": [{"x": row[request.x_col], "y": row[y]} for _, row in subset.iterrows()], "metadata": {"rows": len(subset), "y_col": y}}
    y_columns = [column for column in request.y_cols if column in frame.columns]
    if not y_columns:
        grouped = frame[request.x_col].fillna("Missing").astype(str).value_counts().head(50)
        data = [{"name": str(index), "count": int(value)} for index, value in grouped.items()]
    else:
        aggregation = request.agg_func if request.agg_func in {"mean", "sum", "min", "max", "median", "count"} else "mean"
        grouped = frame.groupby(request.x_col, dropna=False)[y_columns].agg(aggregation).reset_index().head(100)
        data = grouped.where(pd.notna(grouped), None).to_dict(orient="records")
    return {"chart_type": chart, "data": data, "metadata": {"rows": len(frame), "agg_func": request.agg_func}}


@router.post("/eda")
async def run_eda(req: EDARequest):
    frame = await _load_frame(req.file_id)
    try:
        return await asyncio.to_thread(_aggregate, frame, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/eda/summary/{file_id}")
async def eda_summary(file_id: str):
    frame = await _load_frame(file_id)
    numeric = frame.select_dtypes(include="number")
    return {
        "rows": len(frame),
        "columns": len(frame.columns),
        "missing_cells": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "numeric_columns": list(map(str, numeric.columns)),
        "categorical_columns": [str(column) for column in frame.columns if column not in numeric.columns],
    }
