from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.schemas import (
    Chunk,
    GraphBuildRequest,
    GraphResponse,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeType,
    KnowledgeRelationType,
    ParsedTextbook,
    Section,
)
from app.services.converted_textbook_importer import quote_hash, stable_id
from app.services.graph_storage import load_graph, save_graph
from app.services.llm_cache import llm_cache
from app.services.llm_client import llm_client
from app.services.parsed_storage import load_parsed_textbook


PROMPT_VERSION = "kg_extract_v1"
MAX_SECTION_CHARS = 3000
TERM_PATTERN = re.compile(
    r"[\u4e00-\u9fa5A-Za-z0-9]{2,24}?(?:"
    r"电位|传导|细胞|组织|器官|系统|结构|功能|机制|过程|反应|作用|疾病|症状|诊断|治疗|"
    r"病变|炎症|感染|免疫|病毒|细菌|解剖|生理|病理|血管|神经|肌肉|淋巴|膜电位"
    r")"
)


@dataclass(frozen=True)
class NodeDraft:
    name: str
    definition: str
    category: str
    source_quote: str
    chunk: Chunk


@dataclass(frozen=True)
class EdgeDraft:
    source_name: str
    target_name: str
    relation_type: KnowledgeRelationType
    description: str
    source_quote: str
    chunk: Chunk


def build_knowledge_graph(request: GraphBuildRequest) -> tuple[GraphResponse, str, bool]:
    existing = load_graph(request.raw_file_id)
    if existing is not None and not request.force_rebuild:
        return existing, str(save_graph(existing)), True

    parsed = load_parsed_textbook(request.raw_file_id)
    if parsed is None:
        raise ValueError(f"Parsed textbook not found: {request.raw_file_id}")

    sections = _select_sections(parsed, request)
    chunks_by_section = _chunks_by_section(parsed)
    node_by_name: dict[str, KnowledgeNode] = {}
    edge_by_key: dict[tuple[str, str, KnowledgeRelationType], KnowledgeEdge] = {}
    llm_cache_hits = 0
    llm_calls = 0
    llm_errors = 0
    fallback_sections = 0

    for section in sections:
        section_chunks = chunks_by_section.get(section.id) or []
        if not section_chunks:
            continue
        text = _section_text(section, section_chunks)
        llm_payload: dict[str, Any] | None = None
        if request.use_llm:
            cache_key = f"{PROMPT_VERSION}:{parsed.raw_file.id}:{section.id}:{quote_hash(text)}"
            llm_payload = llm_cache.get(cache_key)
            if llm_payload is not None:
                llm_cache_hits += 1
            else:
                prompt = _build_prompt(section, text)
                try:
                    llm_payload = llm_client.extract_json(prompt)
                except Exception:
                    llm_errors += 1
                    llm_payload = None
                if llm_payload is not None:
                    llm_calls += 1
                    llm_cache.set(cache_key, llm_payload)

        if llm_payload is not None:
            node_drafts, edge_drafts = _drafts_from_llm(llm_payload, section_chunks, section)
        else:
            fallback_sections += 1
            node_drafts, edge_drafts = _fallback_drafts(section, section_chunks, request.max_nodes_per_section)

        section_node_ids: dict[str, str] = {}
        for draft in node_drafts[: request.max_nodes_per_section]:
            node = _merge_node(parsed, section, draft, node_by_name)
            section_node_ids[_normalize_name(draft.name)] = node.id

        for draft in edge_drafts:
            source_id = section_node_ids.get(_normalize_name(draft.source_name))
            target_id = section_node_ids.get(_normalize_name(draft.target_name))
            if not source_id or not target_id or source_id == target_id:
                continue
            edge = _build_edge(parsed, draft, source_id, target_id)
            key = (edge.source_node_id, edge.target_node_id, edge.relation_type)
            edge_by_key.setdefault(key, edge)

    nodes = sorted(node_by_name.values(), key=lambda item: (-int(item.metadata.get("frequency", 1)), item.name))
    edges = list(edge_by_key.values())
    graph = GraphResponse(
        id=stable_id("graph", parsed.raw_file.id, parsed.raw_file.sha256, PROMPT_VERSION),
        raw_file_id=parsed.raw_file.id,
        title=parsed.raw_file.title,
        nodes=nodes,
        edges=edges,
        metadata={
            "builder": "phase3_minimal_kg_builder",
            "prompt_version": PROMPT_VERSION,
            "section_count": len(sections),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "llm_enabled": llm_client.is_enabled() and request.use_llm,
            "llm_cache_hits": llm_cache_hits,
            "llm_calls": llm_calls,
            "llm_errors": llm_errors,
            "fallback_sections": fallback_sections,
            "fallback_used": fallback_sections > 0,
        },
    )
    output_path = save_graph(graph)
    return graph, str(output_path), False


