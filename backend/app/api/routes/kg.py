from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    JobStatus,
    JobType,
    LayeredGraphBuildRequest,
    LayeredGraphBuildResponse,
    LayeredGraphResponse,
)
from app.services.converted_textbook_importer import stable_id
from app.services.job_store import job_store
from app.services.layered_graph_builder import build_layered_graph
from app.services.layered_graph_storage import load_latest_layered_graph, load_layered_graph


router = APIRouter(prefix="/kg", tags=["kg"])


@router.post("/layers/build", response_model=LayeredGraphBuildResponse)
def build_layered_kg(payload: LayeredGraphBuildRequest) -> LayeredGraphBuildResponse:
    job_id = stable_id("job", "layered_kg_build", payload.raw_file_id)
    job_store.create(job_id, JobType.layered_kg_build, "多层 KG 构建任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在构建 Document Tree / Concept KG / Evidence Graph")
    try:
        layered_graph, output_path, cache_hit = build_layered_graph(payload)
    except Exception as exc:  # noqa: BLE001 - normalize layered graph build failures for the API.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="多层 KG 构建失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": job.message, "code": "LAYERED_KG_BUILD_FAILED", "detail": job.error}) from exc

    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="多层 KG 已生成" if not cache_hit else "已返回现有多层 KG",
        result={
            "raw_file_id": layered_graph.raw_file_id,
            "layered_graph_output_path": output_path,
            "layer_count": len(layered_graph.layers),
            "node_count": len(layered_graph.nodes),
            "edge_count": len(layered_graph.edges),
            "cache_hit": cache_hit,
        },
    )
    return LayeredGraphBuildResponse(
        job=job,
        raw_file_id=layered_graph.raw_file_id,
        layered_graph_output_path=output_path,
        layered_graph=layered_graph,
    )


@router.get("/layers", response_model=LayeredGraphResponse)
def get_layered_kg(raw_file_id: str | None = None) -> LayeredGraphResponse:
    layered_graph = load_layered_graph(raw_file_id) if raw_file_id else load_latest_layered_graph()
    if layered_graph is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "多层 KG 不存在，请先构建", "code": "LAYERED_KG_NOT_FOUND", "detail": raw_file_id},
        )
    return layered_graph
