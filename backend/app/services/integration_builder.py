from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import settings
from app.models.schemas import (
    AlignmentBuildRequest,
    AlignmentCandidate,
    AlignmentRelationType,
    AlignmentResponse,
    CompressionStats,
    GraphResponse,
    IntegratedConcept,
    IntegrationAction,
    IntegrationBuildRequest,
    IntegrationDecision,
    IntegrationResponse,
    KnowledgeNode,
    SourceLocator,
)
from app.services.alignment_builder import build_alignment
from app.services.converted_textbook_importer import stable_id
from app.services.graph_storage import load_graph
from app.services.integration_storage import load_integration, save_integration
from app.services.parsed_storage import load_parsed_textbook


MIN_CONCEPT_CHARS = 48
HARD_MIN_CONCEPT_CHARS = 12


@dataclass
class ConceptDraft:
    canonical_name: str
    member_node_ids: list[str]
    action: IntegrationAction
    full_definition: str
    cluster_id: str | None = None
    confidence: float = 0.0
    importance: float = 0.0
    evidence_chunk_ids: list[str] = field(default_factory=list)
    source_locators: list[SourceLocator] = field(default_factory=list)
    removed_redundancy: str | None = None
    reason: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    force_retain: bool = False
    definition: str = ""
    decision_id: str | None = None


def build_integration(request: IntegrationBuildRequest) -> tuple[IntegrationResponse, str, bool]:
    raw_file_ids = sorted(request.raw_file_ids)
    existing = load_integration(raw_file_ids)
    if existing is not None and not request.force_rebuild:
        return existing, str(save_integration(existing)), True

    alignment, _alignment_path, _alignment_cache_hit = build_alignment(
        AlignmentBuildRequest(
            raw_file_ids=raw_file_ids,
            force_rebuild=request.force_rebuild,
            min_confidence=request.alignment_min_confidence,
            include_singletons=False,
            max_nodes=request.max_nodes,
        )
    )
    graphs = _load_graphs(alignment.raw_file_ids or raw_file_ids)
    node_by_id = _node_index(graphs, request.max_nodes)
    degree_by_node_id = _node_degrees(graphs, set(node_by_id))
    original_char_count, original_metadata = _original_char_count(graphs, node_by_id)

    conflict_decisions, conflict_node_ids = _conflict_decisions(alignment, node_by_id)
    cluster_drafts, covered_node_ids = _cluster_drafts(alignment, node_by_id, degree_by_node_id, conflict_node_ids)
    singleton_drafts = _singleton_drafts(node_by_id, degree_by_node_id, covered_node_ids, conflict_node_ids)

    retained_drafts, removed_drafts = _apply_compression_budget(
        [*cluster_drafts, *singleton_drafts],
        original_char_count,
        request.target_compression_ratio,
    )
    decisions, integrated_concepts = _materialize(
        retained_drafts=retained_drafts,
        removed_drafts=removed_drafts,
        conflict_decisions=conflict_decisions,
        include_keep_decisions=request.include_keep_decisions,
        conflict_node_ids=conflict_node_ids,
    )
    stats = _compression_stats(
        original_char_count=original_char_count,
        original_node_count=len(node_by_id),
        target_compression_ratio=request.target_compression_ratio,
        decisions=decisions,
        integrated_concepts=integrated_concepts,
        metadata=original_metadata,
    )
    response = IntegrationResponse(
        id=stable_id(
            "integration",
            *alignment.raw_file_ids,
            alignment.id,
            "stage8_v1",
            request.target_compression_ratio,
            request.alignment_min_confidence,
        ),
        raw_file_ids=alignment.raw_file_ids,
        alignment_id=alignment.id,
        decisions=decisions,
        integrated_concepts=integrated_concepts,
        compression_stats=stats,
        generated_at=datetime.utcnow(),
        metadata={
            "builder": "stage8_integration_builder",
            "alignment_candidate_count": len(alignment.candidates),
            "alignment_cluster_count": len(alignment.clusters),
            "stage_boundary": "阶段 8 只生成整合/压缩决策和整合视图，不覆盖原始 KG、对齐候选或证据。",
            "compression_policy": {
                "target_compression_ratio": request.target_compression_ratio,
                "deduplication": "merge/refine/conflict 先判断概念关系",
                "compression": "在证据完整前提下压缩重复解释文本，低重要度 singleton 才进入 remove",
            },
        },
    )
    output_path = save_integration(response)
    return response, str(output_path), False


