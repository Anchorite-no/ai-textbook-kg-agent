from __future__ import annotations

import json
import math
import re
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


INDEX_VERSION = "local_lexical_v1"
INDEX_FILENAME = "rag_index.json"


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
                    "char_count": chunk.char_count,
                }
            )
    payload = {
        "version": INDEX_VERSION,
        "built_by_job_id": job.id,
        "updated_at": datetime.utcnow().isoformat(),
        "raw_file_ids": seen_books,
        "textbook_count": len(seen_books),
        "chunk_count": len(records),
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

    query_terms = _token_counts(request.question)
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

    scored = [
        (score, record)
        for record in records
        if (score := _score_record(query_terms, record)) > 0
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[: request.top_k]

    if not top:
        return RagQueryResponse(
            question=request.question,
            answer="当前知识库中未找到相关信息。",
            metadata={"reason": "no_positive_match", "index_version": payload.get("version")},
        )

    max_score = top[0][0] or 1.0
    citations: list[RagCitation] = []
    source_chunks: list[Chunk] = []
    answer_parts: list[str] = []
    for score, record in top:
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
            "retrieval": "local_lexical",
            "top_k": request.top_k,
            "matched_count": len(top),
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
        metadata={"version": payload.get("version"), "built_by_job_id": payload.get("built_by_job_id")},
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


def _score_record(query_terms: dict[str, int], record: dict[str, Any]) -> float:
    token_counts = record["tokens"]
    score = 0.0
    for term, query_count in query_terms.items():
        count = token_counts.get(term, 0)
        if count:
            score += (1 + math.log(count)) * query_count
    text = record["chunk"]["text"]
    for term in query_terms:
        if len(term) >= 3 and term in text:
            score += 2.0
    return score


def _best_quote(question: str, text: str, limit: int = 180) -> str:
    terms = _token_counts(question)
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？!?；;])", text) if sentence.strip()]
    if not sentences:
        return text[:limit]
    ranked = sorted(
        sentences,
        key=lambda sentence: sum(1 for term in terms if term in sentence),
        reverse=True,
    )
    return ranked[0][:limit]
