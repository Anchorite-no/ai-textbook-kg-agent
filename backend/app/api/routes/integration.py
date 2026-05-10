from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import IntegrationBuildRequest, IntegrationBuildResponse, IntegrationResponse, JobStatus, JobType
from app.services.converted_textbook_importer import stable_id
from app.services.integration_builder import build_integration
from app.services.integration_storage import load_integration, load_latest_integration
from app.services.job_store import job_store


router = APIRouter(prefix="/integration", tags=["integration"])


@router.post("/build", response_model=IntegrationBuildResponse)
def build_integration_decisions(payload: IntegrationBuildRequest) -> IntegrationBuildResponse:
    job_id = stable_id(
        "job",
        "integration_build",
        "|".join(sorted(payload.raw_file_ids)),
        payload.force_rebuild,
        payload.target_compression_ratio,
        payload.alignment_min_confidence,
    )
    job_store.create(job_id, JobType.integration_build, "跨教材整合与压缩任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在读取术语对齐和知识图谱")
    try:
        integration, output_path, cache_hit = build_integration(payload)
    except Exception as exc:  # noqa: BLE001 - keep normalized API error shape.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="跨教材整合与压缩失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": job.message, "code": "INTEGRATION_BUILD_FAILED", "detail": job.error}) from exc

    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="跨教材整合与压缩结果已生成" if not cache_hit else "已返回现有跨教材整合结果",
        result={
            "integration_output_path": output_path,
            "raw_file_ids": integration.raw_file_ids,
            "decision_count": len(integration.decisions),
            "integrated_node_count": len(integration.integrated_concepts),
            "compression_ratio": integration.compression_stats.compression_ratio,
            "target_compression_ratio": integration.compression_stats.target_compression_ratio,
            "cache_hit": cache_hit,
        },
    )
    return IntegrationBuildResponse(job=job, integration_output_path=output_path, integration=integration)


@router.get("", response_model=IntegrationResponse)
def get_integration(raw_file_ids: str | None = None) -> IntegrationResponse:
    ids = [item.strip() for item in raw_file_ids.split(",") if item.strip()] if raw_file_ids else []
    integration = load_integration(sorted(ids)) if ids else load_latest_integration()
    if integration is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "跨教材整合结果不存在，请先构建", "code": "INTEGRATION_NOT_FOUND", "detail": raw_file_ids},
        )
    return integration