def _load_graphs(raw_file_ids: list[str]) -> list[GraphResponse]:
    if raw_file_ids:
        graphs = [graph for raw_file_id in raw_file_ids if (graph := load_graph(raw_file_id)) is not None]
    else:
        graphs = []
        if settings.graph_data_dir.exists():
            for path in sorted(settings.graph_data_dir.glob("raw_*.json")):
                graphs.append(GraphResponse.model_validate_json(path.read_text(encoding="utf-8")))
    if len(graphs) < 2:
        raise ValueError("Stage 8 integration requires at least two built textbook graphs.")
    return graphs


def _node_index(graphs: list[GraphResponse], max_nodes: int) -> dict[str, KnowledgeNode]:
    nodes: list[KnowledgeNode] = []
    for graph in graphs:
        nodes.extend(graph.nodes)
    return {node.id: node for node in nodes[:max_nodes]}


def _node_degrees(graphs: list[GraphResponse], allowed_node_ids: set[str]) -> dict[str, int]:
    degrees = {node_id: 0 for node_id in allowed_node_ids}
    for graph in graphs:
        for edge in graph.edges:
            if edge.source_node_id in degrees:
                degrees[edge.source_node_id] += 1
            if edge.target_node_id in degrees:
                degrees[edge.target_node_id] += 1
    return degrees


def _original_char_count(graphs: list[GraphResponse], node_by_id: dict[str, KnowledgeNode]) -> tuple[int, dict[str, object]]:
    total = 0
    section_count = 0
    raw_file_ids = [graph.raw_file_id for graph in graphs]
    for raw_file_id in raw_file_ids:
        parsed = load_parsed_textbook(raw_file_id)
        if parsed is None:
            continue
        section_count += len(parsed.sections)
        total += sum(section.char_count or len(section.content) for section in parsed.sections)

    fallback_used = False
    if total <= 0:
        fallback_used = True
        total = sum(len(_node_text(node)) for node in node_by_id.values())
    return total, {
        "source": "parsed_sections" if not fallback_used else "graph_node_definitions",
        "section_count": section_count,
        "raw_file_ids": raw_file_ids,
    }


def _conflict_decisions(
    alignment: AlignmentResponse,
    node_by_id: dict[str, KnowledgeNode],
) -> tuple[list[IntegrationDecision], set[str]]:
    decisions: list[IntegrationDecision] = []
    conflict_node_ids: set[str] = set()
    for candidate in alignment.candidates:
        if candidate.relation_type != AlignmentRelationType.conflicts_with:
            continue
        nodes = [node_by_id.get(candidate.source_node_id), node_by_id.get(candidate.target_node_id)]
        if any(node is None for node in nodes):
            continue
        typed_nodes = [node for node in nodes if node is not None]
        conflict_node_ids.update(node.id for node in typed_nodes)
        evidence_chunk_ids = _unique_texts([*candidate.evidence_chunk_ids, *[chunk_id for node in typed_nodes for chunk_id in node.evidence_chunk_ids]])
        source_locators = _unique_locators([*candidate.source_locators, *[node.source_locator for node in typed_nodes]])
        decisions.append(
            IntegrationDecision(
                id=stable_id("integration_decision", "conflict", candidate.id),
                action=IntegrationAction.conflict,
                target_node_ids=[node.id for node in typed_nodes],
                retained_content="保留冲突两侧原始说法，等待教师裁定；不直接合并或删除。",
                reason=f"{candidate.reason} 阶段 8 将其标为 conflict，压缩时强制保留两侧证据。",
                confidence=candidate.confidence,
                evidence_chunk_ids=evidence_chunk_ids,
                source_locators=source_locators,
                metadata={
                    "alignment_candidate_id": candidate.id,
                    "alignment_relation_type": candidate.relation_type.value,
                    "source_node_name": typed_nodes[0].name,
                    "target_node_name": typed_nodes[1].name,
                    "teacher_review_required": True,
                },
            )
        )
    return decisions, conflict_node_ids


