from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field

from app.core.config import settings
from app.models.schemas import (
    AlignmentResponse,
    Chunk,
    GraphRagIntent,
    GraphRagNodeHit,
    GraphRagPath,
    GraphRagPathStep,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagStatus,
    GraphResponse,
    IntegrationDecision,
    IntegrationResponse,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeRelationType,
    RagCitation,
    RagQueryRequest,
    SourceLocator,
)
from app.services.alignment_storage import load_alignment, load_latest_alignment
from app.services.converted_textbook_importer import stable_id
from app.services.graph_storage import load_graph
from app.services.integration_storage import load_integration, load_latest_integration
from app.services.parsed_storage import load_parsed_textbook
from app.services.rag_index import get_rag_index_status, query_rag_index


NO_ANSWER = "当前知识库中未找到相关信息。"
MIN_NODE_SCORE = 1.2
PATH_RELATIONS = {
    KnowledgeRelationType.prerequisite_of,
    KnowledgeRelationType.causes,
    KnowledgeRelationType.leads_to,
    KnowledgeRelationType.explains,
    KnowledgeRelationType.is_a,
    KnowledgeRelationType.part_of,
    KnowledgeRelationType.contains,
    KnowledgeRelationType.contrasts_with,
    KnowledgeRelationType.applies_to,
}
PATH_RELATION_PRIORITY = {
    KnowledgeRelationType.prerequisite_of: 0,
    KnowledgeRelationType.causes: 1,
    KnowledgeRelationType.leads_to: 2,
    KnowledgeRelationType.explains: 3,
    KnowledgeRelationType.applies_to: 4,
    KnowledgeRelationType.part_of: 5,
    KnowledgeRelationType.is_a: 6,
    KnowledgeRelationType.contrasts_with: 7,
    KnowledgeRelationType.contains: 8,
}
PREREQUISITE_RELATIONS = {KnowledgeRelationType.prerequisite_of}
RELATION_INTENT_MARKERS = ("关系", "之间", "路径", "联系")
COMPARISON_MARKERS = ("差异", "不同", "区别", "对比", "两本教材", "说法")
DECISION_MARKERS = ("为什么合并", "为什么删除", "为什么移除", "为什么压缩", "系统为什么", "整合决策", "合并", "删除", "移除", "保留")
DEFINITION_MARKERS = ("是什么", "定义", "概念", "含义")
COVERAGE_MARKERS = ("哪些教材", "出现在哪", "在哪些", "哪里讲", "来源")
PREREQUISITE_MARKERS = ("前要先学", "先学", "前置", "基础", " prerequisite", "预备")


@dataclass(frozen=True)
class GraphRecord:
    graph: GraphResponse
    node_by_id: dict[str, KnowledgeNode]
    edge_by_id: dict[str, KnowledgeEdge]


@dataclass
class RetrievalContext:
    raw_file_ids: list[str]
    graphs: list[GraphRecord]
    alignment: AlignmentResponse | None
    integration: IntegrationResponse | None
    node_graph: dict[str, GraphRecord]
    aliases_by_node_id: dict[str, set[str]]
    canonical_by_node_id: dict[str, str]
    adjacency: dict[str, list[KnowledgeEdge]]
    reverse_adjacency: dict[str, list[KnowledgeEdge]]
    chunk_by_id: dict[str, Chunk] = field(default_factory=dict)
    chunk_textbook: dict[str, str] = field(default_factory=dict)
    chunk_chapter: dict[str, str | None] = field(default_factory=dict)


def get_graphrag_status(raw_file_ids: list[str] | None = None) -> GraphRagStatus:
    ids = sorted(raw_file_ids or [])
    graphs = _load_graph_records(ids)
    graph_ids = [record.graph.raw_file_id for record in graphs]
    alignment = _load_alignment(graph_ids)
    integration = _load_integration(graph_ids)
    node_count = sum(len(record.graph.nodes) for record in graphs)
    edge_count = sum(len(record.graph.edges) for record in graphs)
    rag_status = get_rag_index_status()
    status = "ready" if rag_status.status == "ready" and graphs else "partial" if graphs or rag_status.status == "ready" else "empty"
    return GraphRagStatus(
        status=status,
        rag_index_status=rag_status,
        graph_count=len(graphs),
        node_count=node_count,
        edge_count=edge_count,
        alignment_available=alignment is not None,
        integration_available=integration is not None,
        raw_file_ids=graph_ids,
        metadata={
            "retrieval": "chunk_node_path_decision",
            "requires": ["rag_index", "knowledge_graph"],
            "optional": ["alignment", "integration_decisions"],
        },
    )


