from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import DialogueHistoryResponse, DialogueMessageRequest, DialogueMessageResponse
from app.services.teacher_edit_service import handle_dialogue_message
from app.services.teacher_edit_storage import load_dialogue_messages


router = APIRouter(prefix="/dialogue", tags=["dialogue"])


@router.get("/messages", response_model=DialogueHistoryResponse)
def list_dialogue_messages(raw_file_ids: str | None = None) -> DialogueHistoryResponse:
    ids = [item.strip() for item in raw_file_ids.split(",") if item.strip()] if raw_file_ids else []
    messages = load_dialogue_messages(sorted(ids))
    return DialogueHistoryResponse(raw_file_ids=sorted(ids), messages=messages, count=len(messages))


@router.post("/messages", response_model=DialogueMessageResponse)
def post_dialogue_message(payload: DialogueMessageRequest) -> DialogueMessageResponse:
    try:
        return handle_dialogue_message(payload)
    except Exception as exc:  # noqa: BLE001 - normalize stage 10 dialogue errors.
        raise HTTPException(
            status_code=400,
            detail={"message": "教师对话处理失败", "code": "DIALOGUE_MESSAGE_FAILED", "detail": str(exc)},
        ) from exc
