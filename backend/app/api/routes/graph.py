from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    GraphBuildRequest,
    GraphBuildResponse,
    GraphNodeDetailResponse,
    GraphResponse,
    JobStatus,
    JobType,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeRelationType,
)
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
    edge_budget = max(60, int(top_n * 2.35))
    if len(graph.nodes) <= top_n and len(graph.edges) <= edge_budget:
        return graph

    node_scores = _node_scores(graph.nodes, graph.edges)
    kept_ids = _select_display_node_ids(graph.nodes, graph.edges, node_scores, top_n)
    kept_edges = _select_display_edges(graph.edges, kept_ids, edge_budget)
    incident_ids = {edge.source_node_id for edge in kept_edges} | {edge.target_node_id for edge in kept_edges}

    connected_nodes = [node for node in graph.nodes if node.id in kept_ids and node.id in incident_ids]
    isolated_nodes = [node for node in graph.nodes if node.id in kept_ids and node.id not in incident_ids]
    isolated_keep = max(6, min(18, top_n // 10))
    isolated_nodes = sorted(isolated_nodes, key=lambda item: node_scores.get(item.id, 0), reverse=True)[:isolated_keep]
    kept_nodes = sorted(
        [*connected_nodes, *isolated_nodes],
        key=lambda item: (-node_scores.get(item.id, 0), item.name),
    )
    kept_ids = {node.id for node in kept_nodes}
    kept_edges = [edge for edge in kept_edges if edge.source_node_id in kept_ids and edge.target_node_id in kept_ids]
    return graph.model_copy(
        update={
            "nodes": kept_nodes,
            "edges": kept_edges,
            "metadata": {
                **graph.metadata,
                "top_n": top_n,
                "full_node_count": len(graph.nodes),
                "full_edge_count": len(graph.edges),
                "display_node_count": len(kept_nodes),
                "display_edge_count": len(kept_edges),
                "display_strategy": "semantic_focus_with_evidence_links",
                "display_edge_budget": edge_budget,
            },
        }
    )


def _node_scores(nodes: list[KnowledgeNode], edges: list[KnowledgeEdge]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for node in nodes:
        frequency = _as_float(node.metadata.get("frequency"), 1.0)
        method_bonus = 2.0 if str(node.metadata.get("extraction_method", "")).lower() == "llm" else 0.0
        verified_bonus = 0.9 if node.metadata.get("source_quote_verified") is True else 0.0
        type_bonus = {
            "Disease": 2.0,
            "Mechanism": 1.8,
            "Process": 1.6,
            "Structure": 1.4,
            "Function": 1.4,
            "Diagnosis": 1.2,
            "Treatment": 1.2,
            "Concept": 1.0,
            "Term": 0.4,
        }.get(node.node_type.value, 0.8)
        scores[node.id] = node.confidence * 2.0 + min(frequency, 10) * 0.7 + method_bonus + verified_bonus + type_bonus

    for edge in edges:
        score = _edge_score(edge)
        scores[edge.source_node_id] = scores.get(edge.source_node_id, 0.0) + score
        scores[edge.target_node_id] = scores.get(edge.target_node_id, 0.0) + score
    return scores


def _select_display_node_ids(
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
    node_scores: dict[str, float],
    top_n: int,
) -> set[str]:
    ranked_nodes = sorted(nodes, key=lambda item: (-node_scores.get(item.id, 0), item.name))
    if len(ranked_nodes) <= top_n:
        return {node.id for node in ranked_nodes}

    seed_count = min(top_n, max(24, int(top_n * 0.58)))
    selected = {node.id for node in ranked_nodes[:seed_count]}
    edges_by_node: dict[str, list[KnowledgeEdge]] = {}
    for edge in sorted(edges, key=_edge_score, reverse=True):
        edges_by_node.setdefault(edge.source_node_id, []).append(edge)
        edges_by_node.setdefault(edge.target_node_id, []).append(edge)

    ranked_ids = [node.id for node in ranked_nodes]
    while len(selected) < top_n:
        before = len(selected)
        for node_id in list(selected):
            for edge in edges_by_node.get(node_id, []):
                other_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
                if other_id not in selected:
                    selected.add(other_id)
                    break
            if len(selected) >= top_n:
                break
        if len(selected) == before:
            for node_id in ranked_ids:
                if node_id not in selected:
                    selected.add(node_id)
                    break
        if len(selected) == before:
            break
    return selected


def _select_display_edges(edges: list[KnowledgeEdge], kept_ids: set[str], edge_budget: int) -> list[KnowledgeEdge]:
    candidates = [edge for edge in edges if edge.source_node_id in kept_ids and edge.target_node_id in kept_ids]
    semantic = [edge for edge in candidates if not _is_contextual_edge(edge)]
    contextual = [edge for edge in candidates if _is_contextual_edge(edge)]
    selected: list[KnowledgeEdge] = []
    selected_ids: set[str] = set()
    degree: dict[str, int] = {}
    context_degree: dict[str, int] = {}

    def add(edge: KnowledgeEdge) -> None:
        selected.append(edge)
        selected_ids.add(edge.id)
        degree[edge.source_node_id] = degree.get(edge.source_node_id, 0) + 1
        degree[edge.target_node_id] = degree.get(edge.target_node_id, 0) + 1
        if _is_contextual_edge(edge):
            context_degree[edge.source_node_id] = context_degree.get(edge.source_node_id, 0) + 1
            context_degree[edge.target_node_id] = context_degree.get(edge.target_node_id, 0) + 1

    for edge in sorted(semantic, key=_edge_score, reverse=True):
        if len(selected) >= edge_budget:
            break
        if degree.get(edge.source_node_id, 0) >= 9 and degree.get(edge.target_node_id, 0) >= 9:
            continue
        add(edge)

    for edge in sorted(contextual, key=_edge_score, reverse=True):
        if len(selected) >= edge_budget:
            break
        if edge.id in selected_ids:
            continue
        source_degree = degree.get(edge.source_node_id, 0)
        target_degree = degree.get(edge.target_node_id, 0)
        source_context = context_degree.get(edge.source_node_id, 0)
        target_context = context_degree.get(edge.target_node_id, 0)
        connects_sparse_node = source_degree == 0 or target_degree == 0
        keeps_local_chain = source_context < 2 and target_context < 2 and _edge_score(edge) >= 0.45
        if connects_sparse_node or keeps_local_chain:
            add(edge)

    return selected


def _edge_score(edge: KnowledgeEdge) -> float:
    relation_weight = {
        KnowledgeRelationType.prerequisite_of: 2.4,
        KnowledgeRelationType.causes: 2.3,
        KnowledgeRelationType.leads_to: 2.2,
        KnowledgeRelationType.explains: 2.0,
        KnowledgeRelationType.is_a: 1.9,
        KnowledgeRelationType.part_of: 1.8,
        KnowledgeRelationType.applies_to: 1.7,
        KnowledgeRelationType.contains: 1.4,
        KnowledgeRelationType.contrasts_with: 1.6,
        KnowledgeRelationType.refines: 1.5,
        KnowledgeRelationType.parallel_with: 0.9,
        KnowledgeRelationType.mentioned_in: 0.45,
    }.get(edge.relation_type, 1.0)
    score = edge.confidence * relation_weight
    if _is_contextual_edge(edge):
        score *= 0.48
    if str(edge.metadata.get("extraction_method", "")).lower() == "llm":
        score += 0.75
    if edge.metadata.get("source_quote_verified") is True:
        score += 0.35
    if edge.evidence_chunk_ids:
        score += min(len(edge.evidence_chunk_ids), 3) * 0.08
    return score


def _is_contextual_edge(edge: KnowledgeEdge) -> bool:
    return edge.metadata.get("contextual_edge") is True or edge.relation_type == KnowledgeRelationType.mentioned_in


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
