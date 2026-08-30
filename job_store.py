from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class FileStore:
    def __init__(self, ttl_seconds: int = 3600):
        self.root = Path(tempfile.gettempdir()) / "servallab-uploads"
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._files: dict[str, tuple[Path, float]] = {}
        self._lock = asyncio.Lock()

    async def put(self, source: Path, filename: str) -> str:
        file_id = uuid.uuid4().hex
        safe_name = Path(filename).name
        target = self.root / f"{file_id}-{safe_name}"
        shutil.copy2(source, target)
        async with self._lock:
            self._files[file_id] = (target, time.time())
        return file_id

    async def get(self, file_id: str) -> Path | None:
        async with self._lock:
            entry = self._files.get(file_id)
            if not entry:
                return None
            path, created = entry
            if time.time() - created > self.ttl_seconds or not path.exists():
                self._files.pop(file_id, None)
                path.unlink(missing_ok=True)
                return None
            return path


@dataclass
class Job:
    id: str
    status: str = "queued"
    progress: int = 0
    error: str | None = None
    results: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, metadata: dict[str, Any] | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex, metadata=metadata or {})
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **changes: Any) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in changes.items():
                setattr(job, key, value)
            return job


file_store = FileStore()
job_store = JobStore()