def _select_sections(parsed: ParsedTextbook, request: GraphBuildRequest) -> list[Section]:
    if request.section_ids:
        allowed = set(request.section_ids)
        return [section for section in parsed.sections if section.id in allowed][: request.max_sections]
    return parsed.sections[: request.max_sections]


def _chunks_by_section(parsed: ParsedTextbook) -> dict[str, list[Chunk]]:
    chunks: dict[str, list[Chunk]] = {}
    for chunk in parsed.chunks:
        chunks.setdefault(chunk.section_id, []).append(chunk)
    return chunks


def _section_text(section: Section, chunks: list[Chunk]) -> str:
    joined = "\n".join(chunk.text for chunk in chunks)
    return joined[:MAX_SECTION_CHARS] or section.content[:MAX_SECTION_CHARS]


def _build_prompt(section: Section, text: str) -> str:
    return f"""你是教材知识图谱抽取器。
只基于给定章节内容抽取核心知识点和关系。
输出严格 JSON，不要输出 Markdown。
节点必须包含 name、definition、category、source_quote。
关系必须包含 source、target、relation_type、description、source_quote。
relation_type 只能是 prerequisite、parallel、contains、applies_to。
如果证据不足，不要编造关系。

章节标题：{section.title}
章节内容：
{text}
"""


