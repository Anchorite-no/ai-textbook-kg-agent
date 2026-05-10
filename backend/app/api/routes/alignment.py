from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import AlignmentBuildRequest, AlignmentBuildResponse, AlignmentResponse, JobStatus, JobType
from app.services.alignment_builder import build_alignment
from app.services.alignment_storage import load_alignment, load_latest_alignment
from app.services.converted_textbook_importer import stable_id
from app.services.job_store import job_store


router = APIRouter(prefix="/alignment", tags=["alignment"])


@router.post("/build", response_model=AlignmentBuildResponse)
def build_alignment_graph(payload: AlignmentBuildRequest) -> AlignmentBuildResponse:
    job_id = stable_id("job", "alignment_build", "|".join(sorted(payload.raw_file_ids)), payload.force_rebuild, payload.min_confidence)
    job_store.create(job_id, JobType.alignment_build, "术语对齐任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在召回同义/别名候选并计算置信度")
    try:
        alignment, output_path, cache_hit = build_alignment(payload)
    except Exception as exc:  # noqa: BLE001 - keep normalized API error shape.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="术语对齐失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": job.message, "code": "ALIGNMENT_BUILD_FAILED", "detail": job.error}) from exc

    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="术语对齐已生成" if not cache_hit else "已返回现有术语对齐结果",
        result={
            "alignment_output_path": output_path,
            "raw_file_ids": alignment.raw_file_ids,
            "cluster_count": len(alignment.clusters),
            "candidate_count": len(alignment.candidates),
            "canonical_concept_count": len(alignment.canonical_concepts),
            "cache_hit": cache_hit,
        },
    )
    return AlignmentBuildResponse(job=job, alignment_output_path=output_path, alignment=alignment)


@router.get("", response_model=AlignmentResponse)
def get_alignment(raw_file_ids: str | None = None) -> AlignmentResponse:
    ids = [item.strip() for item in raw_file_ids.split(",") if item.strip()] if raw_file_ids else []
    alignment = load_alignment(sorted(ids)) if ids else load_latest_alignment()
    if alignment is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "术语对齐结果不存在，请先构建", "code": "ALIGNMENT_NOT_FOUND", "detail": raw_file_ids},
        )
    return alignment
