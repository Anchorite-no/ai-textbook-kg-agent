from __future__ import annotations

from datetime import datetime
from threading import Lock

from app.models.schemas import JobRecord, JobStatus, JobType, PipelineStepName, PipelineStepRecord, PipelineStepStatus


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

    def update_step(
        self,
        job_id: str,
        step_name: PipelineStepName,
        status: PipelineStepStatus,
        progress: int,
        message: str = "",
        error: str | None = None,
    ) -> JobRecord:
        with self._lock:
            job = self._jobs[job_id]
            now = datetime.utcnow()
            steps = list(job.steps)
            step_index = next((index for index, step in enumerate(steps) if step.name == step_name), None)
            started_at = now if status == PipelineStepStatus.running else None
            finished_at = now if status in {PipelineStepStatus.completed, PipelineStepStatus.failed, PipelineStepStatus.skipped} else None
            if step_index is None:
                steps.append(
                    PipelineStepRecord(
                        name=step_name,
                        status=status,
                        progress=progress,
                        message=message,
                        started_at=started_at,
                        finished_at=finished_at,
                        error=error,
                    )
                )
            else:
                existing = steps[step_index]
                steps[step_index] = existing.model_copy(
                    update={
                        "status": status,
                        "progress": progress,
                        "message": message,
                        "started_at": existing.started_at or started_at,
                        "finished_at": finished_at if finished_at is not None else existing.finished_at,
                        "error": error,
                    }
                )
            updated = job.model_copy(update={"steps": steps, "updated_at": now})
            self._jobs[job_id] = updated
            return updated


job_store = InMemoryJobStore()
