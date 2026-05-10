from __future__ import annotations

from app.models.schemas import (
    Chunk,
    GraphBuildRequest,
    GraphResponse,
    KnowledgeEdge,
    KnowledgeNode,
    LayeredGraphBuildRequest,
    LayeredGraphEdge,
    LayeredGraphLayer,
    LayeredGraphLayerStatus,
    LayeredGraphLayerType,
    LayeredGraphNode,
    LayeredGraphResponse,
    ParsedTextbook,
    SourceLocator,
)
from app.services.converted_textbook_importer import quote_hash, stable_id
from app.services.graph_storage import load_graph
from app.services.knowledge_graph_builder import build_knowledge_graph
from app.services.layered_graph_storage import load_layered_graph, save_layered_graph
from app.services.parsed_storage import load_parsed_textbook


LAYER_ORDER = [
    LayeredGraphLayerType.document_tree,
    LayeredGraphLayerType.concept_kg,
    LayeredGraphLayerType.alias_alignment,
    LayeredGraphLayerType.evidence_graph,
    LayeredGraphLayerType.integration_decision,
    LayeredGraphLayerType.teacher_edit,
    LayeredGraphLayerType.graphrag_retrieval,
]
READY_LAYERS = {
    LayeredGraphLayerType.document_tree,
    LayeredGraphLayerType.concept_kg,
    LayeredGraphLayerType.evidence_graph,
}
LAYER_DISPLAY_NAMES = {
    LayeredGraphLayerType.document_tree: "Document Tree",
    LayeredGraphLayerType.concept_kg: "Concept KG",
    LayeredGraphLayerType.alias_alignment: "Alias / Alignment Graph",
    LayeredGraphLayerType.evidence_graph: "Evidence Graph",
    LayeredGraphLayerType.integration_decision: "Integration Decision Graph",
    LayeredGraphLayerType.teacher_edit: "Teacher Edit Graph",
    LayeredGraphLayerType.graphrag_retrieval: "GraphRAG Retrieval Layer",
}
RESERVED_STAGE = {
    LayeredGraphLayerType.alias_alignment: "00 阶段 7：术语对齐与去重",
    LayeredGraphLayerType.integration_decision: "00 阶段 8：压缩与整合决策",
    LayeredGraphLayerType.teacher_edit: "00 阶段 10：教师编辑与再次整合",
    LayeredGraphLayerType.graphrag_retrieval: "00 阶段 9：GraphRAG 问答",
}


def build_layered_graph(request: LayeredGraphBuildRequest) -> tuple[LayeredGraphResponse, str, bool]:
    existing = load_layered_graph(request.raw_file_id)
    if existing is not None and not request.force_rebuild:
        return existing, str(save_layered_graph(existing)), True

    parsed = load_parsed_textbook(request.raw_file_id)
    if parsed is None:
        raise ValueError(f"Parsed textbook not found: {request.raw_file_id}")

    graph = _load_or_build_concept_graph(request)
    nodes: list[LayeredGraphNode] = []
    edges: list[LayeredGraphEdge] = []
    seen_edge_ids: set[str] = set()

    document_refs = _build_document_tree(parsed, nodes, edges, seen_edge_ids)
    concept_refs = _build_concept_kg(parsed, graph, nodes, edges, seen_edge_ids)
    _build_evidence_graph(parsed, graph, document_refs["chunks"], concept_refs, nodes, edges, seen_edge_ids)

    layers = _summarize_layers(nodes, edges)
    layered_graph = LayeredGraphResponse(
        id=stable_id("layered_graph", parsed.raw_file.id, parsed.id, graph.id, "stage6_v1"),
        raw_file_id=parsed.raw_file.id,
        title=parsed.raw_file.title,
        layers=layers,
        nodes=nodes,
        edges=edges,
        metadata={
            "builder": "stage6_layered_graph_builder",
            "parsed_textbook_id": parsed.id,
            "concept_graph_id": graph.id,
            "document_element_count": len(parsed.elements),
            "section_count": len(parsed.sections),
            "chunk_count": len(parsed.chunks),
            "concept_node_count": len(graph.nodes),
            "concept_edge_count": len(graph.edges),
            "stage_boundary": "阶段 6 只构建层结构；术语对齐、压缩决策、GraphRAG 和教师编辑保持 reserved。",
        },
    )
    output_path = save_layered_graph(layered_graph)
    return layered_graph, str(output_path), False


