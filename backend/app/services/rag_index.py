from __future__ import annotations

import json
import math
import re
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models.schemas import (
    Chunk,
    JobRecord,
    RagCitation,
    RagIndexRequest,
    RagIndexStatus,
    RagQueryRequest,
    RagQueryResponse,
)
from app.services.parsed_storage import list_parsed_textbooks, load_parsed_textbook


INDEX_VERSION = "hybrid_bm25_hash_embedding_v1"
INDEX_FILENAME = "rag_index.json"
BM25_K1 = 1.5
BM25_B = 0.75
MIN_QUERY_COVERAGE = 0.12
HASH_EMBEDDING_DIM = 256
VECTOR_SCORE_WEIGHT = 2.0
QUERY_STOP_CHARS = set("的是么吗呢了和与对有前要先学")
QUERY_STOP_FRAGMENTS = ("什么", "为什么", "如何", "怎么", "定义", "基本", "作用", "关系", "哪些", "多少")


def build_rag_index(request: RagIndexRequest, job: JobRecord) -> RagIndexStatus:
    raw_file_ids = request.raw_file_ids or [summary.raw_file_id for summary in list_parsed_textbooks()]
    records: list[dict[str, Any]] = []
    seen_books: list[str] = []
    for raw_file_id in raw_file_ids:
        parsed = load_parsed_textbook(raw_file_id)
        if parsed is None:
            continue
        seen_books.append(raw_file_id)
        section_by_id = {section.id: section for section in parsed.sections}
        for chunk in parsed.chunks:
            if request.max_chunks is not None and len(records) >= request.max_chunks:
                break
            section = section_by_id.get(chunk.section_id)
            records.append(
                {
                    "chunk": chunk.model_dump(mode="json"),
                    "raw_file_id": parsed.raw_file.id,
                    "textbook": parsed.raw_file.title,
                    "format": parsed.raw_file.format,
                    "chapter": section.title if section is not None else None,
                    "section_id": chunk.section_id,
                    "tokens": _token_counts(chunk.text),
                    "embedding": _hash_embedding(_token_counts(chunk.text)),
                    "char_count": chunk.char_count,
                }
            )
    document_frequencies = _document_frequencies(records)
    avg_doc_len = _average_doc_length(records)
    payload = {
        "version": INDEX_VERSION,
        "built_by_job_id": job.id,
        "updated_at": datetime.utcnow().isoformat(),
        "raw_file_ids": seen_books,
        "textbook_count": len(seen_books),
        "chunk_count": len(records),
        "format_counts": dict(Counter(record["format"] for record in records)),
        "locator_coverage": _locator_coverage(records),
        "embedding": {
            "backend": "local_hash_embedding",
            "dimensions": HASH_EMBEDDING_DIM,
            "note": "轻量本地 embedding，用于阶段 4 证据索引；后续可替换 FAISS/Chroma。",
        },
        "document_frequencies": document_frequencies,
        "avg_doc_len": avg_doc_len,
        "records": records,
    }
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _status_from_payload(payload, path)


def get_rag_index_status() -> RagIndexStatus:
    payload = _load_index_payload()
    if payload is None:
        return RagIndexStatus(status="empty")
    return _status_from_payload(payload, _index_path())


