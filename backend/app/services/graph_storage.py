from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.models.schemas import Chunk, GraphNodeDetailResponse, GraphResponse, KnowledgeEdge, KnowledgeNode
from app.services.parsed_storage import load_parsed_textbook


def graph_path(raw_file_id: str) -> Path:
    return settings.graph_data_dir / f"{raw_file_id}.json"


def save_graph(graph: GraphResponse) -> Path:
    path = graph_path(graph.raw_file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_graph(raw_file_id: str) -> GraphResponse | None:
    path = graph_path(raw_file_id)
    if not path.exists():
        return None
    return GraphResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_latest_graph() -> GraphResponse | None:
    if not settings.graph_data_dir.exists():
        return None
    paths = sorted(settings.graph_data_dir.glob("raw_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return None
    return GraphResponse.model_validate_json(paths[0].read_text(encoding="utf-8"))


def find_node_detail(node_id: str) -> GraphNodeDetailResponse | None:
    if not settings.graph_data_dir.exists():
        return None
    for path in sorted(settings.graph_data_dir.glob("raw_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        graph = GraphResponse.model_validate_json(path.read_text(encoding="utf-8"))
        node = next((item for item in graph.nodes if item.id == node_id), None)
        if node is None:
            continue
        edges = _edges_for_node(graph.edges, node_id)
        related_nodes = _related_nodes(graph.nodes, edges, node_id)
        evidence_chunks = _evidence_chunks(graph.raw_file_id, node.evidence_chunk_ids)
        return GraphNodeDetailResponse(
            node=node,
            edges=edges,
            related_nodes=related_nodes,
            evidence_chunks=evidence_chunks,
            graph_id=graph.id,
            raw_file_id=graph.raw_file_id,
        )
    return None


def _edges_for_node(edges: list[KnowledgeEdge], node_id: str) -> list[KnowledgeEdge]:
    return [edge for edge in edges if edge.source_node_id == node_id or edge.target_node_id == node_id]


def _related_nodes(nodes: list[KnowledgeNode], edges: list[KnowledgeEdge], node_id: str) -> list[KnowledgeNode]:
    related_ids = {
        edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
        for edge in edges
    }
    node_by_id = {node.id: node for node in nodes}
    return [node_by_id[related_id] for related_id in related_ids if related_id in node_by_id]


def _evidence_chunks(raw_file_id: str, chunk_ids: list[str]) -> list[Chunk]:
    parsed = load_parsed_textbook(raw_file_id)
    if parsed is None:
        return []
    chunk_by_id = {chunk.id: chunk for chunk in parsed.chunks}
    return [chunk_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunk_by_id]
