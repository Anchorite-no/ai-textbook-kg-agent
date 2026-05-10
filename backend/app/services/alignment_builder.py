from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.models.schemas import (
    AliasRecord,
    AlignmentBuildRequest,
    AlignmentCandidate,
    AlignmentRelationType,
    AlignmentResponse,
    AlignmentSignal,
    CanonicalConcept,
    ConceptCluster,
    GraphResponse,
    KnowledgeNode,
)
from app.services.alignment_storage import load_alignment, save_alignment
from app.services.converted_textbook_importer import stable_id
from app.services.graph_storage import load_graph


HASH_DIM = 256
ALIAS_CANONICALS = {
    "白血球": "白细胞",
    "白细胞": "白细胞",
    "leukocyte": "白细胞",
    "leucocyte": "白细胞",
    "whitebloodcell": "白细胞",
    "wbc": "白细胞",
    "动作电位": "动作电位",
    "actionpotential": "动作电位",
    "静息电位": "静息电位",
    "restingpotential": "静息电位",
    "炎症": "炎症",
    "inflammation": "炎症",
    "抗体": "抗体",
    "antibody": "抗体",
    "抗原": "抗原",
    "antigen": "抗原",
}
STOP_TOKENS = {"章节", "内容", "核心", "概念", "定义", "功能", "结构", "过程", "机制"}


@dataclass(frozen=True)
class NodeRecord:
    graph: GraphResponse
    node: KnowledgeNode
    raw_file_id: str
    textbook: str
    normalized_name: str
    canonical_key: str
    aliases: tuple[str, ...]
    definition_tokens: frozenset[str]
    context_tokens: frozenset[str]
    neighbor_keys: frozenset[str]
    embedding: dict[str, float]


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def build_alignment(request: AlignmentBuildRequest) -> tuple[AlignmentResponse, str, bool]:
    existing = load_alignment(sorted(request.raw_file_ids))
    if existing is not None and not request.force_rebuild:
        return existing, str(save_alignment(existing)), True

    graphs = _load_graphs(request.raw_file_ids)
    records = _node_records(graphs)[: request.max_nodes]
    candidates = _alignment_candidates(records, request.min_confidence)
    clusters = _clusters(records, candidates, request)
    canonical_concepts = _canonical_concepts(records, clusters, candidates)
    aliases = _alias_records(records, clusters, candidates)

    raw_file_ids = sorted({graph.raw_file_id for graph in graphs})
    response = AlignmentResponse(
        id=stable_id("alignment", *raw_file_ids, "stage7_v1", request.min_confidence, request.include_singletons),
        raw_file_ids=raw_file_ids,
        canonical_concepts=canonical_concepts,
        aliases=aliases,
        clusters=clusters,
        candidates=candidates,
        generated_at=datetime.utcnow(),
        metadata={
            "builder": "stage7_alignment_builder",
            "node_count": len(records),
            "candidate_count": len(candidates),
            "cluster_count": len(clusters),
            "canonical_concept_count": len(canonical_concepts),
            "min_confidence": request.min_confidence,
            "signals": ["normalized_name", "alias_table", "definition_similarity", "context_similarity", "neighbor_similarity", "hash_embedding"],
            "stage_boundary": "阶段 7 只输出候选对齐和 ConceptCluster，不生成 merge/keep/remove 压缩决策。",
        },
    )
    path = save_alignment(response)
    return response, str(path), False


def _load_graphs(raw_file_ids: list[str]) -> list[GraphResponse]:
    if raw_file_ids:
        graphs = [graph for raw_file_id in raw_file_ids if (graph := load_graph(raw_file_id)) is not None]
    else:
        graphs = []
        if settings.graph_data_dir.exists():
            for path in sorted(settings.graph_data_dir.glob("raw_*.json")):
                graphs.append(GraphResponse.model_validate_json(path.read_text(encoding="utf-8")))
    if len(graphs) < 2:
        raise ValueError("Stage 7 alignment requires at least two built textbook graphs.")
    return graphs