def query_rag_index(request: RagQueryRequest) -> RagQueryResponse:
    payload = _load_index_payload()
    if payload is None or not payload.get("records"):
        return RagQueryResponse(
            question=request.question,
            answer="当前知识库中未找到相关信息。",
            metadata={"reason": "index_empty"},
        )

    query_terms = _query_token_counts(request.question)
    if not query_terms:
        return RagQueryResponse(
            question=request.question,
            answer="当前知识库中未找到相关信息。",
            metadata={"reason": "query_has_no_terms"},
        )

    records = payload["records"]
    if request.raw_file_ids:
        allowed = set(request.raw_file_ids)
        records = [record for record in records if record["raw_file_id"] in allowed]

    query_embedding = _hash_embedding(query_terms)
    scored: list[tuple[float, float, float, float, dict[str, int], dict[str, Any]]] = []
    for record in records:
        bm25_score = _bm25_score_record(query_terms, record, payload)
        vector_score = _cosine_similarity(query_embedding, record.get("embedding") or {})
        score = bm25_score + VECTOR_SCORE_WEIGHT * vector_score
        matched_terms = _matched_terms(query_terms, record)
        coverage = _query_coverage(query_terms, matched_terms)
        if score > 0 and coverage >= MIN_QUERY_COVERAGE:
            scored.append((score, bm25_score, vector_score, coverage, matched_terms, record))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    top = scored[: request.top_k]

    if not top:
        return RagQueryResponse(
            question=request.question,
            answer="当前知识库中未找到相关信息。",
            metadata={
                "reason": "no_grounded_match",
                "index_version": payload.get("version"),
                "min_query_coverage": MIN_QUERY_COVERAGE,
                "retrieval": "hybrid_bm25_hash_embedding_with_query_coverage",
                "embedding_backend": payload.get("embedding", {}).get("backend"),
            },
        )

    max_score = top[0][0] or 1.0
    citations: list[RagCitation] = []
    source_chunks: list[Chunk] = []
    answer_parts: list[str] = []
    for score, bm25_score, vector_score, coverage, matched_terms, record in top:
        chunk = Chunk.model_validate(record["chunk"])
        quote = _best_quote(request.question, chunk.text)
        source_chunks.append(chunk)
        normalized_score = min(1.0, score / max_score)
        citations.append(
            RagCitation(
                chunk_id=chunk.id,
                raw_file_id=record["raw_file_id"],
                textbook=record["textbook"],
                chapter=record.get("chapter"),
                source_locator=chunk.source_locator,
                relevance_score=round(normalized_score, 4),
                quote=quote,
                metadata={
                    "retrieval": "hybrid_bm25_hash_embedding_with_query_coverage",
                    "raw_score": round(score, 6),
                    "bm25_score": round(bm25_score, 6),
                    "vector_score": round(vector_score, 6),
                    "query_coverage": round(coverage, 4),
                    "matched_terms": matched_terms,
                    "section_id": record.get("section_id"),
                    "format": record.get("format"),
                    "quote_hash": chunk.source_locator.quote_hash,
                },
            )
        )
        locator = chunk.source_locator.locator_text
        answer_parts.append(f"{quote} [{record['textbook']}, {record.get('chapter') or '未分章'}, {locator}]")

    return RagQueryResponse(
        question=request.question,
        answer="\n".join(answer_parts),
        citations=citations,
        source_chunks=source_chunks,
        metadata={
            "index_version": payload.get("version"),
            "retrieval": "hybrid_bm25_hash_embedding_with_query_coverage",
            "embedding_backend": payload.get("embedding", {}).get("backend"),
            "embedding_dimensions": payload.get("embedding", {}).get("dimensions"),
            "top_k": request.top_k,
            "matched_count": len(top),
            "textbook_count": payload.get("textbook_count", 0),
            "chunk_count": payload.get("chunk_count", 0),
            "min_query_coverage": MIN_QUERY_COVERAGE,
        },
    )


def _index_path() -> Path:
    return settings.index_data_dir / INDEX_FILENAME


def _load_index_payload() -> dict[str, Any] | None:
    path = _index_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _status_from_payload(payload: dict[str, Any], path: Path) -> RagIndexStatus:
    updated_at_raw = payload.get("updated_at")
    updated_at = datetime.fromisoformat(updated_at_raw) if updated_at_raw else None
    return RagIndexStatus(
        status="ready" if payload.get("chunk_count", 0) > 0 else "empty",
        textbook_count=int(payload.get("textbook_count", 0)),
        chunk_count=int(payload.get("chunk_count", 0)),
        raw_file_ids=list(payload.get("raw_file_ids") or []),
        index_path=str(path),
        updated_at=updated_at,
        metadata={
            "version": payload.get("version"),
            "built_by_job_id": payload.get("built_by_job_id"),
            "retrieval": "hybrid_bm25_hash_embedding_with_query_coverage",
            "embedding_backend": (payload.get("embedding") or {}).get("backend"),
            "embedding_dimensions": (payload.get("embedding") or {}).get("dimensions"),
            "avg_doc_len": payload.get("avg_doc_len"),
            "format_counts": payload.get("format_counts") or {},
            "locator_coverage": payload.get("locator_coverage") or {},
        },
    )


def _token_counts(text: str) -> dict[str, int]:
    tokens: list[str] = []
    lowered = text.lower()
    tokens.extend(re.findall(r"[a-zA-Z0-9_]{2,}", lowered))
    cjk = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
    for segment in cjk:
        tokens.extend(segment[index : index + 2] for index in range(max(0, len(segment) - 1)))
        tokens.extend(segment[index : index + 3] for index in range(max(0, len(segment) - 2)))
        if len(segment) <= 8:
            tokens.append(segment)
    return dict(Counter(token for token in tokens if token.strip()))


def _query_token_counts(text: str) -> dict[str, int]:
    raw_terms = _token_counts(text)
    filtered: dict[str, int] = {}
    for token, count in raw_terms.items():
        if _is_query_stop_token(token):
            continue
        filtered[token] = count
    return filtered or raw_terms


def _is_query_stop_token(token: str) -> bool:
    if token in QUERY_STOP_FRAGMENTS:
        return True
    if any(fragment in token for fragment in QUERY_STOP_FRAGMENTS):
        return True
    if re.search(r"[\u4e00-\u9fa5]", token) and any(char in QUERY_STOP_CHARS for char in token):
        return True
    return False


