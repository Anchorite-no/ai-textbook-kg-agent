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


PROMPT_VERSION = "kg_extract_v3"
MAX_SECTION_CHARS = 3000
LLM_MIN_GROUNDED_NODES = 3
TERM_PATTERN = re.compile(
    r"[\u4e00-\u9fa5A-Za-z0-9]{2,24}?(?:"
    r"电位|传导|细胞|组织|器官|系统|结构|功能|机制|过程|反应|作用|疾病|症状|诊断|治疗|"
    r"病变|炎症|感染|免疫|病毒|细菌|解剖|生理|病理|血管|神经|肌肉|淋巴|膜电位"
    r")"
)
KNOWN_COMPOUND_TERM_PATTERN = re.compile(
    r"动作电位|静息电位|膜电位|神经传导|炎症反应|免疫反应|病理变化|发病机制|"
    r"血液循环|细胞死亡|细胞损伤|适应性变化|临床医学|基础医学|病理诊断|"
    r"病理学|解剖学|组织胚胎学|生理学|医学微生物学"
)
PAREN_TERM_PATTERN = re.compile(r"([\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9]{1,15})[（(][A-Za-z][^）)]{1,80}[）)]")
DEFINITION_TERM_PATTERN = re.compile(
    r"(?:^|[。；：:\n])\s*([\u4e00-\u9fffA-Za-z0-9]{2,18})(?:[（(][^）)]{1,80}[）)])?\s*(?:是指|是|指|称为|简称)"
)
BAD_TERM_PREFIXES = (
    "中的",
    "也与",
    "但",
    "而",
    "并",
    "其",
    "该",
    "它",
    "这些",
    "这种",
    "作为",
    "从",
    "在",
    "由",
    "与",
    "和",
    "或",
    "及",
    "可以",
    "用于",
    "组成",
    "都是",
    "是一种",
    "是",
)
BAD_TERM_FRAGMENTS = (
    "第一部",
    "从无到有",
    "人格魅力",
    "人们可以",
    "严重者",
    "学习中",
    "本书",
)
BAD_TERM_VERBS = (
    "研究",
    "应用",
    "编著",
    "激励",
    "提供",
    "进行",
    "记录",
    "认为",
    "学习",
    "掌握",
    "成为",
    "导致",
    "转化",
    "表达",
    "丧失",
    "推动",
    "解释",
)


@dataclass(frozen=True)
class NodeDraft:
    name: str
    definition: str
    category: str
    source_quote: str
    chunk: Chunk
    source_quote_verified: bool
    evidence_strategy: str
    aliases: tuple[str, ...] = ()
    extraction_method: str = "fallback"
    confidence: float = 0.62


@dataclass(frozen=True)
class EdgeDraft:
    source_name: str
    target_name: str
    relation_type: KnowledgeRelationType
    description: str
    source_quote: str
    chunk: Chunk
    source_quote_verified: bool
    evidence_strategy: str
    extraction_method: str = "fallback"
    confidence: float = 0.55


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
    llm_sections = 0
    llm_grounded_sections = 0
    fallback_sections = 0
    supplemented_sections = 0

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
                prompt = _build_prompt(section, text, request.max_nodes_per_section)
                try:
                    llm_payload = llm_client.extract_json(prompt)
                except Exception:
                    llm_errors += 1
                    llm_payload = None
                if llm_payload is not None:
                    llm_calls += 1
                    llm_cache.set(cache_key, llm_payload)

        if llm_payload is not None:
            llm_sections += 1
            node_drafts, edge_drafts = _drafts_from_llm(llm_payload, section_chunks, section)
            if len(node_drafts) >= min(LLM_MIN_GROUNDED_NODES, request.max_nodes_per_section) and edge_drafts:
                llm_grounded_sections += 1
            else:
                fallback_sections += 1
                supplemented_sections += 1
                fallback_nodes, fallback_edges = _fallback_drafts(section, section_chunks, request.max_nodes_per_section)
                node_drafts = _merge_node_drafts(node_drafts, fallback_nodes, request.max_nodes_per_section)
                edge_drafts = _merge_edge_drafts(edge_drafts, fallback_edges)
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
            "llm_sections": llm_sections,
            "llm_grounded_sections": llm_grounded_sections,
            "fallback_sections": fallback_sections,
            "supplemented_sections": supplemented_sections,
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