def _cluster_drafts(
    alignment: AlignmentResponse,
    node_by_id: dict[str, KnowledgeNode],
    degree_by_node_id: dict[str, int],
    conflict_node_ids: set[str],
) -> tuple[list[ConceptDraft], set[str]]:
    candidates_by_cluster = _candidates_by_cluster(alignment)
    drafts: list[ConceptDraft] = []
    covered_node_ids: set[str] = set()
    for cluster in alignment.clusters:
        members = [node_by_id[node_id] for node_id in cluster.member_node_ids if node_id in node_by_id]
        if len(members) < 2:
            continue
        covered_node_ids.update(node.id for node in members)
        cluster_candidates = candidates_by_cluster.get(cluster.id, [])
        action = IntegrationAction.refine if any(candidate.relation_type == AlignmentRelationType.refines for candidate in cluster_candidates) else IntegrationAction.merge
        representative = _representative_node(members, degree_by_node_id)
        evidence_chunk_ids = _unique_texts([*cluster.evidence_chunk_ids, *[chunk_id for node in members for chunk_id in node.evidence_chunk_ids]])
        source_locators = _unique_locators([node.source_locator for node in members])
        redundant_nodes = [node for node in members if node.id != representative.id]
        reason = _cluster_reason(cluster.canonical_name, action, representative, redundant_nodes, cluster_candidates)
        removed_redundancy = _redundancy_summary(representative, redundant_nodes, action)
        definition = _cluster_definition(representative, redundant_nodes, action)
        drafts.append(
            ConceptDraft(
                canonical_name=cluster.canonical_name,
                member_node_ids=[node.id for node in members],
                action=action,
                full_definition=definition,
                cluster_id=cluster.id,
                confidence=cluster.confidence,
                importance=sum(_node_importance(node, degree_by_node_id) for node in members),
                evidence_chunk_ids=evidence_chunk_ids,
                source_locators=source_locators,
                removed_redundancy=removed_redundancy,
                reason=reason,
                force_retain=any(node.id in conflict_node_ids for node in members),
                metadata={
                    "representative_node_id": representative.id,
                    "representative_node_name": representative.name,
                    "alignment_candidate_ids": [candidate.id for candidate in cluster_candidates],
                    "source_node_names": [node.name for node in members],
                    "compression_basis": "most_complete_definition_plus_unique_supplements",
                },
            )
        )
    return drafts, covered_node_ids


def _singleton_drafts(
    node_by_id: dict[str, KnowledgeNode],
    degree_by_node_id: dict[str, int],
    covered_node_ids: set[str],
    conflict_node_ids: set[str],
) -> list[ConceptDraft]:
    drafts: list[ConceptDraft] = []
    for node in node_by_id.values():
        if node.id in covered_node_ids:
            continue
        importance = _node_importance(node, degree_by_node_id)
        conflict_guarded = node.id in conflict_node_ids
        drafts.append(
            ConceptDraft(
                canonical_name=node.name,
                member_node_ids=[node.id],
                action=IntegrationAction.keep,
                full_definition=_node_text(node),
                confidence=node.confidence,
                importance=importance,
                evidence_chunk_ids=list(node.evidence_chunk_ids),
                source_locators=[node.source_locator],
                reason=_keep_reason(node, importance, conflict_guarded),
                force_retain=conflict_guarded or importance >= 4.5,
                metadata={
                    "source_node_name": node.name,
                    "source_node_type": node.node_type.value,
                    "frequency": int(node.metadata.get("frequency", 1)),
                    "degree": degree_by_node_id.get(node.id, 0),
                    "conflict_guarded": conflict_guarded,
                },
            )
        )
    return sorted(drafts, key=lambda item: (-item.importance, item.canonical_name))


def _apply_compression_budget(
    drafts: list[ConceptDraft],
    original_char_count: int,
    target_compression_ratio: float,
) -> tuple[list[ConceptDraft], list[ConceptDraft]]:
    budget = max(1, int(original_char_count * target_compression_ratio))
    retained = list(drafts)
    removed: list[ConceptDraft] = []

    while _minimum_char_need(retained) > budget:
        removable = [draft for draft in retained if draft.action == IntegrationAction.keep and not draft.force_retain]
        if not removable:
            break
        victim = sorted(removable, key=lambda item: (item.importance, len(item.full_definition), item.canonical_name))[0]
        retained.remove(victim)
        victim.action = IntegrationAction.remove
        victim.reason = (
            f"{victim.canonical_name} 为低频/低连接度 singleton，阶段 8 为满足压缩预算将其从整合正文移除；"
            "原始节点和证据不删除，可在溯源中恢复。"
        )
        victim.removed_redundancy = victim.full_definition
        removed.append(victim)

    _assign_content_budget(retained, budget)
    return retained, removed


def _minimum_char_need(drafts: list[ConceptDraft]) -> int:
    return sum(min(len(_collapse_text(draft.full_definition)), MIN_CONCEPT_CHARS) for draft in drafts)