def _document_frequencies(records: list[dict[str, Any]]) -> dict[str, int]:
    frequencies: Counter[str] = Counter()
    for record in records:
        frequencies.update(record["tokens"].keys())
    return dict(frequencies)


def _average_doc_length(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    return sum(sum(record["tokens"].values()) for record in records) / len(records)


def _bm25_score_record(query_terms: dict[str, int], record: dict[str, Any], payload: dict[str, Any]) -> float:
    token_counts = record["tokens"]
    score = 0.0
    total_docs = max(1, int(payload.get("chunk_count") or len(payload.get("records") or [])))
    document_frequencies = payload.get("document_frequencies") or {}
    avg_doc_len = float(payload.get("avg_doc_len") or 1.0)
    doc_len = max(1, sum(token_counts.values()))
    for term, query_count in query_terms.items():
        term_frequency = token_counts.get(term, 0)
        if term_frequency:
            doc_frequency = int(document_frequencies.get(term, 1))
            idf = math.log(1 + (total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5))
            denominator = term_frequency + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / avg_doc_len)
            score += idf * ((term_frequency * (BM25_K1 + 1)) / denominator) * query_count
    text = record["chunk"]["text"]
    for term in query_terms:
        if len(term) >= 3 and term in text:
            score += 2.0
    return score


def _hash_embedding(token_counts: dict[str, int]) -> dict[str, float]:
    vector: dict[int, float] = {}
    norm = sum(token_counts.values()) or 1
    for token, count in token_counts.items():
        token_hash = _stable_hash(token)
        index = token_hash % HASH_EMBEDDING_DIM
        sign = 1 if _stable_hash(f"{token}:sign") % 2 == 0 else -1
        vector[index] = vector.get(index, 0.0) + sign * (count / norm)
    magnitude = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {str(index): round(value / magnitude, 6) for index, value in vector.items() if value}


def _stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    score = 0.0
    for index, value in left.items():
        score += value * float(right.get(index, 0.0))
    return max(0.0, score)


def _matched_terms(query_terms: dict[str, int], record: dict[str, Any]) -> dict[str, int]:
    token_counts = record["tokens"]
    text = record["chunk"]["text"]
    matched: dict[str, int] = {}
    for term in query_terms:
        count = int(token_counts.get(term, 0))
        if not count and len(term) >= 3 and term in text:
            count = 1
        if count:
            matched[term] = count
    return matched


def _query_coverage(query_terms: dict[str, int], matched_terms: dict[str, int]) -> float:
    if not query_terms:
        return 0.0
    matched_weight = sum(query_terms[term] for term in matched_terms)
    total_weight = sum(query_terms.values())
    return matched_weight / max(1, total_weight)


def _locator_coverage(records: list[dict[str, Any]]) -> dict[str, float]:
    if not records:
        return {"source_locator": 0.0, "page": 0.0, "line": 0.0, "sheet_row": 0.0, "slide": 0.0}
    total = len(records)
    source_locator = 0
    page = 0
    line = 0
    sheet_row = 0
    slide = 0
    for record in records:
        locator = record["chunk"].get("source_locator") or {}
        if locator.get("locator_text"):
            source_locator += 1
        if locator.get("page_start") is not None or locator.get("page_end") is not None:
            page += 1
        if locator.get("line_start") is not None or locator.get("line_end") is not None:
            line += 1
        if locator.get("sheet_name") is not None or locator.get("row_start") is not None or locator.get("row_end") is not None:
            sheet_row += 1
        if locator.get("slide_number") is not None:
            slide += 1
    return {
        "source_locator": round(source_locator / total, 4),
        "page": round(page / total, 4),
        "line": round(line / total, 4),
        "sheet_row": round(sheet_row / total, 4),
        "slide": round(slide / total, 4),
    }


def _best_quote(question: str, text: str, limit: int = 180) -> str:
    terms = _query_token_counts(question)
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？!?；;])", text) if sentence.strip()]
    if not sentences:
        return text[:limit]
    intent_markers = _intent_markers(question)
    ranked = sorted(
        sentences,
        key=lambda sentence: 5 * sum(1 for term in terms if term in sentence) + 2 * sum(1 for marker in intent_markers if marker in sentence),
        reverse=True,
    )
    return ranked[0][:limit]


def _intent_markers(question: str) -> tuple[str, ...]:
    if any(marker in question for marker in ("前", "先", "预备", "基础")):
        return ("基础", "前提", "依赖", "需要先")
    if any(marker in question for marker in ("为什么", "导致", "引起", "造成")):
        return ("导致", "引起", "因为", "由于", "影响")
    if any(marker in question for marker in ("关系", "区别", "对比", "不同")):
        return ("关系", "不同", "区别", "引起", "导致", "构成", "基础", "属于")
    return ()