def _node_records(graphs: list[GraphResponse]) -> list[NodeRecord]:
    records: list[NodeRecord] = []
    node_by_id: dict[str, KnowledgeNode] = {}
    for graph in graphs:
        for node in graph.nodes:
            node_by_id[node.id] = node

    neighbor_names: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    for graph in graphs:
        for edge in graph.edges:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            neighbor_names[source.id].add(target.name)
            neighbor_names[target.id].add(source.name)

    for graph in graphs:
        for node in graph.nodes:
            normalized_name = _normalize_term(node.name)
            aliases = tuple(
                dict.fromkeys(
                    [
                        normalized_name,
                        *[_normalize_term(alias) for alias in node.aliases],
                        *_aliases_from_text(node.name),
                        *_explicit_aliases_for_node(node.name, node.definition or ""),
                    ]
                )
            )
            canonical_key = _canonical_key(normalized_name, aliases)
            definition_tokens = frozenset(_text_tokens(node.definition or ""))
            context_tokens = frozenset(_text_tokens(str(node.metadata.get("chapter") or "")))
            neighbor_keys = frozenset(_canonical_key(_normalize_term(name), tuple(_aliases_from_text(name))) for name in neighbor_names.get(node.id, set()))
            embedding_text = " ".join(
                [
                    node.name,
                    node.definition or "",
                    str(node.metadata.get("category") or ""),
                    str(node.metadata.get("chapter") or ""),
                ]
            )
            records.append(
                NodeRecord(
                    graph=graph,
                    node=node,
                    raw_file_id=graph.raw_file_id,
                    textbook=graph.title,
                    normalized_name=normalized_name,
                    canonical_key=canonical_key,
                    aliases=aliases,
                    definition_tokens=definition_tokens,
                    context_tokens=context_tokens,
                    neighbor_keys=neighbor_keys,
                    embedding=_hash_embedding(Counter(_text_tokens(embedding_text))),
                )
            )
    return records


def _alignment_candidates(records: list[NodeRecord], min_confidence: float) -> list[AlignmentCandidate]:
    candidates: list[AlignmentCandidate] = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            if left.node.id == right.node.id or left.raw_file_id == right.raw_file_id:
                continue
            signals = _signals(left, right)
            confidence = _confidence(signals)
            relation_type = _relation_type(left, right, signals, confidence)
            if confidence < min_confidence and relation_type != AlignmentRelationType.conflicts_with:
                continue
            reason = _candidate_reason(left, right, relation_type, signals, confidence)
            evidence_chunk_ids = list(dict.fromkeys([*left.node.evidence_chunk_ids, *right.node.evidence_chunk_ids]))
            candidates.append(
                AlignmentCandidate(
                    id=stable_id("align_candidate", left.node.id, right.node.id, relation_type.value),
                    source_node_id=left.node.id,
                    target_node_id=right.node.id,
                    relation_type=relation_type,
                    confidence=round(confidence, 4),
                    signals=signals,
                    evidence_chunk_ids=evidence_chunk_ids,
                    source_locators=[left.node.source_locator, right.node.source_locator],
                    reason=reason,
                    needs_teacher_review=_needs_review(relation_type, confidence),
                    metadata={
                        "source_textbook": left.textbook,
                        "target_textbook": right.textbook,
                        "source_name": left.node.name,
                        "target_name": right.node.name,
                        "canonical_key": left.canonical_key if left.canonical_key == right.canonical_key else None,
                    },
                )
            )
    return sorted(candidates, key=lambda item: (-item.confidence, item.relation_type.value, item.id))


def _signals(left: NodeRecord, right: NodeRecord) -> list[AlignmentSignal]:
    normalized_match = 1.0 if left.normalized_name and left.normalized_name == right.normalized_name else 0.0
    alias_match = 1.0 if _alias_overlap(left, right) else 0.0
    canonical_match = 1.0 if left.canonical_key and left.canonical_key == right.canonical_key else 0.0
    definition_similarity = _jaccard(left.definition_tokens, right.definition_tokens)
    context_similarity = _jaccard(left.context_tokens, right.context_tokens)
    neighbor_similarity = _jaccard(left.neighbor_keys, right.neighbor_keys)
    embedding_similarity = _cosine_similarity(left.embedding, right.embedding)
    return [
        AlignmentSignal(name="normalized_name", score=normalized_match, weight=0.24, detail="名称规范化后完全一致"),
        AlignmentSignal(name="alias_table", score=max(alias_match, canonical_match), weight=0.26, detail="alias 表或别名集合命中"),
        AlignmentSignal(name="definition_similarity", score=definition_similarity, weight=0.20, detail="定义 token Jaccard 相似度"),
        AlignmentSignal(name="context_similarity", score=context_similarity, weight=0.10, detail="章节/上下文 token 相似度"),
        AlignmentSignal(name="neighbor_similarity", score=neighbor_similarity, weight=0.10, detail="图谱邻居 canonical key 相似度"),
        AlignmentSignal(name="hash_embedding", score=embedding_similarity, weight=0.10, detail="本地 hash embedding 余弦相似度"),
    ]


