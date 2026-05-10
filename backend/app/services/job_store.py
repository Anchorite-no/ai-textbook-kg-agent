from __future__ import annotations

from datetime import datetime
from threading import Lock

from app.models.schemas import JobRecord, JobStatus, JobType


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(self, job_id: str, job_type: JobType, message: str = "") -> JobRecord:
        job = JobRecord(
            id=job_id,
            job_type=job_type,
            status=JobStatus.queued,
            progress=0,
            message=message,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def update(self, job_id: str, **changes: object) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            changes["updated_at"] = datetime.utcnow()
            updated = job.model_copy(update=changes)
            self._jobs[job_id] = updated
            return updated

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)


job_store = InMemoryJobStore()