def _build_prompt(section: Section, text: str, max_nodes: int) -> str:
    return f"""你是教材知识图谱抽取器。
只基于给定章节内容抽取核心知识点和关系。
输出严格 JSON，不要输出 Markdown。

输出格式必须是：
{{
  "nodes": [
    {{
      "name": "2到16字的教材术语，不要整句",
      "definition": "只基于原文的一句话定义或解释",
      "category": "结构|功能|机制过程|疾病病理|病原体|诊断治疗|核心概念",
      "aliases": ["可选同义名"],
      "source_quote": "章节内容里的原文短句"
    }}
  ],
  "edges": [
    {{
      "source": "节点 name",
      "target": "节点 name",
      "relation_type": "prerequisite|parallel|contains|applies_to|causes|leads_to|explains|is_a|part_of|contrasts_with",
      "description": "只基于原文说明二者关系",
      "source_quote": "章节内容里的原文短句"
    }}
  ]
}}

抽取规则：
1. 最多抽取 {max_nodes} 个节点、{max(3, max_nodes)} 条关系。
2. name 必须是教材知识点，不能是页码、题注、章节标题整句、学习目标、扫描图片提示。
3. source_quote 必须是章节内容中的原文短句，不允许改写；证据不足就不要输出。
4. 优先抽取定义明确、可教学、可跨教材对齐的概念。
5. 如果原文支持，至少覆盖 prerequisite、contains、part_of、causes、explains、contrasts_with 中的 3 类关系；不支持就少输出。
6. 不要引入章节内容外的医学常识。

章节标题：{section.title}
章节内容：
{text}
"""


def _drafts_from_llm(payload: dict[str, Any], chunks: list[Chunk], section: Section) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    node_drafts: list[NodeDraft] = []
    for item in _list_field(payload, "nodes", "concepts", "knowledge_points", "知识点", "节点"):
        if not isinstance(item, dict):
            continue
        name = _clean_term(str(item.get("name") or item.get("term") or item.get("concept") or "").strip())
        if not _is_good_concept_name(name):
            continue
        quote = str(item.get("source_quote") or item.get("definition") or name)
        chunk, grounded_quote, verified, strategy = _ground_evidence(chunks, quote, name)
        if not verified:
            continue
        aliases = tuple(
            alias
            for alias in (_clean_term(str(raw_alias)) for raw_alias in _list_field(item, "aliases", "alias", "同义词"))
            if alias and alias != name and _is_good_concept_name(alias)
        )
        definition = _trim_quote(str(item.get("definition") or _definition_for_term(name, chunk.text)), 240)
        node_drafts.append(
            NodeDraft(
                name=name,
                definition=definition,
                category=_normalize_category(str(item.get("category") or "核心概念")),
                source_quote=grounded_quote,
                chunk=chunk,
                source_quote_verified=verified,
                evidence_strategy=strategy,
                aliases=aliases,
                extraction_method="llm",
                confidence=0.78,
            )
        )

    edge_drafts: list[EdgeDraft] = []
    node_names = {_normalize_name(draft.name) for draft in node_drafts}
    for item in _list_field(payload, "edges", "relations", "relationships", "关系", "边"):
        if not isinstance(item, dict):
            continue
        source_name = _clean_term(str(item.get("source") or item.get("source_name") or item.get("from") or "").strip())
        target_name = _clean_term(str(item.get("target") or item.get("target_name") or item.get("to") or "").strip())
        if not source_name or not target_name:
            continue
        if _normalize_name(source_name) not in node_names or _normalize_name(target_name) not in node_names:
            continue
        quote = str(item.get("source_quote") or item.get("description") or section.title)
        chunk, grounded_quote, verified, strategy = _ground_evidence(chunks, quote, source_name, target_name)
        if not verified:
            continue
        edge_drafts.append(
            EdgeDraft(
                source_name=source_name,
                target_name=target_name,
                relation_type=_relation_from_text(str(item.get("relation_type") or "")),
                description=str(item.get("description") or ""),
                source_quote=grounded_quote,
                chunk=chunk,
                source_quote_verified=verified,
                evidence_strategy=strategy,
                extraction_method="llm",
                confidence=0.72,
            )
        )
    return node_drafts, edge_drafts


