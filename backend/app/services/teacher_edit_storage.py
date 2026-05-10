from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.models.schemas import DialogueMessage, TeacherEdit


def teacher_edit_key(raw_file_ids: list[str]) -> str:
    key = "latest" if not raw_file_ids else "_".join(sorted(raw_file_ids))
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in key)


def teacher_edits_path(raw_file_ids: list[str]) -> Path:
    return settings.teacher_edit_data_dir / f"teacher_edits_{teacher_edit_key(raw_file_ids)}.json"


def dialogue_path(raw_file_ids: list[str]) -> Path:
    return settings.teacher_edit_data_dir / f"dialogue_{teacher_edit_key(raw_file_ids)}.json"


def load_teacher_edits(raw_file_ids: list[str]) -> list[TeacherEdit]:
    path = teacher_edits_path(raw_file_ids)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [TeacherEdit.model_validate(item) for item in payload]


def append_teacher_edit(raw_file_ids: list[str], edit: TeacherEdit) -> Path:
    edits = load_teacher_edits(raw_file_ids)
    edits.append(edit)
    path = teacher_edits_path(raw_file_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.model_dump(mode="json") for item in edits], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_dialogue_messages(raw_file_ids: list[str]) -> list[DialogueMessage]:
    path = dialogue_path(raw_file_ids)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [DialogueMessage.model_validate(item) for item in payload]


def append_dialogue_messages(raw_file_ids: list[str], messages: list[DialogueMessage]) -> Path:
    existing = load_dialogue_messages(raw_file_ids)
    existing.extend(messages)
    path = dialogue_path(raw_file_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.model_dump(mode="json") for item in existing], ensure_ascii=False, indent=2), encoding="utf-8")
    return path
