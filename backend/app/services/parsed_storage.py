from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.models.schemas import ParsedTextbook, TextbookSummary


def list_parsed_textbooks(parsed_dir: Path | None = None) -> list[TextbookSummary]:
    parsed_dir = parsed_dir or settings.parsed_data_dir
    if not parsed_dir.exists():
        return []

    summaries: list[TextbookSummary] = []
    for path in sorted(parsed_dir.glob("raw_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_file = payload["raw_file"]
        summaries.append(
            TextbookSummary(
                raw_file_id=raw_file["id"],
                title=raw_file["title"],
                format=raw_file["format"],
                page_count=raw_file.get("page_count"),
                element_count=len(payload.get("elements") or []),
                section_count=len(payload.get("sections") or []),
                chunk_count=len(payload.get("chunks") or []),
                parsed_output_path=str(path),
                updated_at=datetime.fromtimestamp(path.stat().st_mtime),
            )
        )
    return summaries


def load_parsed_textbook(raw_file_id: str, parsed_dir: Path | None = None) -> ParsedTextbook | None:
    parsed_dir = parsed_dir or settings.parsed_data_dir
    path = parsed_dir / f"{raw_file_id}.json"
    if not path.exists():
        return None
    return ParsedTextbook.model_validate_json(path.read_text(encoding="utf-8"))