def _load_or_build_concept_graph(request: LayeredGraphBuildRequest) -> GraphResponse:
    graph = load_graph(request.raw_file_id)
    if graph is not None:
        return graph
    if not request.build_missing_concept_graph:
        raise ValueError(f"Concept graph not found: {request.raw_file_id}")
    graph, _output_path, _cache_hit = build_knowledge_graph(
        GraphBuildRequest(
            raw_file_id=request.raw_file_id,
            force_rebuild=False,
            max_sections=request.max_sections,
            max_nodes_per_section=request.max_nodes_per_section,
            use_llm=request.use_llm,
        )
    )
    return graph


def _build_document_tree(
    parsed: ParsedTextbook,
    nodes: list[LayeredGraphNode],
    edges: list[LayeredGraphEdge],
    seen_edge_ids: set[str],
) -> dict[str, dict[str, str]]:
    raw_file = parsed.raw_file
    raw_node_id = stable_id("layer_node", raw_file.id, LayeredGraphLayerType.document_tree.value, raw_file.id)
    nodes.append(
        LayeredGraphNode(
            id=raw_node_id,
            layer_type=LayeredGraphLayerType.document_tree,
            label=raw_file.title,
            node_type="RawFile",
            ref_id=raw_file.id,
            source_locator=_raw_file_locator(parsed),
            metadata={
                "format": raw_file.format,
                "source_type": raw_file.source_type,
                "page_count": raw_file.page_count,
                "text_char_count": raw_file.text_char_count,
            },
        )
    )

    section_node_ids: dict[str, str] = {}
    element_node_ids: dict[str, str] = {}
    chunk_node_ids: dict[str, str] = {}

    for section in parsed.sections:
        node_id = stable_id("layer_node", raw_file.id, LayeredGraphLayerType.document_tree.value, section.id)
        section_node_ids[section.id] = node_id
        nodes.append(
            LayeredGraphNode(
                id=node_id,
                layer_type=LayeredGraphLayerType.document_tree,
                label=section.title,
                node_type=f"Section:{section.section_type.value}",
                ref_id=section.id,
                source_locator=section.source_locator,
                evidence_chunk_ids=[],
                metadata={
                    "level": section.level,
                    "order_index": section.order_index,
                    "parent_section_id": section.parent_section_id,
                    "char_count": section.char_count,
                },
            )
        )

    for section in parsed.sections:
        parent_node_id = section_node_ids.get(section.parent_section_id or "") or raw_node_id
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.document_tree,
                parent_node_id,
                section_node_ids[section.id],
                "CONTAINS",
                section.source_locator,
                ref_id=section.id,
                metadata={"target_ref_type": "Section"},
            ),
        )

    sorted_sections = sorted(parsed.sections, key=lambda item: item.order_index)
    for previous, current in zip(sorted_sections, sorted_sections[1:]):
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.document_tree,
                section_node_ids[previous.id],
                section_node_ids[current.id],
                "NEXT",
                current.source_locator,
                ref_id=current.id,
                metadata={"target_ref_type": "Section"},
            ),
        )
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.document_tree,
                section_node_ids[current.id],
                section_node_ids[previous.id],
                "PREVIOUS",
                previous.source_locator,
                ref_id=previous.id,
                metadata={"target_ref_type": "Section"},
            ),
        )

    for element in parsed.elements:
        node_id = stable_id("layer_node", raw_file.id, LayeredGraphLayerType.document_tree.value, element.id)
        element_node_ids[element.id] = node_id
        nodes.append(
            LayeredGraphNode(
                id=node_id,
                layer_type=LayeredGraphLayerType.document_tree,
                label=f"{element.type.value} #{element.order_index + 1}",
                node_type=f"DocumentElement:{element.type.value}",
                ref_id=element.id,
                source_locator=element.source_locator,
                metadata={
                    "order_index": element.order_index,
                    "parent_section_id": element.parent_section_id,
                    "char_count": element.char_count,
                },
            )
        )
        parent_node_id = section_node_ids.get(element.parent_section_id or "") or raw_node_id
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.document_tree,
                parent_node_id,
                node_id,
                "HAS_ELEMENT",
                element.source_locator,
                ref_id=element.id,
                metadata={"target_ref_type": "DocumentElement"},
            ),
        )

    chunks_by_section: dict[str, list[Chunk]] = {}
    for chunk in parsed.chunks:
        node_id = stable_id("layer_node", raw_file.id, LayeredGraphLayerType.document_tree.value, chunk.id)
        chunk_node_ids[chunk.id] = node_id
        chunks_by_section.setdefault(chunk.section_id, []).append(chunk)
        nodes.append(
            LayeredGraphNode(
                id=node_id,
                layer_type=LayeredGraphLayerType.document_tree,
                label=f"Chunk {chunk.order_index + 1}",
                node_type="Chunk",
                ref_id=chunk.id,
                source_locator=chunk.source_locator,
                evidence_chunk_ids=[chunk.id],
                metadata={
                    "section_id": chunk.section_id,
                    "order_index": chunk.order_index,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "char_count": chunk.char_count,
                },
            )
        )
        parent_node_id = section_node_ids.get(chunk.section_id) or raw_node_id
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.document_tree,
                parent_node_id,
                node_id,
                "HAS_CHUNK",
                chunk.source_locator,
                ref_id=chunk.id,
                evidence_chunk_ids=[chunk.id],
                metadata={"target_ref_type": "Chunk"},
            ),
        )

    for section_chunks in chunks_by_section.values():
        ordered_chunks = sorted(section_chunks, key=lambda item: item.order_index)
        for previous, current in zip(ordered_chunks, ordered_chunks[1:]):
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.document_tree,
                    chunk_node_ids[previous.id],
                    chunk_node_ids[current.id],
                    "NEXT",
                    current.source_locator,
                    ref_id=current.id,
                    evidence_chunk_ids=[current.id],
                    metadata={"target_ref_type": "Chunk"},
                ),
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.document_tree,
                    chunk_node_ids[current.id],
                    chunk_node_ids[previous.id],
                    "PREVIOUS",
                    previous.source_locator,
                    ref_id=previous.id,
                    evidence_chunk_ids=[previous.id],
                    metadata={"target_ref_type": "Chunk"},
                ),
            )

    return {
        "raw": {raw_file.id: raw_node_id},
        "sections": section_node_ids,
        "elements": element_node_ids,
        "chunks": chunk_node_ids,
    }