def _fallback_drafts(section: Section, chunks: list[Chunk], max_nodes: int) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    text = _section_text(section, chunks)
    names = _candidate_terms(section.title, text)[:max_nodes]
    node_drafts: list[NodeDraft] = []
    for name in names:
        chunk, quote, verified, strategy = _ground_evidence(chunks, _definition_for_term(name, text), name)
        if not verified:
            continue
        node_drafts.append(
            NodeDraft(
                name=name,
                definition=_definition_for_term(name, text),
                category=_category_for_term(name),
                source_quote=quote,
                chunk=chunk,
                source_quote_verified=verified,
                evidence_strategy=strategy,
            )
        )
    edge_drafts = _fallback_edges([draft.name for draft in node_drafts], text, chunks)
    return node_drafts, edge_drafts


def _candidate_terms(title: str, text: str) -> list[str]:
    candidates: list[str] = []
    raw_terms = [
        title,
        *KNOWN_COMPOUND_TERM_PATTERN.findall(text),
        *_parenthetical_terms(text),
        *_definition_terms(text),
        *TERM_PATTERN.findall(text),
    ]
    for raw in raw_terms:
        name = _clean_term(raw)
        if not _is_good_concept_name(name):
            continue
        if name not in candidates:
            candidates.append(name)
    return candidates


def _parenthetical_terms(text: str) -> list[str]:
    return [match.group(1) for match in PAREN_TERM_PATTERN.finditer(text)]


def _definition_terms(text: str) -> list[str]:
    return [match.group(1) for match in DEFINITION_TERM_PATTERN.finditer(text)]


def _fallback_edges(names: list[str], text: str, chunks: list[Chunk]) -> list[EdgeDraft]:
    edges: list[EdgeDraft] = []
    if len(names) < 2:
        return edges
    hub = names[0]
    for name in names[1:4]:
        chunk, quote, verified, strategy = _ground_evidence(chunks, _definition_for_term(name, text), name)
        edges.append(
            EdgeDraft(
                source_name=hub,
                target_name=name,
                relation_type=KnowledgeRelationType.contains,
                description=f"{hub} 章节内容包含 {name}。",
                source_quote=quote,
                chunk=chunk,
                source_quote_verified=verified,
                evidence_strategy=f"fallback_contains:{strategy}",
            )
        )

    prerequisite = _prerequisite_edge(names, text, chunks)
    if prerequisite is not None:
        edges.append(prerequisite)

    applies_to = _keyword_edge(names, text, chunks, ("应用", "用于", "适用于", "作用于"), KnowledgeRelationType.applies_to)
    if applies_to is not None:
        edges.append(applies_to)

    is_a = _keyword_edge(names, text, chunks, ("是一种", "属于", "归为", "称为"), KnowledgeRelationType.is_a)
    if is_a is not None:
        edges.append(is_a)

    part_of = _keyword_edge(names, text, chunks, ("组成", "构成", "部分", "包括"), KnowledgeRelationType.part_of)
    if part_of is not None:
        edges.append(part_of)

    causes = _keyword_edge(names, text, chunks, ("导致", "引起", "造成", "诱发"), KnowledgeRelationType.causes)
    if causes is not None:
        edges.append(causes)

    leads_to = _keyword_edge(names, text, chunks, ("进而", "随后", "最终", "使得"), KnowledgeRelationType.leads_to)
    if leads_to is not None:
        edges.append(leads_to)

    explains = _keyword_edge(names, text, chunks, ("解释", "说明", "由于", "因为"), KnowledgeRelationType.explains)
    if explains is not None:
        edges.append(explains)

    contrasts = _keyword_edge(names, text, chunks, ("不同", "区别", "相反", "对比"), KnowledgeRelationType.contrasts_with)
    if contrasts is not None:
        edges.append(contrasts)

    if len(names) >= 3:
        chunk, quote, verified, strategy = _ground_evidence(chunks, _definition_for_term(names[1], text), names[1], names[2])
        edges.append(
            EdgeDraft(
                source_name=names[1],
                target_name=names[2],
                relation_type=KnowledgeRelationType.parallel_with,
                description=f"{names[1]} 与 {names[2]} 在同一章节中并列出现。",
                source_quote=quote,
                chunk=chunk,
                source_quote_verified=verified,
                evidence_strategy=f"fallback_parallel:{strategy}",
            )
        )
    return edges


def _merge_node_drafts(primary: list[NodeDraft], fallback: list[NodeDraft], max_nodes: int) -> list[NodeDraft]:
    merged: list[NodeDraft] = []
    seen: set[str] = set()
    for draft in [*primary, *fallback]:
        key = _normalize_name(draft.name)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(draft)
        if len(merged) >= max_nodes:
            break
    return merged


