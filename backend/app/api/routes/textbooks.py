from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.models.schemas import (
    JobStatus,
    JobType,
    ParsedTextbook,
    TextbookListResponse,
    TextbookUploadResponse,
)
from app.services.converted_textbook_importer import import_converted_textbook, stable_id
from app.services.job_store import job_store
from app.services.parsed_storage import list_parsed_textbooks, load_parsed_textbook
from app.services.text_file_parser import SUPPORTED_TEXT_EXTENSIONS, parse_uploaded_text_file


router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("", response_model=TextbookListResponse)
def list_textbooks() -> TextbookListResponse:
    return TextbookListResponse(textbooks=list_parsed_textbooks())


@router.post("/upload", response_model=TextbookUploadResponse)
async def upload_textbook(
    file: UploadFile | None = File(default=None),
    textbook_title: str | None = Form(default=None),
) -> TextbookUploadResponse:
    job_id = stable_id("job", "textbook_upload", textbook_title or "demo", file.filename if file else "")
    job_store.create(job_id, JobType.converted_textbook_import, "任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在准备教材输入")

    uploaded_path: Path | None = None
    if file is not None:
        uploaded_path = await _save_uploaded_file(file)

    try:
        if uploaded_path is not None:
            suffix = uploaded_path.suffix.lower()
            if suffix not in SUPPORTED_TEXT_EXTENSIONS:
                raise ValueError(f"当前计划 02 首批只支持 txt/md 上传，暂不支持 {suffix or 'unknown'}")
            parsed, output_path = parse_uploaded_text_file(uploaded_path, original_filename=file.filename)
        else:
            parsed, output_path = import_converted_textbook(textbook_title=textbook_title)
    except Exception as exc:  # noqa: BLE001 - API must surface parser failures cleanly.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="教材导入失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=job.error) from exc

    result = {
        "raw_file_id": parsed.raw_file.id,
        "title": parsed.raw_file.title,
        "parsed_output_path": str(output_path),
        "element_count": len(parsed.elements),
        "section_count": len(parsed.sections),
        "chunk_count": len(parsed.chunks),
    }
    job = job_store.update(
        job_id,
        status=JobStatus.completed,
        progress=100,
        message="教材已导入并生成统一 JSON",
        result=result,
    )
    return TextbookUploadResponse(
        job=job,
        raw_file_id=parsed.raw_file.id,
        parsed_output_path=str(output_path),
        parsed_textbook=parsed,
    )


@router.get("/{raw_file_id}", response_model=ParsedTextbook)
def get_textbook(raw_file_id: str) -> ParsedTextbook:
    parsed = load_parsed_textbook(raw_file_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail=f"Textbook not found: {raw_file_id}")
    return parsed


async def _save_uploaded_file(file: UploadFile) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    digest = hashlib.sha256(content).hexdigest()[:16]
    suffix = Path(file.filename or "upload.bin").suffix
    output_path = settings.upload_dir / f"upload_{digest}{suffix}"
    output_path.write_bytes(content)
    return output_path
