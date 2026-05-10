from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.models.schemas import SampleDatasetPrepareRequest, SampleDatasetPrepareResponse, SampleDatasetResponse
from app.services.job_store import job_store
from app.services.sample_dataset import create_prepare_seven_books_job, get_seven_books_dataset, run_prepare_seven_books


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/seven-books", response_model=SampleDatasetResponse)
def get_seven_books() -> SampleDatasetResponse:
    return get_seven_books_dataset()


@router.post("/seven-books/prepare", response_model=SampleDatasetPrepareResponse)
def prepare_seven_books(
    background_tasks: BackgroundTasks,
    payload: SampleDatasetPrepareRequest | None = None,
) -> SampleDatasetPrepareResponse:
    request = payload or SampleDatasetPrepareRequest()
    job_id = create_prepare_seven_books_job(request)
    background_tasks.add_task(run_prepare_seven_books, job_id, request)
    job = job_store.get(job_id)
    if job is None:
        raise RuntimeError(f"Job not found after create: {job_id}")
    return SampleDatasetPrepareResponse(job=job, dataset=get_seven_books_dataset())