def _assign_content_budget(drafts: list[ConceptDraft], budget: int) -> None:
    if not drafts:
        return
    sorted_drafts = sorted(drafts, key=lambda item: (-item.importance, item.canonical_name))
    weight_total = sum(max(1.0, draft.importance) for draft in sorted_drafts) or 1.0
    remaining_budget = budget
    remaining_weight = weight_total
    for index, draft in enumerate(sorted_drafts):
        text = _collapse_text(draft.full_definition)
        if index == len(sorted_drafts) - 1:
            limit = remaining_budget
        else:
            share = max(HARD_MIN_CONCEPT_CHARS, int(remaining_budget * (max(1.0, draft.importance) / remaining_weight)))
            limit = min(share, remaining_budget - HARD_MIN_CONCEPT_CHARS * (len(sorted_drafts) - index - 1))
        limit = max(1, limit)
        draft.definition = _truncate_text(text, limit)
        remaining_budget -= len(draft.definition)
        remaining_weight -= max(1.0, draft.importance)

    overflow = sum(len(draft.definition) for draft in sorted_drafts) - budget
    if overflow <= 0:
        return
    for draft in reversed(sorted_drafts):
        if overflow <= 0:
            break
        removable = max(0, len(draft.definition) - HARD_MIN_CONCEPT_CHARS)
        if removable <= 0:
            continue
        shrink_by = min(removable, overflow)
        draft.definition = _truncate_text(draft.definition, len(draft.definition) - shrink_by)
        overflow -= shrink_by
    if overflow <= 0:
        return
    for draft in reversed(sorted_drafts):
        if overflow <= 0:
            break
        removable = max(0, len(draft.definition) - 1)
        if removable <= 0:
            continue
        shrink_by = min(removable, overflow)
        draft.definition = _truncate_text(draft.definition, len(draft.definition) - shrink_by)
        overflow -= shrink_by


def _materialize(
    retained_drafts: list[ConceptDraft],
    removed_drafts: list[ConceptDraft],
    conflict_decisions: list[IntegrationDecision],
    include_keep_decisions: bool,
    conflict_node_ids: set[str],
) -> tuple[list[IntegrationDecision], list[IntegratedConcept]]:
    decisions: list[IntegrationDecision] = list(conflict_decisions)
    conflict_decision_ids_by_node: dict[str, list[str]] = {}
    for decision in conflict_decisions:
        for node_id in decision.target_node_ids:
            conflict_decision_ids_by_node.setdefault(node_id, []).append(decision.id)

    for draft in retained_drafts:
        if draft.action == IntegrationAction.keep and not include_keep_decisions:
            continue
        draft.decision_id = stable_id("integration_decision", draft.action.value, draft.cluster_id or draft.canonical_name, *draft.member_node_ids)
        decisions.append(
            IntegrationDecision(
                id=draft.decision_id,
                cluster_id=draft.cluster_id,
                action=draft.action,
                target_node_ids=draft.member_node_ids,
                retained_content=draft.definition,
                removed_redundancy=draft.removed_redundancy,
                reason=draft.reason,
                confidence=round(draft.confidence, 4),
                evidence_chunk_ids=draft.evidence_chunk_ids,
                source_locators=draft.source_locators,
                metadata={
                    **draft.metadata,
                    "conflict_decision_ids": _unique_texts([item for node_id in draft.member_node_ids for item in conflict_decision_ids_by_node.get(node_id, [])]),
                    "retained_char_count": len(draft.definition),
                    "source_action": draft.action.value,
                },
            )
        )

    for draft in removed_drafts:
        decision_id = stable_id("integration_decision", "remove", draft.canonical_name, *draft.member_node_ids)
        decisions.append(
            IntegrationDecision(
                id=decision_id,
                cluster_id=draft.cluster_id,
                action=IntegrationAction.remove,
                target_node_ids=draft.member_node_ids,
                retained_content=None,
                removed_redundancy=draft.removed_redundancy,
                reason=draft.reason,
                confidence=round(max(0.55, min(0.86, draft.confidence or 0.72)), 4),
                evidence_chunk_ids=draft.evidence_chunk_ids,
                source_locators=draft.source_locators,
                metadata={
                    **draft.metadata,
                    "compression_decision": "removed_from_integrated_body_only",
                    "source_action": "remove",
                },
            )
        )

    concepts: list[IntegratedConcept] = []
    for draft in retained_drafts:
        decision_ids = [decision.id for decision in decisions if any(node_id in draft.member_node_ids for node_id in decision.target_node_ids)]
        concepts.append(
            IntegratedConcept(
                id=stable_id("integrated_concept", draft.canonical_name, *draft.member_node_ids),
                canonical_name=draft.canonical_name,
                member_node_ids=draft.member_node_ids,
                decision_ids=_unique_texts(decision_ids),
                definition=draft.definition,
                summary=_summary_for_concept(draft),
                source_locators=draft.source_locators,
                evidence_chunk_ids=draft.evidence_chunk_ids,
                confidence=round(draft.confidence, 4),
                metadata={
                    **draft.metadata,
                    "action": draft.action.value,
                    "member_count": len(draft.member_node_ids),
                    "contains_conflict_guarded_node": any(node_id in conflict_node_ids for node_id in draft.member_node_ids),
                },
            )
        )
    return _sort_decisions(decisions), sorted(concepts, key=lambda item: (item.canonical_name, item.id))