def query_graphrag(request: GraphRagQueryRequest) -> GraphRagQueryResponse:
    context = _build_context(request.raw_file_ids)
    intent = _detect_intent(request.question)
    rag_response = query_rag_index(
        RagQueryRequest(
            question=request.question,
            top_k=max(request.top_k, min(20, request.top_k * 2)),
            raw_file_ids=context.raw_file_ids or request.raw_file_ids,
        )
    )
    rag_citations = list(rag_response.citations)
    rag_chunks = list(rag_response.source_chunks)
    terms = _recognize_terms(request.question, context)
    node_hits = _node_hits(request.question, terms, context, request.top_k)
    if intent == GraphRagIntent.hybrid and rag_citations and _max_query_coverage(rag_citations) < 0.45:
        rag_citations = []
        rag_chunks = []
    if _is_underconstrained_relation_question(request.question, intent, node_hits):
        rag_citations = []
        rag_chunks = []
        terms = []
        node_hits = []
    if not _has_grounded_seed(rag_citations, node_hits):
        terms = []
        node_hits = []
    paths = _paths_for_query(request, intent, terms, node_hits, context)
    decisions = _decisions_for_query(request, intent, terms, node_hits, context) if request.include_decisions else []
    citations, source_chunks = _reranked_evidence(rag_citations, rag_chunks, node_hits, paths, decisions, context, request.top_k)

    if not (citations or node_hits or paths or decisions):
        return GraphRagQueryResponse(
            question=request.question,
            intent=intent,
            answer=NO_ANSWER,
            metadata={
                "reason": "no_grounded_graph_or_chunk_match",
                "retrieval_chain": _retrieval_chain(),
                "recognized_terms": terms,
                "rag_reason": rag_response.metadata.get("reason"),
            },
        )

    answer = _build_answer(intent, request.question, terms, node_hits, paths, decisions, citations, source_chunks, context)
    return GraphRagQueryResponse(
        question=request.question,
        intent=intent,
        answer=answer,
        citations=citations,
        source_chunks=source_chunks,
        node_hits=node_hits,
        paths=paths,
        decisions=decisions,
        metadata={
            "retrieval": "graphrag_chunk_node_path_decision",
            "retrieval_chain": _retrieval_chain(),
            "recognized_terms": terms,
            "rag_matched_count": rag_response.metadata.get("matched_count", 0),
            "node_hit_count": len(node_hits),
            "path_count": len(paths),
            "decision_count": len(decisions),
            "alignment_available": context.alignment is not None,
            "integration_available": context.integration is not None,
            "raw_file_ids": context.raw_file_ids,
        },
    )


def _build_context(raw_file_ids: list[str]) -> RetrievalContext:
    graph_records = _load_graph_records(raw_file_ids)
    ids = sorted({record.graph.raw_file_id for record in graph_records})
    alignment = _load_alignment(ids)
    integration = _load_integration(ids)
    node_graph: dict[str, GraphRecord] = {}
    for record in graph_records:
        for node in record.graph.nodes:
            node_graph[node.id] = record
    aliases_by_node_id, canonical_by_node_id = _alias_maps(graph_records, alignment)
    adjacency, reverse_adjacency = _edge_maps(graph_records)
    context = RetrievalContext(
        raw_file_ids=ids,
        graphs=graph_records,
        alignment=alignment,
        integration=integration,
        node_graph=node_graph,
        aliases_by_node_id=aliases_by_node_id,
        canonical_by_node_id=canonical_by_node_id,
        adjacency=adjacency,
        reverse_adjacency=reverse_adjacency,
    )
    _load_chunks(context)
    return context


def _load_graph_records(raw_file_ids: list[str]) -> list[GraphRecord]:
    graphs: list[GraphResponse] = []
    if raw_file_ids:
        for raw_file_id in raw_file_ids:
            graph = load_graph(raw_file_id)
            if graph is not None:
                graphs.append(graph)
    elif settings.graph_data_dir.exists():
        for path in sorted(settings.graph_data_dir.glob("raw_*.json")):
            graphs.append(GraphResponse.model_validate_json(path.read_text(encoding="utf-8")))
    return [
        GraphRecord(
            graph=graph,
            node_by_id={node.id: node for node in graph.nodes},
            edge_by_id={edge.id: edge for edge in graph.edges},
        )
        for graph in graphs
    ]


def _load_alignment(raw_file_ids: list[str]) -> AlignmentResponse | None:
    if raw_file_ids:
        alignment = load_alignment(raw_file_ids)
        if alignment is not None:
            return alignment
    return load_latest_alignment()


def _load_integration(raw_file_ids: list[str]) -> IntegrationResponse | None:
    if raw_file_ids:
        integration = load_integration(raw_file_ids)
        if integration is not None:
            return integration
    return load_latest_integration()


def _load_chunks(context: RetrievalContext) -> None:
    for raw_file_id in context.raw_file_ids:
        parsed = load_parsed_textbook(raw_file_id)
        if parsed is None:
            continue
        section_by_id = {section.id: section for section in parsed.sections}
        for chunk in parsed.chunks:
            context.chunk_by_id[chunk.id] = chunk
            context.chunk_textbook[chunk.id] = parsed.raw_file.title
            section = section_by_id.get(chunk.section_id)
            context.chunk_chapter[chunk.id] = section.title if section is not None else None


