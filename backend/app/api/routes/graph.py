from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import GraphBuildRequest, GraphBuildResponse, GraphNodeDetailResponse, GraphResponse, JobStatus, JobType
from app.services.graph_storage import find_node_detail, load_graph, load_latest_graph
from app.services.job_store import job_store
from app.services.knowledge_graph_builder import build_knowledge_graph
from app.services.converted_textbook_importer import stable_id


router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/build", response_model=GraphBuildResponse)
def build_graph(payload: GraphBuildRequest) -> GraphBuildResponse:
    job_id = stable_id("job", "graph_build", payload.raw_file_id)
    job_store.create(job_id, JobType.graph_build, "知识图谱构建任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在抽取知识点和关系")
    try:
        graph, output_path, cache_hit = build_knowledge_graph(payload)
    except Exception as exc:  # noqa: BLE001 - expose graph build failures through normalized API errors.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="知识图谱构建失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": job.message, "code": "GRAPH_BUILD_FAILED", "detail": job.error}) from exc

    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="知识图谱已生成" if not cache_hit else "已返回现有知识图谱",
        result={
            "raw_file_id": graph.raw_file_id,
            "graph_output_path": output_path,
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "cache_hit": cache_hit,
        },
    )
    return GraphBuildResponse(job=job, raw_file_id=graph.raw_file_id, graph_output_path=output_path, graph=graph)


@router.get("", response_model=GraphResponse)
def get_graph(
    mode: Literal["single"] = Query(default="single"),
    raw_file_id: str | None = None,
    top_n: int = Query(default=200, ge=1, le=1000),
) -> GraphResponse:
    if mode != "single":
        raise HTTPException(
            status_code=400,
            detail={"message": "当前计划 03 只支持单本教材图谱", "code": "GRAPH_MODE_NOT_SUPPORTED", "detail": mode},
        )
    graph = load_graph(raw_file_id) if raw_file_id else load_latest_graph()
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "知识图谱不存在，请先构建", "code": "GRAPH_NOT_FOUND", "detail": raw_file_id},
        )
    return _limit_graph(graph, top_n)


@router.get("/nodes/{node_id}", response_model=GraphNodeDetailResponse)
def get_graph_node(node_id: str) -> GraphNodeDetailResponse:
    detail = find_node_detail(node_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "知识节点不存在", "code": "NODE_NOT_FOUND", "detail": node_id},
        )
    return detail


def _limit_graph(graph: GraphResponse, top_n: int) -> GraphResponse:
    if len(graph.nodes) <= top_n:
        return graph
    kept_nodes = graph.nodes[:top_n]
    kept_ids = {node.id for node in kept_nodes}
    kept_edges = [edge for edge in graph.edges if edge.source_node_id in kept_ids and edge.target_node_id in kept_ids]
    return graph.model_copy(
        update={
            "nodes": kept_nodes,
            "edges": kept_edges,
            "metadata": {
                **graph.metadata,
                "top_n": top_n,
                "full_node_count": len(graph.nodes),
                "full_edge_count": len(graph.edges),
            },
        }
    )