def _compression_stats(
    original_char_count: int,
    original_node_count: int,
    target_compression_ratio: float,
    decisions: list[IntegrationDecision],
    integrated_concepts: list[IntegratedConcept],
    metadata: dict[str, object],
) -> CompressionStats:
    retained_char_count = sum(len(concept.definition) for concept in integrated_concepts)
    compression_ratio = round(retained_char_count / original_char_count, 4) if original_char_count else 0.0
    action_counts = {action: sum(1 for decision in decisions if decision.action == action) for action in IntegrationAction}
    evidence_complete = sum(1 for decision in decisions if decision.reason and decision.confidence > 0 and decision.evidence_chunk_ids and decision.source_locators)
    return CompressionStats(
        original_char_count=original_char_count,
        retained_char_count=retained_char_count,
        original_node_count=original_node_count,
        integrated_node_count=len(integrated_concepts),
        merged_node_count=sum(max(0, len(decision.target_node_ids) - 1) for decision in decisions if decision.action == IntegrationAction.merge),
        kept_node_count=sum(len(decision.target_node_ids) for decision in decisions if decision.action == IntegrationAction.keep),
        removed_node_count=sum(len(decision.target_node_ids) for decision in decisions if decision.action == IntegrationAction.remove),
        refined_node_count=sum(max(1, len(decision.target_node_ids) - 1) for decision in decisions if decision.action == IntegrationAction.refine),
        conflict_count=action_counts[IntegrationAction.conflict],
        target_compression_ratio=target_compression_ratio,
        compression_ratio=compression_ratio,
        node_reduction_ratio=round(max(0, original_node_count - len(integrated_concepts)) / original_node_count, 4) if original_node_count else 0.0,
        evidence_coverage_ratio=round(evidence_complete / len(decisions), 4) if decisions else 0.0,
        metadata={
            **metadata,
            "action_counts": {action.value: count for action, count in action_counts.items()},
            "compression_budget_chars": int(original_char_count * target_compression_ratio),
            "compression_target_met": compression_ratio <= target_compression_ratio if original_char_count else True,
        },
    )


def _candidates_by_cluster(alignment: AlignmentResponse) -> dict[str, list[AlignmentCandidate]]:
    by_cluster: dict[str, list[AlignmentCandidate]] = {}
    for cluster in alignment.clusters:
        member_ids = set(cluster.member_node_ids)
        by_cluster[cluster.id] = [
            candidate
            for candidate in alignment.candidates
            if candidate.source_node_id in member_ids and candidate.target_node_id in member_ids
        ]
    return by_cluster


def _cluster_reason(
    canonical_name: str,
    action: IntegrationAction,
    representative: KnowledgeNode,
    redundant_nodes: list[KnowledgeNode],
    candidates: list[AlignmentCandidate],
) -> str:
    candidate_reasons = "；".join(candidate.reason for candidate in candidates[:2])
    names = "、".join(node.name for node in redundant_nodes) or canonical_name
    if action == IntegrationAction.refine:
        return (
            f"{canonical_name} 的跨教材说法存在粒度差异，保留 {representative.name} 的完整定义并吸收 {names} 的补充信息；"
            f"依据：{candidate_reasons or '定义长度和上下文差异'}。"
        )
    return (
        f"{canonical_name} 在多本教材中被判定为同一/别名概念，保留 {representative.name} 的较完整定义，"
        f"将 {names} 的重复解释并入冗余记录；依据：{candidate_reasons or '对齐置信度和证据重合'}。"
    )


