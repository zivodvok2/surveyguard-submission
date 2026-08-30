from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.cleaner import DataCleaner
from core.loader import DataLoader
from job_store import file_store
from routers.qc import upload_dataset

router = APIRouter(prefix="/compare")


class DiffRequest(BaseModel):
    file_id_1: str
    file_id_2: str
    id_column: str
    compare_columns: list[str]


class ShiftRequest(BaseModel):
    file_id_1: str
    file_id_2: str
    interviewer_column: str


async def _frame(file_id: str) -> pd.DataFrame:
    path = await file_store.get(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="File not found or expired")
    return DataCleaner().clean(DataLoader().load(path))


@router.post("/upload")
async def upload_wave(file: UploadFile = File(...)):
    return await upload_dataset(file)


def _records(frame: pd.DataFrame, limit: int = 500) -> list[dict[str, Any]]:
    return frame.head(limit).where(pd.notna(frame.head(limit)), None).to_dict(orient="records")


@router.post("/diff")
async def diff(req: DiffRequest):
    first, second = await _frame(req.file_id_1), await _frame(req.file_id_2)
    if req.id_column not in first.columns or req.id_column not in second.columns:
        raise HTTPException(status_code=422, detail="ID column must exist in both waves")
    columns = [column for column in req.compare_columns if column in first.columns and column in second.columns]
    left = first.set_index(req.id_column, drop=False)
    right = second.set_index(req.id_column, drop=False)
    common_ids = left.index.intersection(right.index)
    new_ids, removed_ids = right.index.difference(left.index), left.index.difference(right.index)
    changed_ids = []
    for item in common_ids:
        if any(str(left.at[item, column]) != str(right.at[item, column]) for column in columns):
            changed_ids.append(item)
    changed = right.loc[changed_ids].copy() if changed_ids else right.iloc[0:0].copy()
    for column in columns:
        if changed_ids:
            changed[f"previous_{column}"] = [left.at[item, column] for item in changed_ids]
    return {"summary": {"wave1_rows": len(first), "wave2_rows": len(second), "new_count": len(new_ids), "removed_count": len(removed_ids), "common_count": len(common_ids), "changed_count": len(changed_ids)}, "new_rows": _records(right.loc[new_ids]), "removed_rows": _records(left.loc[removed_ids]), "changed_rows": _records(changed), "common_columns": columns}


@router.post("/interviewer-shift")
async def interviewer_shift(req: ShiftRequest):
    first, second = await _frame(req.file_id_1), await _frame(req.file_id_2)
    column = req.interviewer_column
    if column not in first.columns or column not in second.columns:
        raise HTTPException(status_code=422, detail="Interviewer column must exist in both waves")
    a, b = first[column].astype(str).value_counts(), second[column].astype(str).value_counts()
    rows = []
    for interviewer in a.index.union(b.index):
        before, after = int(a.get(interviewer, 0)), int(b.get(interviewer, 0))
        rows.append({column: interviewer, "wave1_count": before, "wave2_count": after, "change": after - before, "change_pct": round((after - before) / before * 100, 1) if before else 100.0})
    return {"rows": rows, "interviewer_column": column}