def _confidence(signals: list[AlignmentSignal]) -> float:
    weighted = sum(signal.score * signal.weight for signal in signals)
    total_weight = sum(signal.weight for signal in signals) or 1.0
    score = weighted / total_weight
    by_name = {signal.name: signal.score for signal in signals}
    if by_name.get("normalized_name", 0.0) >= 1.0:
        score = max(score, 0.9 + 0.05 * by_name.get("definition_similarity", 0.0))
    if by_name.get("alias_table", 0.0) >= 1.0:
        score = max(
            score,
            0.78
            + 0.10 * by_name.get("definition_similarity", 0.0)
            + 0.05 * by_name.get("context_similarity", 0.0)
            + 0.05 * by_name.get("hash_embedding", 0.0),
        )
    return max(0.0, min(1.0, score))


def _relation_type(
    left: NodeRecord,
    right: NodeRecord,
    signals: list[AlignmentSignal],
    confidence: float,
) -> AlignmentRelationType:
    if _looks_conflicting(left, right) and (left.canonical_key == right.canonical_key or _alias_overlap(left, right)):
        return AlignmentRelationType.conflicts_with
    alias_score = next(signal.score for signal in signals if signal.name == "alias_table")
    normalized_score = next(signal.score for signal in signals if signal.name == "normalized_name")
    if alias_score >= 1 and normalized_score < 1:
        return AlignmentRelationType.alias_of
    if _looks_refinement(left, right) and confidence >= 0.58:
        return AlignmentRelationType.refines
    return AlignmentRelationType.same_as


def _clusters(
    records: list[NodeRecord],
    candidates: list[AlignmentCandidate],
    request: AlignmentBuildRequest,
) -> list[ConceptCluster]:
    by_id = {record.node.id: record for record in records}
    union_find = UnionFind(list(by_id.keys()))
    for candidate in candidates:
        if candidate.relation_type == AlignmentRelationType.conflicts_with:
            continue
        if candidate.confidence >= request.min_confidence:
            union_find.union(candidate.source_node_id, candidate.target_node_id)

    grouped: dict[str, list[NodeRecord]] = {}
    for record in records:
        grouped.setdefault(union_find.find(record.node.id), []).append(record)

    conflict_node_ids = {
        node_id
        for candidate in candidates
        if candidate.relation_type == AlignmentRelationType.conflicts_with
        for node_id in (candidate.source_node_id, candidate.target_node_id)
    }
    clusters: list[ConceptCluster] = []
    for members in grouped.values():
        if len(members) == 1 and not request.include_singletons:
            continue
        canonical_name = _canonical_name(members)
        aliases = _cluster_aliases(members, canonical_name)
        member_node_ids = [member.node.id for member in members]
        cluster_candidates = [candidate for candidate in candidates if candidate.source_node_id in member_node_ids and candidate.target_node_id in member_node_ids]
        confidence = _cluster_confidence(cluster_candidates, members)
        evidence_chunk_ids = list(dict.fromkeys(chunk_id for member in members for chunk_id in member.node.evidence_chunk_ids))
        clusters.append(
            ConceptCluster(
                id=stable_id("cluster", canonical_name, *sorted(member_node_ids)),
                canonical_name=canonical_name,
                aliases=aliases,
                member_node_ids=member_node_ids,
                evidence_chunk_ids=evidence_chunk_ids,
                confidence=confidence,
                metadata={
                    "raw_file_ids": sorted({member.raw_file_id for member in members}),
                    "textbooks": sorted({member.textbook for member in members}),
                    "member_count": len(members),
                    "candidate_ids": [candidate.id for candidate in cluster_candidates],
                    "needs_teacher_review": any(member.node.id in conflict_node_ids for member in members),
                    "stage_boundary": "ConceptCluster is an alignment candidate, not a merge/remove decision.",
                },
            )
        )
    return sorted(clusters, key=lambda item: (-item.confidence, item.canonical_name))


def _canonical_concepts(
    records: list[NodeRecord],
    clusters: list[ConceptCluster],
    candidates: list[AlignmentCandidate],
) -> list[CanonicalConcept]:
    by_id = {record.node.id: record for record in records}
    conflict_pairs = {(candidate.source_node_id, candidate.target_node_id) for candidate in candidates if candidate.relation_type == AlignmentRelationType.conflicts_with}
    concepts: list[CanonicalConcept] = []
    for cluster in clusters:
        members = [by_id[node_id] for node_id in cluster.member_node_ids if node_id in by_id]
        if not members:
            continue
        representative = _representative_member(members)
        concepts.append(
            CanonicalConcept(
                id=stable_id("canonical", cluster.id, cluster.canonical_name),
                canonical_name=cluster.canonical_name,
                cluster_id=cluster.id,
                aliases=cluster.aliases,
                member_node_ids=cluster.member_node_ids,
                definition=representative.node.definition,
                source_locators=[member.node.source_locator for member in members],
                evidence_chunk_ids=cluster.evidence_chunk_ids,
                confidence=cluster.confidence,
                metadata={
                    "representative_node_id": representative.node.id,
                    "representative_textbook": representative.textbook,
                    "conflict_pair_count": len(conflict_pairs),
                    "source_definitions": [
                        {
                            "node_id": member.node.id,
                            "textbook": member.textbook,
                            "definition": member.node.definition,
                        }
                        for member in members
                    ],
                },
            )
        )
    return concepts


