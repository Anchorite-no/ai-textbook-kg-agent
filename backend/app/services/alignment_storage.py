from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.models.schemas import AlignmentResponse


def alignment_path(raw_file_ids: list[str]) -> Path:
    key = "all" if not raw_file_ids else "_".join(sorted(raw_file_ids))
    safe_key = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in key)
    return settings.alignment_data_dir / f"alignment_{safe_key}.json"


def save_alignment(alignment: AlignmentResponse) -> Path:
    path = alignment_path(alignment.raw_file_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(alignment.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_alignment(raw_file_ids: list[str]) -> AlignmentResponse | None:
    path = alignment_path(raw_file_ids)
    if not path.exists():
        return None
    return AlignmentResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_latest_alignment() -> AlignmentResponse | None:
    if not settings.alignment_data_dir.exists():
        return None
    paths = sorted(settings.alignment_data_dir.glob("alignment_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return None
    return AlignmentResponse.model_validate_json(paths[0].read_text(encoding="utf-8"))
