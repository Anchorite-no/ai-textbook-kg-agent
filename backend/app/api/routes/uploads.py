from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import (
    JobStatus,
    JobType,
    TextbookUploadResponse,
    UploadChunkResponse,
    UploadSessionCompleteResponse,
    UploadSessionCreateRequest,
    UploadSessionRecord,
)
from app.services.converted_textbook_importer import stable_id
from app.services.job_store import job_store
from app.services.upload_session_store import upload_session_store
from app.services.uploaded_file_parser import parse_uploaded_file


router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/sessions", response_model=UploadSessionRecord)
def create_upload_session(payload: UploadSessionCreateRequest) -> UploadSessionRecord:
    return upload_session_store.create(payload)


@router.get("/sessions/{session_id}", response_model=UploadSessionRecord)
def get_upload_session(session_id: str) -> UploadSessionRecord:
    return _load_session(session_id)


@router.put("/sessions/{session_id}/chunks/{chunk_index}", response_model=UploadChunkResponse)
async def upload_chunk(session_id: str, chunk_index: int, file: UploadFile = File(...)) -> UploadChunkResponse:
    session = _load_session(session_id)
    try:
        content = await file.read()
        updated = upload_session_store.write_chunk(session, chunk_index, content)
    except Exception as exc:  # noqa: BLE001 - chunk upload errors must use normalized API shape.
        failed = upload_session_store.fail(session, str(exc))
        raise HTTPException(status_code=400, detail=_upload_error("分片上传失败", failed.error)) from exc
    return UploadChunkResponse(session=updated, chunk_index=chunk_index, received_bytes=len(content))


@router.post("/sessions/{session_id}/complete", response_model=UploadSessionCompleteResponse)
def complete_upload_session(session_id: str) -> UploadSessionCompleteResponse:
    session = _load_session(session_id)
    job_id = stable_id("job", "large_file_upload", session.id, session.filename)
    job_store.create(job_id, JobType.large_file_upload, "大文件上传完成任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=70, message="正在合并上传分片")

    try:
        assembled_session, assembled_path = upload_session_store.assemble(session)
    except Exception as exc:  # noqa: BLE001 - surface merge/checksum errors to caller.
        failed_session = upload_session_store.fail(session, str(exc))
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="大文件合并失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=_upload_error(job.message, failed_session.error)) from exc

    if not assembled_session.parse_on_complete:
        completed_session = upload_session_store.mark_completed(assembled_session, raw_file_id=None, parsed_output_path=None)
        job = job_store.update(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="大文件已合并，未触发解析",
            result={"assembled_path": completed_session.assembled_path},
        )
        return UploadSessionCompleteResponse(session=completed_session, job=job, parsed_upload=None)

    parsing_session = upload_session_store.mark_parsing(assembled_session, job_id)
    job_store.update(job_id, status=JobStatus.running, progress=85, message="正在解析合并后的文件")

    try:
        parsed, output_path = parse_uploaded_file(assembled_path, original_filename=parsing_session.filename)
    except Exception as exc:  # noqa: BLE001 - parser errors stay attached to session and job.
        failed_session = upload_session_store.fail(parsing_session, str(exc))
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="大文件解析失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=_upload_error(job.message, failed_session.error)) from exc

    completed_session = upload_session_store.mark_completed(
        parsing_session,
        raw_file_id=parsed.raw_file.id,
        parsed_output_path=str(output_path),
    )
    result = {
        "raw_file_id": parsed.raw_file.id,
        "title": parsed.raw_file.title,
        "parsed_output_path": str(output_path),
        "element_count": len(parsed.elements),
        "section_count": len(parsed.sections),
        "chunk_count": len(parsed.chunks),
        "assembled_path": str(assembled_path),
    }
    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="大文件已合并并解析为统一 JSON",
        result=result,
    )
    parsed_upload = TextbookUploadResponse(
        job=job,
        raw_file_id=parsed.raw_file.id,
        parsed_output_path=str(output_path),
        parsed_textbook=parsed,
    )
    return UploadSessionCompleteResponse(session=completed_session, job=job, parsed_upload=parsed_upload)


def _load_session(session_id: str) -> UploadSessionRecord:
    session = upload_session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"message": "上传会话不存在", "code": "UPLOAD_SESSION_NOT_FOUND", "detail": session_id})
    return upload_session_store.refresh_progress(session)


def _upload_error(message: str, detail: str | None) -> dict[str, str]:
    return {
        "message": message,
        "code": "UPLOAD_FAILED",
        "detail": detail or message,
    }