def _alias_records(
    records: list[NodeRecord],
    clusters: list[ConceptCluster],
    candidates: list[AlignmentCandidate],
) -> list[AliasRecord]:
    by_id = {record.node.id: record for record in records}
    aliases: list[AliasRecord] = []
    for cluster in clusters:
        members = [by_id[node_id] for node_id in cluster.member_node_ids if node_id in by_id]
        for alias in cluster.aliases:
            alias_members = [member for member in members if alias in {member.node.name, member.normalized_name, *member.aliases}]
            if not alias_members:
                alias_members = members
            relation_type = _alias_relation_for(cluster.member_node_ids, candidates)
            aliases.append(
                AliasRecord(
                    id=stable_id("alias", cluster.id, alias),
                    alias=alias,
                    canonical_name=cluster.canonical_name,
                    node_ids=[member.node.id for member in alias_members],
                    relation_type=relation_type,
                    confidence=cluster.confidence,
                    evidence_chunk_ids=list(dict.fromkeys(chunk_id for member in alias_members for chunk_id in member.node.evidence_chunk_ids)),
                    source_locators=[member.node.source_locator for member in alias_members],
                    metadata={"cluster_id": cluster.id},
                )
            )
    return sorted(aliases, key=lambda item: (item.canonical_name, item.alias))


def _candidate_reason(
    left: NodeRecord,
    right: NodeRecord,
    relation_type: AlignmentRelationType,
    signals: list[AlignmentSignal],
    confidence: float,
) -> str:
    strong = [signal.name for signal in signals if signal.score >= 0.65]
    if relation_type == AlignmentRelationType.conflicts_with:
        return f"{left.node.name} 与 {right.node.name} 指向同一术语但定义中存在否定/冲突标记，需要教师复核。"
    if relation_type == AlignmentRelationType.alias_of:
        return f"{left.node.name} 与 {right.node.name} 命中 alias/canonical 表，置信度 {confidence:.2f}。"
    if relation_type == AlignmentRelationType.refines:
        return f"{left.node.name} 与 {right.node.name} 指向相近概念，但定义粒度不同，标记为 refine 候选。"
    return f"{left.node.name} 与 {right.node.name} 在 {', '.join(strong) or '弱信号组合'} 上相似，置信度 {confidence:.2f}。"


def _needs_review(relation_type: AlignmentRelationType, confidence: float) -> bool:
    return relation_type == AlignmentRelationType.conflicts_with or confidence < 0.78


def _alias_relation_for(node_ids: list[str], candidates: list[AlignmentCandidate]) -> AlignmentRelationType:
    candidate_relations = {
        candidate.relation_type
        for candidate in candidates
        if candidate.source_node_id in node_ids and candidate.target_node_id in node_ids
    }
    if AlignmentRelationType.alias_of in candidate_relations:
        return AlignmentRelationType.alias_of
    if AlignmentRelationType.refines in candidate_relations:
        return AlignmentRelationType.refines
    return AlignmentRelationType.same_as


def _cluster_confidence(candidates: list[AlignmentCandidate], members: list[NodeRecord]) -> float:
    if candidates:
        return round(sum(candidate.confidence for candidate in candidates) / len(candidates), 4)
    if len(members) == 1:
        return 1.0
    return 0.0


def _representative_member(members: list[NodeRecord]) -> NodeRecord:
    return sorted(
        members,
        key=lambda member: (
            -len(member.node.definition or ""),
            -len(member.node.evidence_chunk_ids),
            member.node.name,
        ),
    )[0]


def _canonical_name(members: list[NodeRecord]) -> str:
    canonical_counts: Counter[str] = Counter(member.canonical_key for member in members if member.canonical_key)
    for canonical, _count in canonical_counts.most_common():
        if canonical in ALIAS_CANONICALS.values():
            return canonical
    name_counts = Counter(member.node.name for member in members)
    return name_counts.most_common(1)[0][0]


