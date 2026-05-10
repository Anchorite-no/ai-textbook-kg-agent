from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.models.schemas import LayeredGraphResponse


def layered_graph_path(raw_file_id: str) -> Path:
    return settings.layered_graph_data_dir / f"{raw_file_id}.json"


def save_layered_graph(graph: LayeredGraphResponse) -> Path:
    path = layered_graph_path(graph.raw_file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_layered_graph(raw_file_id: str) -> LayeredGraphResponse | None:
    path = layered_graph_path(raw_file_id)
    if not path.exists():
        return None
    return LayeredGraphResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_latest_layered_graph() -> LayeredGraphResponse | None:
    if not settings.layered_graph_data_dir.exists():
        return None
    paths = sorted(settings.layered_graph_data_dir.glob("raw_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return None
    return LayeredGraphResponse.model_validate_json(paths[0].read_text(encoding="utf-8"))