def _merge_edge_drafts(primary: list[EdgeDraft], fallback: list[EdgeDraft]) -> list[EdgeDraft]:
    merged: list[EdgeDraft] = []
    seen: set[tuple[str, str, KnowledgeRelationType]] = set()
    for draft in [*primary, *fallback]:
        key = (_normalize_name(draft.source_name), _normalize_name(draft.target_name), draft.relation_type)
        if key[0] == key[1] or key in seen:
            continue
        seen.add(key)
        merged.append(draft)
    return merged


def _prerequisite_edge(names: list[str], text: str, chunks: list[Chunk]) -> EdgeDraft | None:
    if not any(marker in text for marker in ("基础", "前提", "依赖", "需要先")):
        return None
    for source in names:
        for target in names:
            if source == target:
                continue
            sentence = _sentence_with_terms(text, source, target)
            if sentence and any(marker in sentence for marker in ("基础", "前提", "依赖", "需要先")):
                source_name, target_name = _orient_prerequisite(source, target, sentence)
                return EdgeDraft(
                    source_name=source_name,
                    target_name=target_name,
                    relation_type=KnowledgeRelationType.prerequisite_of,
                    description=f"理解 {target_name} 需要先掌握 {source_name}。",
                    source_quote=sentence,
                    chunk=_chunk_for_quote(chunks, sentence),
                    source_quote_verified=True,
                    evidence_strategy="fallback_sentence",
                )
    return None


def _orient_prerequisite(source: str, target: str, sentence: str) -> tuple[str, str]:
    compact = re.sub(r"\s+", "", sentence)
    if re.search(re.escape(source) + r".{0,8}是" + re.escape(target) + r".{0,8}(基础|前提)", compact):
        return source, target
    if re.search(re.escape(target) + r".{0,8}是" + re.escape(source) + r".{0,8}(基础|前提)", compact):
        return target, source
    if re.search(r"(学习|理解|掌握)" + re.escape(target) + r".{0,20}" + re.escape(source) + r".{0,8}(基础|前提)", compact):
        return source, target
    if re.search(r"(学习|理解|掌握)" + re.escape(source) + r".{0,20}" + re.escape(target) + r".{0,8}(基础|前提)", compact):
        return target, source
    if re.search(re.escape(target) + r".{0,8}以" + re.escape(source) + r".{0,8}为(基础|前提)", compact):
        return source, target
    if re.search(re.escape(source) + r".{0,8}以" + re.escape(target) + r".{0,8}为(基础|前提)", compact):
        return target, source
    return source, target


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
            sentence = _sentence_with_terms_and_markers(text, markers, source, target)
            if sentence:
                return EdgeDraft(
                    source_name=source,
                    target_name=target,
                    relation_type=relation_type,
                    description=_description_for_relation(source, target, relation_type),
                    source_quote=sentence,
                    chunk=_chunk_for_quote(chunks, sentence),
                    source_quote_verified=True,
                    evidence_strategy="fallback_sentence",
                )
    return None