def _cluster_aliases(members: list[NodeRecord], canonical_name: str) -> list[str]:
    aliases: list[str] = []
    for member in members:
        for alias in [member.node.name, member.normalized_name, *member.aliases]:
            if alias and alias != canonical_name and alias not in aliases:
                aliases.append(alias)
    return aliases


def _alias_overlap(left: NodeRecord, right: NodeRecord) -> bool:
    left_aliases = {left.normalized_name, left.canonical_key, *left.aliases}
    right_aliases = {right.normalized_name, right.canonical_key, *right.aliases}
    return bool(left_aliases.intersection(right_aliases))


def _canonical_key(normalized_name: str, aliases: tuple[str, ...]) -> str:
    for value in (normalized_name, *aliases):
        if value in ALIAS_CANONICALS:
            return ALIAS_CANONICALS[value]
    return normalized_name


def _normalize_term(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"（[^）]*）", "", value)
    value = re.sub(r"[\s_\-·,，。；;:：/\\()\[\]（）【】]+", "", value)
    return value.strip()


def _aliases_from_text(value: str) -> tuple[str, ...]:
    aliases: list[str] = []
    for match in re.findall(r"[\(（]([A-Za-z][A-Za-z\s\-]{1,40})[\)）]", value or ""):
        normalized = _normalize_term(match)
        if normalized:
            aliases.append(normalized)
    for phrase in re.findall(r"\b[A-Za-z][A-Za-z\s\-]{2,40}\b", value or ""):
        normalized = _normalize_term(phrase)
        if normalized:
            aliases.append(normalized)
    return tuple(dict.fromkeys(aliases))


def _explicit_aliases_for_node(name: str, text: str) -> tuple[str, ...]:
    aliases: list[str] = []
    normalized_name = _normalize_term(name)
    for left, right in re.findall(r"([\u4e00-\u9fa5A-Za-z\s\-]{2,40})(?:又称|也称|称为|指|called|also known as)([\u4e00-\u9fa5A-Za-z\s\-]{2,40})", text or "", flags=re.IGNORECASE):
        left_normalized = _normalize_term(left)
        if left_normalized != normalized_name:
            continue
        for value in (right,):
            normalized = _normalize_term(value)
            if normalized:
                aliases.append(normalized)
    return tuple(dict.fromkeys(aliases))


def _text_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    lowered = text.lower()
    tokens.extend(re.findall(r"[a-zA-Z0-9_]{2,}", lowered))
    for segment in re.findall(r"[\u4e00-\u9fa5]{2,}", text):
        tokens.extend(segment[index : index + 2] for index in range(max(0, len(segment) - 1)))
        tokens.extend(segment[index : index + 3] for index in range(max(0, len(segment) - 2)))
        if len(segment) <= 8:
            tokens.append(segment)
    return [token for token in tokens if token and token not in STOP_TOKENS]


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left.intersection(right)) / len(left.union(right))


def _hash_embedding(token_counts: Counter[str]) -> dict[str, float]:
    if not token_counts:
        return {}
    vector: dict[int, float] = {}
    norm = sum(token_counts.values()) or 1
    for token, count in token_counts.items():
        index = _stable_hash(token) % HASH_DIM
        sign = 1 if _stable_hash(f"{token}:sign") % 2 == 0 else -1
        vector[index] = vector.get(index, 0.0) + sign * count / norm
    magnitude = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {str(index): value / magnitude for index, value in vector.items()}


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return max(0.0, sum(value * right.get(index, 0.0) for index, value in left.items()))


def _stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _looks_refinement(left: NodeRecord, right: NodeRecord) -> bool:
    if not (left.canonical_key == right.canonical_key or _alias_overlap(left, right)):
        return False
    left_len = len(left.node.definition or "")
    right_len = len(right.node.definition or "")
    if min(left_len, right_len) == 0:
        return False
    length_ratio = max(left_len, right_len) / max(1, min(left_len, right_len))
    return length_ratio >= 1.55


def _looks_conflicting(left: NodeRecord, right: NodeRecord) -> bool:
    left_text = f"{left.node.name} {left.node.definition or ''}"
    right_text = f"{right.node.name} {right.node.definition or ''}"
    negative_markers = ("不是", "不属于", "不能", "无", "非")
    positive_markers = ("是", "属于", "可以", "有", "能")
    left_negative = any(marker in left_text for marker in negative_markers)
    right_negative = any(marker in right_text for marker in negative_markers)
    left_positive = any(marker in left_text for marker in positive_markers)
    right_positive = any(marker in right_text for marker in positive_markers)
    return (left_negative and right_positive) or (right_negative and left_positive)
