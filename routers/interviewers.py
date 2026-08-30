from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.cleaner import DataCleaner
from core.loader import DataLoader
from job_store import file_store, job_store

router = APIRouter(prefix="/interviewers")


class RiskRequest(BaseModel):
    file_id: str
    job_id: str
    interviewer_column: str
    red_threshold: float = 60
    amber_threshold: float = 30
    supervisor_column: str | None = None
    date_column: str | None = None
    duration_column: str | None = None


@router.post("/risk")
async def risk(req: RiskRequest):
    path, job = await file_store.get(req.file_id), await job_store.get(req.job_id)
    if not path or not job or not job.results:
        raise HTTPException(status_code=404, detail="Dataset or completed QC job not found")
    frame = DataCleaner().clean(DataLoader().load(path))
    if req.interviewer_column not in frame.columns:
        raise HTTPException(status_code=422, detail="Interviewer column not found")
    frame[req.interviewer_column] = frame[req.interviewer_column].astype(str)
    counts = frame[req.interviewer_column].value_counts()
    issues: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    for check in job.results.get("checks", []):
        issue_type = str(check.get("issue_type", "other"))
        for row in check.get("flagged_rows", []):
            interviewer = str(row.get(req.interviewer_column, ""))
            if interviewer:
                issues[interviewer][issue_type] += 1
                issues[interviewer]["total"] += 1
    rows = []
    for interviewer, total in counts.items():
        flags = issues[interviewer]
        flag_rate = flags["total"] / max(int(total), 1) * 100
        score = min(100.0, flag_rate * 1.4 + min(flags.get("duplicate", 0) * 8, 24))
        record: dict[str, Any] = {req.interviewer_column: interviewer, "risk_score": round(score, 1), "risk_level": "HIGH" if score >= req.red_threshold else "MEDIUM" if score >= req.amber_threshold else "LOW", "total_interviews": int(total), "total_flags": flags["total"], "flag_rate_pct": round(flag_rate, 1), "fabrication_flags": flags.get("fabrication", 0) + flags.get("near_duplicate", 0), "duration_flags": flags.get("duration_anomaly", 0), "straightlining_flags": flags.get("straightlining", 0), "productivity_flags": flags.get("productivity_anomaly", 0), "verbatim_flags": flags.get("verbatim", 0)}
        subset = frame[frame[req.interviewer_column] == interviewer]
        if req.supervisor_column and req.supervisor_column in subset.columns:
            mode = subset[req.supervisor_column].dropna().mode()
            record["supervisor"] = None if mode.empty else str(mode.iloc[0])
        if req.duration_column and req.duration_column in subset.columns:
            duration = pd.to_numeric(subset[req.duration_column], errors="coerce")
            record.update({"avg_duration": None if duration.dropna().empty else round(float(duration.mean()), 1), "min_duration": None if duration.dropna().empty else float(duration.min()), "max_duration": None if duration.dropna().empty else float(duration.max())})
        rows.append(record)
    date_trends = []
    if req.date_column and req.date_column in frame.columns:
        date_counts: dict[str, int] = defaultdict(int)
        for check in job.results.get("checks", []):
            for row in check.get("flagged_rows", []):
                if row.get(req.date_column) is not None:
                    date_counts[str(row[req.date_column])] += 1
        date_trends = [{"date": key, "flag_count": value} for key, value in sorted(date_counts.items())]
    matrix = frame.groupby(req.interviewer_column).size().rename("interviews").reset_index().to_dict(orient="records")
    return {"rows": sorted(rows, key=lambda item: item["risk_score"], reverse=True), "interviewer_column": req.interviewer_column, "date_trends": date_trends, "productivity_matrix": matrix}
