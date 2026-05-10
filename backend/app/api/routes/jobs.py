from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.schemas import JobRecord, JobRetryResponse
from app.services.job_store import job_store
from app.services.pipeline_runner import retry_textbook_pipeline, run_textbook_pipeline


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
def retry_job(job_id: str, background_tasks: BackgroundTasks) -> JobRetryResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if not job.context_path:
        raise HTTPException(
            status_code=400,
            detail={"message": "该任务没有可重试上下文", "code": "JOB_NOT_RETRYABLE", "detail": job_id},
        )
    try:
        queued = retry_textbook_pipeline(job_id)
    except Exception as exc:  # noqa: BLE001 - normalized by app exception handler.
        raise HTTPException(
            status_code=400,
            detail={"message": "任务重试失败", "code": "JOB_RETRY_FAILED", "detail": str(exc)},
        ) from exc
    background_tasks.add_task(run_textbook_pipeline, job_id)
    return JobRetryResponse(job=queued, accepted=True)
