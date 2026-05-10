from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import TeacherEditApplyResponse, TeacherEditCreateRequest, TeacherEditListResponse
from app.services.teacher_edit_service import record_teacher_edit
from app.services.teacher_edit_storage import load_teacher_edits


router = APIRouter(prefix="/teacher-edits", tags=["teacher-edits"])


@router.get("", response_model=TeacherEditListResponse)
def list_teacher_edits(raw_file_ids: str | None = None) -> TeacherEditListResponse:
    ids = [item.strip() for item in raw_file_ids.split(",") if item.strip()] if raw_file_ids else []
    edits = load_teacher_edits(sorted(ids))
    return TeacherEditListResponse(raw_file_ids=sorted(ids), edits=edits, count=len(edits))


@router.post("", response_model=TeacherEditApplyResponse)
def create_teacher_edit(payload: TeacherEditCreateRequest) -> TeacherEditApplyResponse:
    try:
        return record_teacher_edit(payload)
    except Exception as exc:  # noqa: BLE001 - normalize stage 10 edit errors.
        raise HTTPException(
            status_code=400,
            detail={"message": "教师修改事件记录失败", "code": "TEACHER_EDIT_FAILED", "detail": str(exc)},
        ) from exc