def _cluster_definition(representative: KnowledgeNode, redundant_nodes: list[KnowledgeNode], action: IntegrationAction) -> str:
    base = _node_text(representative)
    supplements: list[str] = []
    base_tokens = set(_tokenize(base))
    for node in redundant_nodes:
        text = _node_text(node)
        if not text:
            continue
        overlap = len(base_tokens.intersection(_tokenize(text)))
        if action == IntegrationAction.refine or overlap < max(2, len(base_tokens) // 5):
            supplements.append(text)
    if not supplements:
        return base
    return f"{base} 补充：{' '.join(supplements[:2])}"


def _redundancy_summary(representative: KnowledgeNode, redundant_nodes: list[KnowledgeNode], action: IntegrationAction) -> str | None:
    if not redundant_nodes:
        return None
    prefix = "保留为补充差异" if action == IntegrationAction.refine else "重复解释已压缩"
    details = [f"{node.name}: {_truncate_text(_node_text(node), 80)}" for node in redundant_nodes]
    return f"{prefix}；" + "；".join(details)


def _representative_node(nodes: list[KnowledgeNode], degree_by_node_id: dict[str, int]) -> KnowledgeNode:
    return sorted(
        nodes,
        key=lambda node: (
            -len(_node_text(node)),
            -degree_by_node_id.get(node.id, 0),
            -len(node.evidence_chunk_ids),
            node.name,
        ),
    )[0]


def _node_importance(node: KnowledgeNode, degree_by_node_id: dict[str, int]) -> float:
    frequency = int(node.metadata.get("frequency", 1))
    degree = degree_by_node_id.get(node.id, 0)
    evidence_count = len(node.evidence_chunk_ids)
    category = str(node.metadata.get("category") or "")
    core_bonus = 1.5 if any(marker in category for marker in ("核心", "机制", "结构", "病理")) else 0.0
    name_bonus = 1.2 if any(marker in node.name for marker in ("基础", "机制", "过程", "系统", "细胞", "反应", "电位", "炎症", "免疫")) else 0.0
    return round(frequency * 1.4 + degree * 1.8 + evidence_count * 0.6 + core_bonus + name_bonus, 4)


def _keep_reason(node: KnowledgeNode, importance: float, conflict_guarded: bool) -> str:
    if conflict_guarded:
        return f"{node.name} 参与冲突候选，阶段 8 必须保留原始说法，等待教师裁定。"
    degree = int(node.metadata.get("frequency", 1))
    return f"{node.name} 未命中可合并重复项，重要度 {importance:.2f}，频次 {degree}，作为独立知识点保留。"


def _summary_for_concept(draft: ConceptDraft) -> str:
    if draft.action == IntegrationAction.merge:
        return f"{draft.canonical_name} 已跨教材合并，保留代表定义并记录冗余来源。"
    if draft.action == IntegrationAction.refine:
        return f"{draft.canonical_name} 保留主定义和补充差异，等待教师可选精修。"
    return f"{draft.canonical_name} 作为独立知识点保留。"


def _node_text(node: KnowledgeNode) -> str:
    source_quote = str(node.metadata.get("source_quote") or "")
    return _collapse_text(node.definition or source_quote or node.name)


def _truncate_text(text: str, limit: int) -> str:
    clean = _collapse_text(text)
    if limit <= 0:
        return ""
    if len(clean) <= limit:
        return clean
    if limit <= 1:
        return clean[:limit]
    return clean[: max(1, limit - 1)].rstrip(" ，,；;。") + "…"


def _collapse_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fa5]{2,}", text):
        tokens.extend(segment[index : index + 2] for index in range(max(0, len(segment) - 1)))
    tokens.extend(re.findall(r"[A-Za-z0-9_]{2,}", text.lower()))
    return tokens


def _unique_texts(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _unique_locators(locators: list[SourceLocator]) -> list[SourceLocator]:
    seen: set[str] = set()
    unique: list[SourceLocator] = []
    for locator in locators:
        key = json.dumps(locator.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(locator)
    return unique


def _sort_decisions(decisions: list[IntegrationDecision]) -> list[IntegrationDecision]:
    action_order = {
        IntegrationAction.conflict: 0,
        IntegrationAction.refine: 1,
        IntegrationAction.merge: 2,
        IntegrationAction.keep: 3,
        IntegrationAction.remove: 4,
    }
    return sorted(decisions, key=lambda decision: (action_order[decision.action], decision.cluster_id or "", decision.id))