def _build_concept_kg(
    parsed: ParsedTextbook,
    graph: GraphResponse,
    nodes: list[LayeredGraphNode],
    edges: list[LayeredGraphEdge],
    seen_edge_ids: set[str],
) -> dict[str, str]:
    concept_node_ids: dict[str, str] = {}
    for node in graph.nodes:
        node_id = stable_id("layer_node", parsed.raw_file.id, LayeredGraphLayerType.concept_kg.value, node.id)
        concept_node_ids[node.id] = node_id
        nodes.append(
            LayeredGraphNode(
                id=node_id,
                layer_type=LayeredGraphLayerType.concept_kg,
                label=node.name,
                node_type=node.node_type.value,
                ref_id=node.id,
                source_locator=node.source_locator,
                evidence_chunk_ids=node.evidence_chunk_ids,
                confidence=node.confidence,
                metadata={
                    **node.metadata,
                    "definition": node.definition,
                    "aliases": node.aliases,
                },
            )
        )

    for edge in graph.edges:
        source_node_id = concept_node_ids.get(edge.source_node_id)
        target_node_id = concept_node_ids.get(edge.target_node_id)
        if source_node_id is None or target_node_id is None:
            continue
        _append_edge(
            edges,
            seen_edge_ids,
            _layer_edge(
                parsed.raw_file.id,
                LayeredGraphLayerType.concept_kg,
                source_node_id,
                target_node_id,
                edge.relation_type.value,
                edge.source_locator,
                ref_id=edge.id,
                evidence_chunk_ids=edge.evidence_chunk_ids,
                confidence=edge.confidence,
                metadata={
                    **edge.metadata,
                    "description": edge.description,
                    "source_knowledge_edge_id": edge.id,
                },
            ),
        )
    return concept_node_ids


