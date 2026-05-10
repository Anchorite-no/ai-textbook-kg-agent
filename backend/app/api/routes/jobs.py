from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import JobRecord
from app.services.job_store import job_store


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job