def _drafts_from_llm(payload: dict[str, Any], chunks: list[Chunk], section: Section) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    node_drafts: list[NodeDraft] = []
    for item in payload.get("nodes", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        quote = str(item.get("source_quote") or item.get("definition") or name)
        chunk = _chunk_for_quote(chunks, quote)
        node_drafts.append(
            NodeDraft(
                name=name,
                definition=str(item.get("definition") or _definition_for_term(name, chunk.text)),
                category=str(item.get("category") or "核心概念"),
                source_quote=_trim_quote(quote),
                chunk=chunk,
            )
        )

    edge_drafts: list[EdgeDraft] = []
    for item in payload.get("edges", []):
        if not isinstance(item, dict):
            continue
        source_name = str(item.get("source") or "").strip()
        target_name = str(item.get("target") or "").strip()
        if not source_name or not target_name:
            continue
        quote = str(item.get("source_quote") or item.get("description") or section.title)
        edge_drafts.append(
            EdgeDraft(
                source_name=source_name,
                target_name=target_name,
                relation_type=_relation_from_text(str(item.get("relation_type") or "")),
                description=str(item.get("description") or ""),
                source_quote=_trim_quote(quote),
                chunk=_chunk_for_quote(chunks, quote),
            )
        )
    return node_drafts, edge_drafts


def _fallback_drafts(section: Section, chunks: list[Chunk], max_nodes: int) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    text = _section_text(section, chunks)
    names = _candidate_terms(section.title, text)[:max_nodes]
    node_drafts = [
        NodeDraft(
            name=name,
            definition=_definition_for_term(name, text),
            category=_category_for_term(name),
            source_quote=_definition_for_term(name, text),
            chunk=_chunk_for_quote(chunks, name),
        )
        for name in names
    ]
    edge_drafts = _fallback_edges(names, text, chunks)
    return node_drafts, edge_drafts


def _candidate_terms(title: str, text: str) -> list[str]:
    candidates: list[str] = []
    for raw in [title, *TERM_PATTERN.findall(text)]:
        name = _clean_term(raw)
        if not name or len(name) < 2 or len(name) > 24:
            continue
        if name not in candidates:
            candidates.append(name)
    return candidates


def _fallback_edges(names: list[str], text: str, chunks: list[Chunk]) -> list[EdgeDraft]:
    edges: list[EdgeDraft] = []
    if len(names) < 2:
        return edges
    hub = names[0]
    for name in names[1:4]:
        edges.append(
            EdgeDraft(
                source_name=hub,
                target_name=name,
                relation_type=KnowledgeRelationType.contains,
                description=f"{hub} 章节内容包含 {name}。",
                source_quote=_definition_for_term(name, text),
                chunk=_chunk_for_quote(chunks, name),
            )
        )

    prerequisite = _prerequisite_edge(names, text, chunks)
    if prerequisite is not None:
        edges.append(prerequisite)

    applies_to = _keyword_edge(names, text, chunks, ("应用", "用于", "适用于", "作用于"), KnowledgeRelationType.applies_to)
    if applies_to is not None:
        edges.append(applies_to)

    if len(names) >= 3:
        edges.append(
            EdgeDraft(
                source_name=names[1],
                target_name=names[2],
                relation_type=KnowledgeRelationType.parallel_with,
                description=f"{names[1]} 与 {names[2]} 在同一章节中并列出现。",
                source_quote=_definition_for_term(names[1], text),
                chunk=_chunk_for_quote(chunks, names[1]),
            )
        )
    return edges


def _prerequisite_edge(names: list[str], text: str, chunks: list[Chunk]) -> EdgeDraft | None:
    if not any(marker in text for marker in ("基础", "前提", "依赖", "需要先")):
        return None
    for source in names:
        for target in names:
            if source == target:
                continue
            sentence = _sentence_with_terms(text, source, target)
            if sentence and any(marker in sentence for marker in ("基础", "前提", "依赖", "需要先")):
                return EdgeDraft(
                    source_name=source,
                    target_name=target,
                    relation_type=KnowledgeRelationType.prerequisite_of,
                    description=f"理解 {target} 需要先掌握 {source}。",
                    source_quote=sentence,
                    chunk=_chunk_for_quote(chunks, sentence),
                )
    return None


def _keyword_edge(
    names: list[str],
    text: str,
    chunks: list[Chunk],
    markers: tuple[str, ...],
    relation_type: KnowledgeRelationType,
) -> EdgeDraft | None:
    if not any(marker in text for marker in markers):
        return None
    for source in names:
        for target in names:
            if source == target:
                continue
            sentence = _sentence_with_terms(text, source, target)
            if sentence and any(marker in sentence for marker in markers):
                return EdgeDraft(
                    source_name=source,
                    target_name=target,
                    relation_type=relation_type,
                    description=f"{source} 可应用或作用于 {target}。",
                    source_quote=sentence,
                    chunk=_chunk_for_quote(chunks, sentence),
                )
    return None


def _merge_node(parsed: ParsedTextbook, section: Section, draft: NodeDraft, node_by_name: dict[str, KnowledgeNode]) -> KnowledgeNode:
    key = _normalize_name(draft.name)
    existing = node_by_name.get(key)
    if existing is not None:
        evidence = list(dict.fromkeys([*existing.evidence_chunk_ids, draft.chunk.id]))
        frequency = int(existing.metadata.get("frequency", 1)) + 1
        updated = existing.model_copy(
            update={
                "evidence_chunk_ids": evidence,
                "metadata": {
                    **existing.metadata,
                    "frequency": frequency,
                },
            }
        )
        node_by_name[key] = updated
        return updated

    node = KnowledgeNode(
        id=stable_id("node", parsed.raw_file.id, key),
        name=draft.name,
        node_type=_node_type_for_term(draft.name),
        definition=draft.definition,
        aliases=[],
        source_locator=draft.chunk.source_locator,
        evidence_chunk_ids=[draft.chunk.id],
        confidence=0.62,
        metadata={
            "category": draft.category,
            "chapter": section.title,
            "page": draft.chunk.source_locator.page_start,
            "source_quote": _trim_quote(draft.source_quote),
            "frequency": 1,
            "section_id": section.id,
        },
    )
    node_by_name[key] = node
    return node


def _build_edge(parsed: ParsedTextbook, draft: EdgeDraft, source_id: str, target_id: str) -> KnowledgeEdge:
    return KnowledgeEdge(
        id=stable_id("edge", parsed.raw_file.id, source_id, target_id, draft.relation_type.value, quote_hash(draft.source_quote)),
        source_node_id=source_id,
        target_node_id=target_id,
        relation_type=draft.relation_type,
        description=draft.description,
        source_locator=draft.chunk.source_locator,
        evidence_chunk_ids=[draft.chunk.id],
        confidence=0.55,
        metadata={
            "source_quote": _trim_quote(draft.source_quote),
            "plan3_relation_type": _plan3_relation_name(draft.relation_type),
        },
    )


def _chunk_for_quote(chunks: list[Chunk], quote: str) -> Chunk:
    for chunk in chunks:
        if quote and quote in chunk.text:
            return chunk
    for chunk in chunks:
        if any(term and term in chunk.text for term in TERM_PATTERN.findall(quote)):
            return chunk
    return chunks[0]


def _definition_for_term(term: str, text: str) -> str:
    sentence = _sentence_with_terms(text, term)
    return _trim_quote(sentence or term)


def _sentence_with_terms(text: str, *terms: str) -> str | None:
    for sentence in re.split(r"(?<=[。！？!?；;])", text):
        clean = sentence.strip()
        if clean and all(term in clean for term in terms):
            return clean
    return None


def _category_for_term(term: str) -> str:
    if any(marker in term for marker in ("疾病", "炎", "病")):
        return "疾病与病理"
    if any(marker in term for marker in ("结构", "细胞", "组织", "器官", "系统", "血管", "神经", "肌肉")):
        return "结构"
    if any(marker in term for marker in ("功能", "机制", "过程", "反应", "作用")):
        return "机制过程"
    return "核心概念"


def _node_type_for_term(term: str) -> KnowledgeNodeType:
    if any(marker in term for marker in ("疾病", "炎", "病")):
        return KnowledgeNodeType.disease
    if any(marker in term for marker in ("结构", "细胞", "组织", "器官", "系统", "血管", "神经", "肌肉")):
        return KnowledgeNodeType.structure
    if any(marker in term for marker in ("机制", "过程", "反应")):
        return KnowledgeNodeType.process
    if "功能" in term or "作用" in term:
        return KnowledgeNodeType.function
    return KnowledgeNodeType.concept


def _relation_from_text(value: str) -> KnowledgeRelationType:
    normalized = value.strip().lower()
    if normalized in {"prerequisite", "prerequisite_of"}:
        return KnowledgeRelationType.prerequisite_of
    if normalized in {"parallel", "parallel_with"}:
        return KnowledgeRelationType.parallel_with
    if normalized in {"contains", "contain"}:
        return KnowledgeRelationType.contains
    if normalized in {"applies_to", "apply"}:
        return KnowledgeRelationType.applies_to
    return KnowledgeRelationType.mentioned_in


def _plan3_relation_name(relation_type: KnowledgeRelationType) -> str:
    mapping = {
        KnowledgeRelationType.prerequisite_of: "prerequisite",
        KnowledgeRelationType.parallel_with: "parallel",
        KnowledgeRelationType.contains: "contains",
        KnowledgeRelationType.applies_to: "applies_to",
    }
    return mapping.get(relation_type, relation_type.value.lower())


def _clean_term(term: str) -> str:
    return re.sub(r"^[第\d一二三四五六七八九十百章节篇、\s.．]+", "", term).strip(" ：:，,。；;（）()[]【】")


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def _trim_quote(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:limit]