def _merge_node(parsed: ParsedTextbook, section: Section, draft: NodeDraft, node_by_name: dict[str, KnowledgeNode]) -> KnowledgeNode:
    key = _normalize_name(draft.name)
    existing = node_by_name.get(key)
    if existing is not None:
        evidence = list(dict.fromkeys([*existing.evidence_chunk_ids, draft.chunk.id]))
        aliases = list(dict.fromkeys([*existing.aliases, *draft.aliases]))
        frequency = int(existing.metadata.get("frequency", 1)) + 1
        updated = existing.model_copy(
            update={
                "aliases": aliases,
                "evidence_chunk_ids": evidence,
                "confidence": max(existing.confidence, draft.confidence),
                "metadata": {
                    **existing.metadata,
                    "frequency": frequency,
                    "extraction_method": _merge_extraction_method(str(existing.metadata.get("extraction_method", "")), draft.extraction_method),
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
        aliases=list(draft.aliases),
        source_locator=draft.chunk.source_locator,
        evidence_chunk_ids=[draft.chunk.id],
        confidence=draft.confidence,
        metadata={
            "category": draft.category,
            "chapter": section.title,
            "page": draft.chunk.source_locator.page_start,
            "source_quote": _trim_quote(draft.source_quote),
            "source_quote_verified": draft.source_quote_verified,
            "evidence_strategy": draft.evidence_strategy,
            "extraction_method": draft.extraction_method,
            "frequency": 1,
            "section_id": section.id,
        },
    )
    node_by_name[key] = node
    return node


def _merge_extraction_method(existing: str, new: str) -> str:
    methods = [method for method in existing.split("+") if method]
    if new and new not in methods:
        methods.append(new)
    return "+".join(methods) if methods else new


def _build_edge(parsed: ParsedTextbook, draft: EdgeDraft, source_id: str, target_id: str) -> KnowledgeEdge:
    return KnowledgeEdge(
        id=stable_id("edge", parsed.raw_file.id, source_id, target_id, draft.relation_type.value, quote_hash(draft.source_quote)),
        source_node_id=source_id,
        target_node_id=target_id,
        relation_type=draft.relation_type,
        description=draft.description,
        source_locator=draft.chunk.source_locator,
        evidence_chunk_ids=[draft.chunk.id],
        confidence=draft.confidence,
        metadata={
            "source_quote": _trim_quote(draft.source_quote),
            "source_quote_verified": draft.source_quote_verified,
            "evidence_strategy": draft.evidence_strategy,
            "extraction_method": draft.extraction_method,
            "plan3_relation_type": _plan3_relation_name(draft.relation_type),
        },
    )


def _ground_evidence(chunks: list[Chunk], quote: str, *terms: str) -> tuple[Chunk, str, bool, str]:
    clean_quote = _trim_quote(quote)
    for chunk in chunks:
        if clean_quote and clean_quote in chunk.text:
            return chunk, clean_quote, True, "exact_quote"

    for chunk in chunks:
        sentence = _sentence_with_terms(chunk.text, *[term for term in terms if term])
        if sentence:
            return chunk, _trim_quote(sentence), True, "term_sentence"

    for chunk in chunks:
        for term in terms:
            if not term:
                continue
            sentence = _sentence_with_terms(chunk.text, term)
            if sentence:
                return chunk, _trim_quote(sentence), True, "partial_term_sentence"

    chunk = chunks[0]
    fallback_quote = _trim_quote(chunk.text or clean_quote)
    return chunk, fallback_quote, False, "fallback_first_chunk"


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


def _sentence_with_terms_and_markers(text: str, markers: tuple[str, ...], *terms: str) -> str | None:
    for sentence in re.split(r"(?<=[。！？!?；;])", text):
        clean = sentence.strip()
        if clean and all(term in clean for term in terms) and any(marker in clean for marker in markers):
            return clean
    return None


def _category_for_term(term: str) -> str:
    if any(marker in term for marker in ("功能", "机制", "过程", "反应", "作用")):
        return "机制过程"
    if any(marker in term for marker in ("结构", "细胞", "组织", "器官", "系统", "血管", "神经", "肌肉")):
        return "结构"
    if any(marker in term for marker in ("疾病", "炎症", "病变", "肿瘤", "癌")):
        return "疾病与病理"
    return "核心概念"


def _node_type_for_term(term: str) -> KnowledgeNodeType:
    if "机制" in term:
        return KnowledgeNodeType.mechanism
    if any(marker in term for marker in ("过程", "反应")):
        return KnowledgeNodeType.process
    if "功能" in term or "作用" in term:
        return KnowledgeNodeType.function
    if any(marker in term for marker in ("结构", "细胞", "组织", "器官", "系统", "血管", "神经", "肌肉")):
        return KnowledgeNodeType.structure
    if any(marker in term for marker in ("疾病", "炎症", "病变", "肿瘤", "癌")):
        return KnowledgeNodeType.disease
    return KnowledgeNodeType.concept


def _relation_from_text(value: str) -> KnowledgeRelationType:
    normalized = re.sub(r"[\s\-]+", "_", value.strip().lower())
    enum_by_value = {item.value.lower(): item for item in KnowledgeRelationType}
    if normalized in enum_by_value:
        return enum_by_value[normalized]
    if normalized in {"prerequisite", "prerequisite_of", "先修", "前置", "前置知识", "基础", "依赖"}:
        return KnowledgeRelationType.prerequisite_of
    if normalized in {"parallel", "parallel_with", "并列", "并行"}:
        return KnowledgeRelationType.parallel_with
    if normalized in {"contains", "contain", "包含"}:
        return KnowledgeRelationType.contains
    if normalized in {"is_a", "isa", "是一种", "属于"}:
        return KnowledgeRelationType.is_a
    if normalized in {"part_of", "partof", "组成", "部分"}:
        return KnowledgeRelationType.part_of
    if normalized in {"applies_to", "apply", "应用", "作用于"}:
        return KnowledgeRelationType.applies_to
    if normalized in {"contrasts_with", "contrast", "contrasts", "区别", "对比"}:
        return KnowledgeRelationType.contrasts_with
    if normalized in {"causes", "cause", "导致", "引起"}:
        return KnowledgeRelationType.causes
    if normalized in {"leads_to", "lead_to", "进而", "结果"}:
        return KnowledgeRelationType.leads_to
    if normalized in {"explains", "explain", "解释", "说明"}:
        return KnowledgeRelationType.explains
    return KnowledgeRelationType.mentioned_in


def _description_for_relation(source: str, target: str, relation_type: KnowledgeRelationType) -> str:
    if relation_type == KnowledgeRelationType.applies_to:
        return f"{source} 可应用或作用于 {target}。"
    if relation_type == KnowledgeRelationType.is_a:
        return f"{source} 是或属于 {target}。"
    if relation_type == KnowledgeRelationType.part_of:
        return f"{source} 是 {target} 的组成部分或相关组成。"
    if relation_type == KnowledgeRelationType.causes:
        return f"{source} 可能导致或引起 {target}。"
    if relation_type == KnowledgeRelationType.contrasts_with:
        return f"{source} 与 {target} 存在差异或对比。"
    if relation_type == KnowledgeRelationType.leads_to:
        return f"{source} 可能进一步导致 {target}。"
    if relation_type == KnowledgeRelationType.explains:
        return f"{source} 可解释 {target}。"
    return f"{source} 与 {target} 存在关系。"


def _plan3_relation_name(relation_type: KnowledgeRelationType) -> str:
    mapping = {
        KnowledgeRelationType.prerequisite_of: "prerequisite",
        KnowledgeRelationType.parallel_with: "parallel",
        KnowledgeRelationType.contains: "contains",
        KnowledgeRelationType.is_a: "is_a",
        KnowledgeRelationType.part_of: "part_of",
        KnowledgeRelationType.applies_to: "applies_to",
        KnowledgeRelationType.contrasts_with: "contrasts_with",
        KnowledgeRelationType.causes: "causes",
        KnowledgeRelationType.leads_to: "leads_to",
        KnowledgeRelationType.explains: "explains",
    }
    return mapping.get(relation_type, relation_type.value.lower())


def _clean_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.replace("\n", " ")).strip()
    cleaned = re.sub(r"^[第\d一二三四五六七八九十百章节篇、\s.．]+", "", cleaned)
    for marker in ("被称为", "称为", "叫做"):
        if marker in cleaned and not cleaned.endswith(marker):
            cleaned = cleaned.split(marker)[-1].strip()
    for prefix in ("但严重者可导致", "严重者可导致", "可导致", "导致", "中的", "也与"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned.strip(" ：:，,。；;（）()[]【】\"'")


def _is_good_concept_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 40:
        return False
    if re.fullmatch(r"\d{1,4}", name):
        return False
    if name.startswith(BAD_TERM_PREFIXES):
        return False
    if name.endswith(("都", "时", "者", "的特征")):
        return False
    if any(fragment in name for fragment in BAD_TERM_FRAGMENTS):
        return False
    if len(name) > 8 and any(verb in name for verb in BAD_TERM_VERBS):
        return False
    if len(name) > 10 and name.count("的") >= 2:
        return False
    if any(marker in name for marker in ("扫描图片", "体验AR", "学习目标", "复习思考题", "本章小结", "目录")):
        return False
    if re.search(r"[。！？；;，,]", name):
        return False
    if len(name) > 18 and not re.search(r"[A-Za-z]", name):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", name))


def _list_field(payload: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            return [value]
    return []


def _normalize_category(category: str) -> str:
    normalized = category.strip()
    if any(marker in normalized for marker in ("结构", "组织", "器官", "细胞")):
        return "结构"
    if any(marker in normalized for marker in ("功能", "作用")):
        return "功能"
    if any(marker in normalized for marker in ("机制", "过程", "反应")):
        return "机制过程"
    if any(marker in normalized for marker in ("疾病", "病理", "病变", "炎症")):
        return "疾病病理"
    if any(marker in normalized for marker in ("病原", "病毒", "细菌")):
        return "病原体"
    if any(marker in normalized for marker in ("诊断", "治疗")):
        return "诊断治疗"
    return "核心概念"


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def _trim_quote(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:limit]