def _alias_maps(
    graph_records: list[GraphRecord],
    alignment: AlignmentResponse | None,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    aliases: dict[str, set[str]] = {}
    canonical: dict[str, str] = {}
    for record in graph_records:
        for node in record.graph.nodes:
            node_aliases = {node.name, *node.aliases, _normalize(node.name)}
            aliases[node.id] = {item for item in node_aliases if item}
            canonical[node.id] = node.name
    if alignment is not None:
        for concept in alignment.canonical_concepts:
            for node_id in concept.member_node_ids:
                aliases.setdefault(node_id, set()).update({concept.canonical_name, *concept.aliases, *[_normalize(alias) for alias in concept.aliases]})
                canonical[node_id] = concept.canonical_name
        for alias in alignment.aliases:
            for node_id in alias.node_ids:
                aliases.setdefault(node_id, set()).update({alias.alias, alias.canonical_name, _normalize(alias.alias), _normalize(alias.canonical_name)})
                canonical[node_id] = alias.canonical_name
    return aliases, canonical


def _edge_maps(graph_records: list[GraphRecord]) -> tuple[dict[str, list[KnowledgeEdge]], dict[str, list[KnowledgeEdge]]]:
    adjacency: dict[str, list[KnowledgeEdge]] = {}
    reverse: dict[str, list[KnowledgeEdge]] = {}
    for record in graph_records:
        for edge in record.graph.edges:
            adjacency.setdefault(edge.source_node_id, []).append(edge)
            reverse.setdefault(edge.target_node_id, []).append(edge)
    return adjacency, reverse


def _detect_intent(question: str) -> GraphRagIntent:
    if any(marker in question for marker in DECISION_MARKERS):
        return GraphRagIntent.decision_review
    if any(marker in question for marker in COMPARISON_MARKERS):
        return GraphRagIntent.comparison
    if any(marker in question for marker in PREREQUISITE_MARKERS):
        return GraphRagIntent.prerequisite
    if any(marker in question for marker in COVERAGE_MARKERS):
        return GraphRagIntent.coverage
    if any(marker in question for marker in RELATION_INTENT_MARKERS):
        return GraphRagIntent.relation_path
    if any(marker in question for marker in DEFINITION_MARKERS):
        return GraphRagIntent.definition
    return GraphRagIntent.hybrid


def _recognize_terms(question: str, context: RetrievalContext) -> list[str]:
    normalized_question = _normalize(question)
    terms: list[str] = []
    for record in context.graphs:
        for node in record.graph.nodes:
            aliases = context.aliases_by_node_id.get(node.id, set())
            candidates = {node.name, context.canonical_by_node_id.get(node.id, node.name), *aliases}
            for candidate in sorted(candidates, key=len, reverse=True):
                if not candidate:
                    continue
                normalized_candidate = _normalize(candidate)
                if candidate in question or (len(normalized_candidate) >= 2 and normalized_candidate in normalized_question):
                    canonical = context.canonical_by_node_id.get(node.id, node.name)
                    if canonical not in terms:
                        terms.append(canonical)
                    break
    if terms:
        return terms[:6]

    question_tokens = set(_text_tokens(question))
    scored: list[tuple[int, str]] = []
    for record in context.graphs:
        for node in record.graph.nodes:
            node_tokens = set(_text_tokens(f"{node.name} {node.definition or ''}"))
            overlap = len(question_tokens.intersection(node_tokens))
            if overlap:
                scored.append((overlap, context.canonical_by_node_id.get(node.id, node.name)))
    return list(dict.fromkeys(term for _score, term in sorted(scored, reverse=True)))[:4]


def _node_hits(
    question: str,
    terms: list[str],
    context: RetrievalContext,
    top_k: int,
) -> list[GraphRagNodeHit]:
    question_tokens = set(_text_tokens(question))
    normalized_question = _normalize(question)
    scored: list[tuple[float, KnowledgeNode, GraphRecord, list[str], list[str]]] = []
    for record in context.graphs:
        for node in record.graph.nodes:
            aliases = context.aliases_by_node_id.get(node.id, set())
            canonical = context.canonical_by_node_id.get(node.id, node.name)
            matched_aliases = [
                alias
                for alias in sorted({node.name, canonical, *aliases}, key=len, reverse=True)
                if alias and (alias in question or _normalize(alias) in normalized_question)
            ]
            matched_terms = [term for term in terms if term == canonical or term in aliases or _normalize(term) in {_normalize(alias) for alias in aliases}]
            node_tokens = set(_text_tokens(f"{node.name} {node.definition or ''} {node.metadata.get('chapter') or ''}"))
            overlap = len(question_tokens.intersection(node_tokens))
            score = overlap * 0.45
            if matched_aliases:
                score += 3.5
            if matched_terms:
                score += 2.0
            if node.name in question:
                score += 2.0
            if canonical in question:
                score += 1.5
            if score >= MIN_NODE_SCORE:
                scored.append((score, node, record, matched_terms, matched_aliases))
    scored.sort(key=lambda item: (-item[0], item[1].name, item[2].graph.title))
    if not scored:
        return []
    max_score = scored[0][0] or 1.0
    hits: list[GraphRagNodeHit] = []
    seen: set[str] = set()
    for score, node, record, matched_terms, matched_aliases in scored:
        if node.id in seen:
            continue
        seen.add(node.id)
        hits.append(
            GraphRagNodeHit(
                node=node,
                raw_file_id=record.graph.raw_file_id,
                textbook=record.graph.title,
                score=round(min(1.0, score / max_score), 4),
                matched_terms=list(dict.fromkeys(matched_terms)),
                matched_aliases=list(dict.fromkeys(matched_aliases)),
                source_locator=node.source_locator,
                evidence_chunk_ids=list(node.evidence_chunk_ids),
                metadata={
                    "canonical_name": context.canonical_by_node_id.get(node.id, node.name),
                    "degree": len(context.adjacency.get(node.id, [])) + len(context.reverse_adjacency.get(node.id, [])),
                },
            )
        )
        if len(hits) >= max(top_k * 3, top_k):
            break
    return hits


def _has_grounded_seed(rag_citations: list[RagCitation], node_hits: list[GraphRagNodeHit]) -> bool:
    if rag_citations:
        return True
    return any(hit.matched_aliases for hit in node_hits)


def _max_query_coverage(citations: list[RagCitation]) -> float:
    coverage_values = [float(citation.metadata.get("query_coverage") or 0.0) for citation in citations]
    return max(coverage_values) if coverage_values else 0.0


def _is_underconstrained_relation_question(
    question: str,
    intent: GraphRagIntent,
    node_hits: list[GraphRagNodeHit],
) -> bool:
    if intent not in {GraphRagIntent.hybrid, GraphRagIntent.relation_path}:
        return False
    if not any(marker in question for marker in ("影响", "导致", "引起", "造成", "为什么", "如何")):
        return False
    exact_canonicals = {
        str(hit.metadata.get("canonical_name") or hit.node.name)
        for hit in node_hits
        if hit.matched_aliases
    }
    return len(exact_canonicals) < 2


def _paths_for_query(
    request: GraphRagQueryRequest,
    intent: GraphRagIntent,
    terms: list[str],
    node_hits: list[GraphRagNodeHit],
    context: RetrievalContext,
) -> list[GraphRagPath]:
    if not node_hits:
        return []
    if intent == GraphRagIntent.prerequisite:
        return _prerequisite_paths(node_hits, context)[: request.top_k]
    if intent == GraphRagIntent.relation_path or len(terms) >= 2:
        paths = _term_pair_paths(terms, node_hits, context, request.max_path_depth)
        if paths:
            return paths[: request.top_k]
    return _neighbor_paths(node_hits, context)[: request.top_k]


def _prerequisite_paths(node_hits: list[GraphRagNodeHit], context: RetrievalContext) -> list[GraphRagPath]:
    paths: list[GraphRagPath] = []
    for hit in node_hits[:8]:
        target = hit.node
        incoming = [
            edge
            for edge in context.reverse_adjacency.get(target.id, [])
            if edge.relation_type in PREREQUISITE_RELATIONS or "基础" in (edge.description or "")
        ]
        for edge in incoming:
            source = _node_for_id(edge.source_node_id, context)
            if source is None:
                continue
            paths.append(_path_from_edges([edge], context, "prerequisite", f"学习 {target.name} 前需要先掌握 {source.name}。"))
        paths.extend(_sentence_prerequisite_paths(target, context))
    return _dedupe_paths(paths)


def _sentence_prerequisite_paths(target: KnowledgeNode, context: RetrievalContext) -> list[GraphRagPath]:
    paths: list[GraphRagPath] = []
    target_names = {target.name, context.canonical_by_node_id.get(target.id, target.name)}
    for source in _nodes_in_same_graph(target.id, context):
        if source.id == target.id:
            continue
        if source.name.startswith(("是", "包括", "它")) or len(source.name) > 12:
            continue
        text = f"{source.definition or ''} {source.metadata.get('source_quote') or ''}"
        if not text or source.name not in text:
            continue
        if not any(target_name and target_name in text for target_name in target_names):
            continue
        if not any(marker in text for marker in ("基础", "前提", "依赖", "需要先")):
            continue
        if text.find(source.name) > text.find(target.name):
            continue
        if not re.search(rf"{re.escape(source.name)}.*(?:是|为).{{0,8}}{re.escape(target.name)}.*(?:基础|前提)", text):
            continue
        step = GraphRagPathStep(
            source_node_id=source.id,
            source_node_name=source.name,
            target_node_id=target.id,
            target_node_name=target.name,
            relation_type=KnowledgeRelationType.prerequisite_of,
            description=f"{source.name} 是学习 {target.name} 的基础。",
            confidence=min(source.confidence, target.confidence, 0.72),
            evidence_chunk_ids=list(dict.fromkeys([*source.evidence_chunk_ids, *target.evidence_chunk_ids])),
            source_locator=source.source_locator,
            metadata={"retrieval": "sentence_prerequisite_fallback"},
        )
        paths.append(
            GraphRagPath(
                id=stable_id("graphrag_path", "sentence_prerequisite", source.id, target.id),
                path_type="prerequisite",
                node_ids=[source.id, target.id],
                node_names=[source.name, target.name],
                steps=[step],
                evidence_chunk_ids=step.evidence_chunk_ids,
                confidence=step.confidence,
                reason=f"原文明确出现“{source.name} 是 {target.name} 的基础/前提”类表达。",
                metadata={"fallback": "source_sentence"},
            )
        )
    return paths


def _nodes_in_same_graph(node_id: str, context: RetrievalContext) -> list[KnowledgeNode]:
    record = context.node_graph.get(node_id)
    if record is None:
        return []
    return record.graph.nodes


def _term_pair_paths(
    terms: list[str],
    node_hits: list[GraphRagNodeHit],
    context: RetrievalContext,
    max_depth: int,
) -> list[GraphRagPath]:
    groups: list[list[GraphRagNodeHit]] = []
    for term in terms[:2]:
        normalized = _normalize(term)
        group = [
            hit
            for hit in node_hits
            if normalized in _normalize(hit.node.name)
            or normalized in _normalize(str(hit.metadata.get("canonical_name") or ""))
            or any(normalized in _normalize(alias) for alias in hit.matched_aliases)
        ]
        if group:
            groups.append(group[:4])
    if len(groups) < 2:
        groups = [node_hits[:4], node_hits[4:8]]
    if len(groups) < 2 or not groups[1]:
        return []

    paths: list[GraphRagPath] = []
    for left in groups[0]:
        for right in groups[1]:
            if left.node.id == right.node.id:
                continue
            edge_path = _shortest_edge_path(left.node.id, right.node.id, context, max_depth)
            if edge_path:
                paths.append(_path_from_edges(edge_path, context, "relation_path", f"{left.node.name} 与 {right.node.name} 存在图谱路径。"))
    return _dedupe_paths(paths)


def _neighbor_paths(node_hits: list[GraphRagNodeHit], context: RetrievalContext) -> list[GraphRagPath]:
    paths: list[GraphRagPath] = []
    for hit in node_hits[:5]:
        edges = [
            edge
            for edge in [*context.adjacency.get(hit.node.id, []), *context.reverse_adjacency.get(hit.node.id, [])]
            if edge.relation_type in PATH_RELATIONS
        ]
        for edge in sorted(edges, key=lambda item: (-item.confidence, item.relation_type.value))[:3]:
            paths.append(_path_from_edges([edge], context, "neighbor", f"{hit.node.name} 的相关知识路径。"))
    return _dedupe_paths(paths)


def _shortest_edge_path(
    source_node_id: str,
    target_node_id: str,
    context: RetrievalContext,
    max_depth: int,
) -> list[KnowledgeEdge]:
    queue: deque[tuple[str, list[KnowledgeEdge]]] = deque([(source_node_id, [])])
    visited = {source_node_id}
    while queue:
        current, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        edges = [*context.adjacency.get(current, []), *context.reverse_adjacency.get(current, [])]
        for edge in sorted(edges, key=lambda item: (PATH_RELATION_PRIORITY.get(item.relation_type, 99), -item.confidence)):
            if edge.relation_type not in PATH_RELATIONS:
                continue
            next_id = edge.target_node_id if edge.source_node_id == current else edge.source_node_id
            if next_id == target_node_id:
                return [*path, edge]
            if next_id in visited:
                continue
            visited.add(next_id)
            queue.append((next_id, [*path, edge]))
    return []


def _path_from_edges(edges: list[KnowledgeEdge], context: RetrievalContext, path_type: str, reason: str) -> GraphRagPath:
    steps: list[GraphRagPathStep] = []
    node_ids: list[str] = []
    node_names: list[str] = []
    evidence_chunk_ids: list[str] = []
    confidences: list[float] = []
    for edge in edges:
        source = _node_for_id(edge.source_node_id, context)
        target = _node_for_id(edge.target_node_id, context)
        if source is None or target is None:
            continue
        for node in (source, target):
            if node.id not in node_ids:
                node_ids.append(node.id)
                node_names.append(node.name)
        evidence_chunk_ids.extend(edge.evidence_chunk_ids)
        confidences.append(edge.confidence)
        steps.append(
            GraphRagPathStep(
                source_node_id=source.id,
                source_node_name=source.name,
                target_node_id=target.id,
                target_node_name=target.name,
                relation_type=edge.relation_type,
                description=edge.description,
                confidence=edge.confidence,
                evidence_chunk_ids=list(edge.evidence_chunk_ids),
                source_locator=edge.source_locator,
                metadata=edge.metadata,
            )
        )
    return GraphRagPath(
        id=stable_id("graphrag_path", path_type, *[edge.id for edge in edges]),
        path_type=path_type,
        node_ids=node_ids,
        node_names=node_names,
        steps=steps,
        evidence_chunk_ids=list(dict.fromkeys(evidence_chunk_ids)),
        confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        reason=reason,
        metadata={"edge_ids": [edge.id for edge in edges]},
    )


def _node_for_id(node_id: str, context: RetrievalContext) -> KnowledgeNode | None:
    record = context.node_graph.get(node_id)
    if record is None:
        return None
    return record.node_by_id.get(node_id)


def _decisions_for_query(
    request: GraphRagQueryRequest,
    intent: GraphRagIntent,
    terms: list[str],
    node_hits: list[GraphRagNodeHit],
    context: RetrievalContext,
) -> list[IntegrationDecision]:
    integration = context.integration
    if integration is None:
        return []
    requested_actions = _requested_decision_actions(request.question)
    term_norms = {_normalize(term) for term in terms}
    node_ids = {hit.node.id for hit in node_hits}
    matched: list[tuple[int, IntegrationDecision]] = []
    for decision in integration.decisions:
        score = 0
        if requested_actions and decision.action.value in requested_actions:
            score += 5
        if node_ids.intersection(decision.target_node_ids):
            score += 4
        names = _decision_names(decision, integration, context)
        if any(term and any(term in _normalize(name) for name in names) for term in term_norms):
            score += 3
        if intent == GraphRagIntent.decision_review and (requested_actions or score > 0):
            score += 1
        if score > 0:
            matched.append((score, decision))
    matched.sort(key=lambda item: (-item[0], item[1].action.value, item[1].id))
    return [decision for _score, decision in matched[: request.top_k]]


def _requested_decision_actions(question: str) -> set[str]:
    actions: set[str] = set()
    if any(marker in question for marker in ("合并", "去重")):
        actions.add("merge")
    if any(marker in question for marker in ("删除", "移除")):
        actions.add("remove")
    if "保留" in question:
        actions.add("keep")
    if any(marker in question for marker in ("补充", "进一步", "细化")):
        actions.add("refine")
    if any(marker in question for marker in ("冲突", "矛盾")):
        actions.add("conflict")
    return actions


def _decision_names(decision: IntegrationDecision, integration: IntegrationResponse, context: RetrievalContext) -> set[str]:
    names: set[str] = set()
    for node_id in decision.target_node_ids:
        node = _node_for_id(node_id, context)
        if node is not None:
            names.update({node.name, context.canonical_by_node_id.get(node_id, node.name)})
    for concept in integration.integrated_concepts:
        if set(concept.member_node_ids).intersection(decision.target_node_ids):
            names.add(concept.canonical_name)
    for value in ("source_node_name", "representative_node_name"):
        if decision.metadata.get(value):
            names.add(str(decision.metadata[value]))
    for name in decision.metadata.get("source_node_names", []) if isinstance(decision.metadata.get("source_node_names"), list) else []:
        names.add(str(name))
    return {name for name in names if name}


def _reranked_evidence(
    rag_citations: list[RagCitation],
    rag_chunks: list[Chunk],
    node_hits: list[GraphRagNodeHit],
    paths: list[GraphRagPath],
    decisions: list[IntegrationDecision],
    context: RetrievalContext,
    top_k: int,
) -> tuple[list[RagCitation], list[Chunk]]:
    citations: list[RagCitation] = []
    chunks: list[Chunk] = []
    seen_chunk_ids: set[str] = set()

    def add_chunk(chunk_id: str, score: float, metadata: dict[str, object]) -> None:
        chunk = context.chunk_by_id.get(chunk_id)
        if chunk is None or chunk.id in seen_chunk_ids:
            return
        seen_chunk_ids.add(chunk.id)
        chunks.append(chunk)
        citations.append(
            RagCitation(
                chunk_id=chunk.id,
                raw_file_id=chunk.raw_file_id,
                textbook=context.chunk_textbook.get(chunk.id, chunk.raw_file_id),
                chapter=context.chunk_chapter.get(chunk.id),
                source_locator=chunk.source_locator,
                relevance_score=round(max(0.0, min(1.0, score)), 4),
                quote=_best_quote(chunk.text),
                metadata=metadata,
            )
        )

    for citation, chunk in zip(rag_citations, rag_chunks, strict=False):
        if citation.chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(citation.chunk_id)
        citations.append(citation)
        chunks.append(chunk)

    for hit in node_hits:
        for chunk_id in hit.evidence_chunk_ids:
            add_chunk(chunk_id, hit.score * 0.92, {"retrieval": "graph_node_evidence", "node_id": hit.node.id, "node_name": hit.node.name})
    for path in paths:
        for chunk_id in path.evidence_chunk_ids:
            add_chunk(chunk_id, path.confidence * 0.88, {"retrieval": "graph_path_evidence", "path_id": path.id, "path_type": path.path_type})
    for decision in decisions:
        for chunk_id in decision.evidence_chunk_ids:
            add_chunk(chunk_id, decision.confidence * 0.86, {"retrieval": "integration_decision_evidence", "decision_id": decision.id, "action": decision.action.value})

    sorted_pairs = sorted(zip(citations, chunks, strict=False), key=lambda item: item[0].relevance_score, reverse=True)
    limited = sorted_pairs[: max(top_k, 1)]
    return [item[0] for item in limited], [item[1] for item in limited]


def _build_answer(
    intent: GraphRagIntent,
    question: str,
    terms: list[str],
    node_hits: list[GraphRagNodeHit],
    paths: list[GraphRagPath],
    decisions: list[IntegrationDecision],
    citations: list[RagCitation],
    source_chunks: list[Chunk],
    context: RetrievalContext,
) -> str:
    if intent == GraphRagIntent.decision_review and decisions:
        return _decision_answer(decisions, citations, context)
    if intent == GraphRagIntent.coverage and node_hits:
        return _coverage_answer(terms, node_hits)
    if intent == GraphRagIntent.comparison and node_hits:
        return _comparison_answer(terms, node_hits, context)
    if intent == GraphRagIntent.prerequisite and paths:
        return _path_answer("前置知识路径", paths, citations)
    if intent == GraphRagIntent.relation_path and paths:
        return _path_answer("关系路径", paths, citations)
    if intent == GraphRagIntent.definition and node_hits:
        return _definition_answer(node_hits, citations)
    return _hybrid_answer(question, node_hits, paths, decisions, citations, source_chunks)


def _definition_answer(node_hits: list[GraphRagNodeHit], citations: list[RagCitation]) -> str:
    lines: list[str] = []
    for hit in node_hits[:3]:
        locator = _locator_for_hit(hit)
        definition = _trim(hit.node.definition or hit.node.metadata.get("source_quote") or hit.node.name, 180)
        lines.append(f"{hit.node.name}：{definition} {locator}")
    if citations:
        lines.append(f"可展开原文证据：{_citation_marker(citations[0])}")
    return "\n".join(lines)


def _coverage_answer(terms: list[str], node_hits: list[GraphRagNodeHit]) -> str:
    grouped: dict[str, list[GraphRagNodeHit]] = {}
    for hit in node_hits:
        grouped.setdefault(hit.textbook, []).append(hit)
    term_text = "、".join(terms[:3]) or node_hits[0].node.name
    lines = [f"{term_text} 在以下教材/章节中出现："]
    for textbook, hits in sorted(grouped.items()):
        locators = []
        for hit in hits[:4]:
            chapter = hit.node.metadata.get("chapter") or hit.source_locator.locator_text
            locators.append(f"{chapter}（{hit.node.name}）")
        lines.append(f"- {textbook}：{'；'.join(locators)} {_locator_for_hit(hits[0])}")
    return "\n".join(lines)


def _comparison_answer(terms: list[str], node_hits: list[GraphRagNodeHit], context: RetrievalContext) -> str:
    grouped: dict[str, list[GraphRagNodeHit]] = {}
    for hit in node_hits:
        canonical = str(hit.metadata.get("canonical_name") or hit.node.name)
        if terms and canonical not in terms and not any(_normalize(term) in _normalize(canonical) for term in terms):
            continue
        grouped.setdefault(hit.textbook, []).append(hit)
    if len(grouped) < 2:
        grouped = {}
        for hit in node_hits[:6]:
            grouped.setdefault(hit.textbook, []).append(hit)
    lines = ["不同教材说法对比如下："]
    for textbook, hits in sorted(grouped.items()):
        hit = hits[0]
        definition = _trim(hit.node.definition or hit.node.metadata.get("source_quote") or hit.node.name, 160)
        lines.append(f"- {textbook}：{hit.node.name}，{definition} {_locator_for_hit(hit)}")
    if context.integration is not None:
        matched_concepts = [
            concept
            for concept in context.integration.integrated_concepts
            if any(node_id in {hit.node.id for hit in node_hits} for node_id in concept.member_node_ids)
        ]
        if matched_concepts:
            lines.append(f"整合视图将其归入：{matched_concepts[0].canonical_name}，但保留各来源证据。")
    return "\n".join(lines)


def _path_answer(title: str, paths: list[GraphRagPath], citations: list[RagCitation]) -> str:
    lines = [f"{title}："]
    for path in paths[:3]:
        if not path.steps:
            continue
        step_text = " -> ".join(
            f"{step.source_node_name} --{step.relation_type.value}--> {step.target_node_name}"
            for step in path.steps
        )
        lines.append(f"- {step_text}；依据：{path.reason}")
    if citations:
        lines.append(f"原文证据：{_citation_marker(citations[0])}")
    return "\n".join(lines)


def _decision_answer(decisions: list[IntegrationDecision], citations: list[RagCitation], context: RetrievalContext) -> str:
    lines = ["相关整合决策如下："]
    for decision in decisions[:5]:
        names = sorted(_decision_names(decision, context.integration, context)) if context.integration is not None else []
        target = "、".join(names[:4]) or "相关节点"
        retained = f"；保留：{_trim(decision.retained_content, 100)}" if decision.retained_content else ""
        removed = f"；压缩/移出：{_trim(decision.removed_redundancy, 100)}" if decision.removed_redundancy else ""
        lines.append(f"- {decision.action.value} {target}：{decision.reason}{retained}{removed}")
    if citations:
        lines.append(f"决策证据可回到原文：{_citation_marker(citations[0])}")
    return "\n".join(lines)


def _hybrid_answer(
    question: str,
    node_hits: list[GraphRagNodeHit],
    paths: list[GraphRagPath],
    decisions: list[IntegrationDecision],
    citations: list[RagCitation],
    source_chunks: list[Chunk],
) -> str:
    lines: list[str] = []
    if node_hits:
        hit = node_hits[0]
        lines.append(f"命中的核心知识点是 {hit.node.name}：{_trim(hit.node.definition or hit.node.name, 160)} {_locator_for_hit(hit)}")
    if paths:
        step = paths[0].steps[0] if paths[0].steps else None
        if step is not None:
            lines.append(f"相关路径：{step.source_node_name} --{step.relation_type.value}--> {step.target_node_name}。")
    if decisions:
        lines.append(f"相关整合决策：{decisions[0].action.value}，原因是 {decisions[0].reason}")
    if citations:
        lines.append(f"引用：{_citation_marker(citations[0])}")
    elif source_chunks:
        lines.append(_trim(source_chunks[0].text, 180))
    if not lines:
        return NO_ANSWER
    return "\n".join(lines)


def _locator_for_hit(hit: GraphRagNodeHit) -> str:
    chapter = hit.node.metadata.get("chapter") or "未分章"
    return f"[{hit.textbook}, {chapter}, {hit.source_locator.locator_text}]"


def _citation_marker(citation: RagCitation) -> str:
    chapter = citation.chapter or "未分章"
    return f"[{citation.textbook}, {chapter}, {citation.source_locator.locator_text}]"


def _dedupe_paths(paths: list[GraphRagPath]) -> list[GraphRagPath]:
    seen: set[str] = set()
    unique: list[GraphRagPath] = []
    for path in paths:
        key = json.dumps({"nodes": path.node_ids, "steps": [step.model_dump(mode="json") for step in path.steps]}, ensure_ascii=False, sort_keys=True)
        if key in seen or not path.steps:
            continue
        seen.add(key)
        unique.append(path)
    return sorted(unique, key=lambda item: (-item.confidence, item.path_type, item.id))


def _retrieval_chain() -> list[str]:
    return [
        "term_recognition",
        "alias_expansion",
        "chunk_retrieval",
        "knowledge_node_retrieval",
        "graph_neighbor_or_path_expansion",
        "integration_decision_lookup",
        "evidence_rerank",
        "grounded_answer",
    ]


def _text_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    lowered = text.lower()
    tokens.extend(re.findall(r"[a-zA-Z0-9_]{2,}", lowered))
    for segment in re.findall(r"[\u4e00-\u9fa5]{2,}", text):
        tokens.extend(segment[index : index + 2] for index in range(max(0, len(segment) - 1)))
        tokens.extend(segment[index : index + 3] for index in range(max(0, len(segment) - 2)))
        if len(segment) <= 10:
            tokens.append(segment)
    stop_fragments = {"什么", "为什么", "如何", "怎么", "哪些", "关系", "定义", "教材", "系统"}
    return [token for token in tokens if token and token not in stop_fragments and not any(fragment in token for fragment in stop_fragments)]


def _normalize(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"（[^）]*）", "", value)
    value = re.sub(r"[\s_\-·,，。；;:：/\\()\[\]（）【】]+", "", value)
    return value.strip()


def _best_quote(text: str, limit: int = 180) -> str:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？!?；;])", text) if sentence.strip()]
    if not sentences:
        return _trim(text, limit)
    return _trim(sentences[0], limit)


def _trim(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip(" ，,；;。") + "…"
