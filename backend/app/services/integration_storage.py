from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.models.schemas import IntegrationResponse


def integration_path(raw_file_ids: list[str]) -> Path:
    key = "all" if not raw_file_ids else "_".join(sorted(raw_file_ids))
    safe_key = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in key)
    return settings.integration_data_dir / f"integration_{safe_key}.json"


def save_integration(integration: IntegrationResponse) -> Path:
    path = integration_path(integration.raw_file_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(integration.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_integration(raw_file_ids: list[str]) -> IntegrationResponse | None:
    path = integration_path(raw_file_ids)
    if not path.exists():
        return None
    return IntegrationResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_latest_integration() -> IntegrationResponse | None:
    if not settings.integration_data_dir.exists():
        return None
    paths = sorted(settings.integration_data_dir.glob("integration_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return None
    return IntegrationResponse.model_validate_json(paths[0].read_text(encoding="utf-8"))