def _build_evidence_graph(
    parsed: ParsedTextbook,
    graph: GraphResponse,
    chunk_node_ids: dict[str, str],
    concept_node_ids: dict[str, str],
    nodes: list[LayeredGraphNode],
    edges: list[LayeredGraphEdge],
    seen_edge_ids: set[str],
) -> None:
    chunk_by_id = {chunk.id: chunk for chunk in parsed.chunks}
    node_by_id = {node.id: node for node in graph.nodes}
    source_quote_node_ids: dict[tuple[str, str], str] = {}

    for node in graph.nodes:
        source_node_id = concept_node_ids.get(node.id)
        if source_node_id is None:
            continue
        quote = str(node.metadata.get("source_quote") or node.definition or node.name)
        for chunk_id in node.evidence_chunk_ids:
            chunk = chunk_by_id.get(chunk_id)
            target_node_id = chunk_node_ids.get(chunk_id)
            if chunk is None or target_node_id is None:
                continue
            quote_node_id = _ensure_source_quote_node(
                parsed,
                chunk,
                quote,
                "KnowledgeNode",
                node.id,
                source_quote_node_ids,
                nodes,
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    source_node_id,
                    target_node_id,
                    "EVIDENCED_BY",
                    chunk.source_locator,
                    ref_id=node.id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=node.confidence,
                    metadata={"evidence_for": "KnowledgeNode", "knowledge_node_id": node.id},
                ),
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    source_node_id,
                    quote_node_id,
                    "HAS_SOURCE_QUOTE",
                    chunk.source_locator,
                    ref_id=node.id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=node.confidence,
                    metadata={"evidence_for": "KnowledgeNode", "knowledge_node_id": node.id},
                ),
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    quote_node_id,
                    target_node_id,
                    "DERIVED_FROM",
                    chunk.source_locator,
                    ref_id=chunk_id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=node.confidence,
                    metadata={"evidence_for": "KnowledgeNode", "knowledge_node_id": node.id},
                ),
            )

    for edge in graph.edges:
        evidence_node_id = stable_id("layer_node", parsed.raw_file.id, LayeredGraphLayerType.evidence_graph.value, edge.id)
        source_node = node_by_id.get(edge.source_node_id)
        target_node = node_by_id.get(edge.target_node_id)
        edge_quote = str(edge.metadata.get("source_quote") or edge.description or edge.id)
        nodes.append(
            LayeredGraphNode(
                id=evidence_node_id,
                layer_type=LayeredGraphLayerType.evidence_graph,
                label=_edge_evidence_label(edge, source_node, target_node),
                node_type="KnowledgeEdgeEvidence",
                ref_id=edge.id,
                source_locator=edge.source_locator,
                evidence_chunk_ids=edge.evidence_chunk_ids,
                confidence=edge.confidence,
                metadata={
                    "relation_type": edge.relation_type.value,
                    "description": edge.description,
                    "source_quote": edge.metadata.get("source_quote"),
                    "source_knowledge_edge_id": edge.id,
                },
            )
        )

        source_concept_id = concept_node_ids.get(edge.source_node_id)
        target_concept_id = concept_node_ids.get(edge.target_node_id)
        if source_concept_id is not None:
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    source_concept_id,
                    evidence_node_id,
                    "RELATION_SOURCE",
                    edge.source_locator,
                    ref_id=edge.id,
                    evidence_chunk_ids=edge.evidence_chunk_ids,
                    confidence=edge.confidence,
                ),
            )
        if target_concept_id is not None:
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    evidence_node_id,
                    target_concept_id,
                    "RELATION_TARGET",
                    edge.source_locator,
                    ref_id=edge.id,
                    evidence_chunk_ids=edge.evidence_chunk_ids,
                    confidence=edge.confidence,
                ),
            )

        for chunk_id in edge.evidence_chunk_ids:
            chunk = chunk_by_id.get(chunk_id)
            chunk_node_id = chunk_node_ids.get(chunk_id)
            if chunk is None or chunk_node_id is None:
                continue
            quote_node_id = _ensure_source_quote_node(
                parsed,
                chunk,
                edge_quote,
                "KnowledgeEdge",
                edge.id,
                source_quote_node_ids,
                nodes,
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    evidence_node_id,
                    quote_node_id,
                    "HAS_SOURCE_QUOTE",
                    chunk.source_locator,
                    ref_id=edge.id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=edge.confidence,
                    metadata={"evidence_for": "KnowledgeEdge", "knowledge_edge_id": edge.id},
                ),
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    evidence_node_id,
                    chunk_node_id,
                    "EVIDENCED_BY",
                    chunk.source_locator,
                    ref_id=edge.id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=edge.confidence,
                    metadata={"evidence_for": "KnowledgeEdge", "knowledge_edge_id": edge.id},
                ),
            )
            _append_edge(
                edges,
                seen_edge_ids,
                _layer_edge(
                    parsed.raw_file.id,
                    LayeredGraphLayerType.evidence_graph,
                    quote_node_id,
                    chunk_node_id,
                    "DERIVED_FROM",
                    chunk.source_locator,
                    ref_id=chunk_id,
                    evidence_chunk_ids=[chunk_id],
                    confidence=edge.confidence,
                    metadata={"evidence_for": "KnowledgeEdge", "knowledge_edge_id": edge.id},
                ),
            )


