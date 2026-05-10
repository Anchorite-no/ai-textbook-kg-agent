from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import JobStatus, JobType, RagIndexRequest, RagIndexResponse, RagIndexStatus, RagQueryRequest, RagQueryResponse
from app.services.converted_textbook_importer import stable_id
from app.services.job_store import job_store
from app.services.rag_index import build_rag_index, get_rag_index_status, query_rag_index


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index", response_model=RagIndexResponse)
def index_rag_evidence(payload: RagIndexRequest) -> RagIndexResponse:
    job_id = stable_id("job", "rag_index", "|".join(payload.raw_file_ids), payload.force_rebuild, payload.max_chunks or "")
    job_store.create(job_id, JobType.rag_index, "RAG 证据索引任务已创建")
    running_job = job_store.update(job_id, status=JobStatus.running, progress=20, message="正在建立 chunk 证据索引")
    try:
        status = build_rag_index(payload, running_job)
    except Exception as exc:  # noqa: BLE001 - keep API error shape stable.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="RAG 证据索引失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": job.message, "code": "RAG_INDEX_FAILED", "detail": job.error}) from exc
    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="RAG 证据索引已建立",
        result=status.model_dump(mode="json"),
    )
    return RagIndexResponse(job=job, status=status)


@router.get("/status", response_model=RagIndexStatus)
def get_rag_status() -> RagIndexStatus:
    return get_rag_index_status()


@router.post("/query", response_model=RagQueryResponse)
def query_rag(payload: RagQueryRequest) -> RagQueryResponse:
    return query_rag_index(payload)