def _raw_file_locator(parsed: ParsedTextbook) -> SourceLocator:
    raw_file = parsed.raw_file
    return SourceLocator(
        raw_file_id=raw_file.id,
        source_path=raw_file.storage_path,
        source_type=raw_file.source_type,
        locator_text=raw_file.title,
        page_start=1 if raw_file.page_count else None,
        page_end=raw_file.page_count,
        quote_hash=raw_file.sha256,
    )


def _ensure_source_quote_node(
    parsed: ParsedTextbook,
    chunk: Chunk,
    quote: str,
    evidence_for: str,
    ref_id: str,
    source_quote_node_ids: dict[tuple[str, str], str],
    nodes: list[LayeredGraphNode],
) -> str:
    clean_quote = _trim_quote(quote)
    key = (chunk.id, quote_hash(clean_quote))
    existing = source_quote_node_ids.get(key)
    if existing is not None:
        return existing

    node_id = stable_id("layer_node", parsed.raw_file.id, LayeredGraphLayerType.evidence_graph.value, "source_quote", chunk.id, key[1])
    source_quote_node_ids[key] = node_id
    nodes.append(
        LayeredGraphNode(
            id=node_id,
            layer_type=LayeredGraphLayerType.evidence_graph,
            label=clean_quote,
            node_type="SourceQuote",
            ref_id=ref_id,
            source_locator=chunk.source_locator,
            evidence_chunk_ids=[chunk.id],
            confidence=1.0,
            metadata={
                "quote": clean_quote,
                "quote_hash": key[1],
                "evidence_for": evidence_for,
                "chunk_id": chunk.id,
            },
        )
    )
    return node_id


def _layer_edge(
    raw_file_id: str,
    layer_type: LayeredGraphLayerType,
    source_node_id: str,
    target_node_id: str,
    relation_type: str,
    source_locator: SourceLocator,
    ref_id: str | None = None,
    evidence_chunk_ids: list[str] | None = None,
    confidence: float = 1.0,
    metadata: dict[str, object] | None = None,
) -> LayeredGraphEdge:
    edge_id = stable_id("layer_edge", raw_file_id, layer_type.value, source_node_id, target_node_id, relation_type, ref_id or "")
    return LayeredGraphEdge(
        id=edge_id,
        layer_type=layer_type,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relation_type=relation_type,
        ref_id=ref_id,
        source_locator=source_locator,
        evidence_chunk_ids=evidence_chunk_ids or [],
        confidence=confidence,
        metadata=metadata or {},
    )


def _append_edge(edges: list[LayeredGraphEdge], seen_edge_ids: set[str], edge: LayeredGraphEdge) -> None:
    if edge.id in seen_edge_ids:
        return
    edges.append(edge)
    seen_edge_ids.add(edge.id)


def _edge_evidence_label(edge: KnowledgeEdge, source_node: KnowledgeNode | None, target_node: KnowledgeNode | None) -> str:
    source = source_node.name if source_node else edge.source_node_id
    target = target_node.name if target_node else edge.target_node_id
    return f"{source} {edge.relation_type.value} {target}"


def _trim_quote(text: str, limit: int = 180) -> str:
    return " ".join(text.split())[:limit]


def _summarize_layers(nodes: list[LayeredGraphNode], edges: list[LayeredGraphEdge]) -> list[LayeredGraphLayer]:
    layers: list[LayeredGraphLayer] = []
    for layer_type in LAYER_ORDER:
        node_count = sum(1 for node in nodes if node.layer_type == layer_type)
        edge_count = sum(1 for edge in edges if edge.layer_type == layer_type)
        status = LayeredGraphLayerStatus.ready if layer_type in READY_LAYERS else LayeredGraphLayerStatus.reserved
        metadata: dict[str, object] = {}
        if layer_type in RESERVED_STAGE:
            metadata["reserved_for"] = RESERVED_STAGE[layer_type]
            metadata["reason"] = "按 00 路线图阶段边界预留，不在阶段 6 中生成真实决策或跨教材对齐结果。"
        layers.append(
            LayeredGraphLayer(
                layer_type=layer_type,
                display_name=LAYER_DISPLAY_NAMES[layer_type],
                status=status,
                node_count=node_count,
                edge_count=edge_count,
                metadata=metadata,
            )
        )
    return layers
