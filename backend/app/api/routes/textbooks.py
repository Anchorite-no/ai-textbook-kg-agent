from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.models.schemas import (
    JobStatus,
    JobType,
    ParsedTextbook,
    TextbookBatchUploadResponse,
    TextbookListResponse,
    TextbookUploadError,
    TextbookUploadResponse,
)
from app.services.converted_textbook_importer import import_converted_textbook, stable_id
from app.services.job_store import job_store
from app.services.parsed_storage import list_parsed_textbooks, load_parsed_textbook
from app.services.uploaded_file_parser import parse_uploaded_file


router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("", response_model=TextbookListResponse)
def list_textbooks() -> TextbookListResponse:
    return TextbookListResponse(textbooks=list_parsed_textbooks())


@router.post("/upload", response_model=TextbookUploadResponse | TextbookBatchUploadResponse)
async def upload_textbook(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    textbook_title: str | None = Form(default=None),
) -> TextbookUploadResponse | TextbookBatchUploadResponse:
    if files:
        batch_files = [*files]
        if file is not None:
            batch_files.insert(0, file)
        return await _run_batch_upload(batch_files, textbook_title)

    if file is not None:
        return await _run_single_upload(file, textbook_title)

    return _run_converted_textbook_import(textbook_title)


@router.post("/upload-batch", response_model=TextbookBatchUploadResponse)
async def upload_textbooks_batch(
    files: list[UploadFile] = File(...),
    textbook_title: str | None = Form(default=None),
) -> TextbookBatchUploadResponse:
    return await _run_batch_upload(files, textbook_title)


@router.post("/{raw_file_id}/parse", response_model=TextbookUploadResponse)
def parse_textbook(raw_file_id: str) -> TextbookUploadResponse:
    uploaded_path = _find_uploaded_file(raw_file_id)
    if uploaded_path is None:
        existing = load_parsed_textbook(raw_file_id)
        if existing is not None:
            job_id = stable_id("job", "textbook_parse", raw_file_id, "cached")
            job_store.create(job_id, JobType.textbook_parse, "解析结果已存在")
            output_path = settings.parsed_data_dir / f"{raw_file_id}.json"
            return _complete_job(job_id, existing, output_path, message="已返回现有统一 JSON")
        raise HTTPException(status_code=404, detail=f"Uploaded source not found: {raw_file_id}")

    job_id = stable_id("job", "textbook_parse", raw_file_id, uploaded_path.name)
    job_store.create(job_id, JobType.textbook_parse, "解析任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在重新解析上传文件")
    try:
        parsed, output_path = parse_uploaded_file(uploaded_path, original_filename=_existing_original_filename(raw_file_id))
    except Exception as exc:  # noqa: BLE001 - API must surface parser failures cleanly.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="教材导入失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=job.error) from exc

    return _complete_job(job_id, parsed, output_path, message="上传文件已重新解析为统一 JSON")


@router.get("/{raw_file_id}", response_model=ParsedTextbook)
def get_textbook(raw_file_id: str) -> ParsedTextbook:
    parsed = load_parsed_textbook(raw_file_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail=f"Textbook not found: {raw_file_id}")
    return parsed


async def _run_single_upload(file: UploadFile, textbook_title: str | None) -> TextbookUploadResponse:
    job_id = stable_id("job", "textbook_upload", textbook_title or "", file.filename or "")
    job_store.create(job_id, JobType.textbook_upload, "上传解析任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在保存上传文件")
    try:
        uploaded_path = await _save_uploaded_file(file)
        job_store.update(job_id, status=JobStatus.running, progress=50, message="正在解析上传文件")
        parsed, output_path = parse_uploaded_file(uploaded_path, original_filename=file.filename)
    except Exception as exc:  # noqa: BLE001 - parser failures should be reported through the job.
        job = job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="教材解析失败",
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=job.error) from exc
    return _complete_job(job_id, parsed, output_path, message="上传文件已解析为统一 JSON")


def _run_converted_textbook_import(textbook_title: str | None) -> TextbookUploadResponse:
    job_id = stable_id("job", "converted_textbook_import", textbook_title or "demo")
    job_store.create(job_id, JobType.converted_textbook_import, "converted_textbooks 导入任务已创建")
    job_store.update(job_id, status=JobStatus.running, progress=20, message="正在准备教材输入")
    try:
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
    return _complete_job(job_id, parsed, output_path, message="教材已导入并生成统一 JSON")


async def _run_batch_upload(files: list[UploadFile], textbook_title: str | None) -> TextbookBatchUploadResponse:
    upload_files = [item for item in files if item.filename]
    if not upload_files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    names = "|".join(file.filename or "" for file in upload_files)
    batch_job_id = stable_id("job", "textbook_batch_upload", textbook_title or "", len(upload_files), names)
    job_store.create(batch_job_id, JobType.textbook_batch_upload, "批量上传解析任务已创建")
    job_store.update(batch_job_id, status=JobStatus.running, progress=5, message="正在批量解析上传文件")

    items: list[TextbookUploadResponse] = []
    errors: list[TextbookUploadError] = []
    total = len(upload_files)

    for index, upload_file in enumerate(upload_files, start=1):
        item_job_id = stable_id("job", "textbook_upload", batch_job_id, index, upload_file.filename or "")
        job_store.create(item_job_id, JobType.textbook_upload, "批量子任务已创建")
        job_store.update(item_job_id, status=JobStatus.running, progress=20, message="正在保存上传文件")
        try:
            uploaded_path = await _save_uploaded_file(upload_file)
            job_store.update(item_job_id, status=JobStatus.running, progress=50, message="正在解析上传文件")
            parsed, output_path = parse_uploaded_file(uploaded_path, original_filename=upload_file.filename)
            items.append(_complete_job(item_job_id, parsed, output_path, message="上传文件已解析为统一 JSON"))
        except Exception as exc:  # noqa: BLE001 - one failed file must not stop the batch.
            failed_job = job_store.update(
                item_job_id,
                status=JobStatus.failed,
                progress=100,
                message="教材解析失败",
                error=str(exc),
            )
            errors.append(TextbookUploadError(filename=upload_file.filename or "unknown", error=str(exc), job=failed_job))

        progress = min(95, 5 + int(index / total * 90))
        job_store.update(
            batch_job_id,
            status=JobStatus.running,
            progress=progress,
            message=f"批量解析进度 {index}/{total}",
        )

    failed_count = len(errors)
    success_count = len(items)
    status = JobStatus.completed if success_count else JobStatus.failed
    message = f"批量解析完成：成功 {success_count} 个，失败 {failed_count} 个"
    result: dict[str, Any] = {
        "total_count": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "raw_file_ids": [item.raw_file_id for item in items],
        "errors": [error.model_dump(mode="json") for error in errors],
    }
    batch_job = job_store.update(
        batch_job_id,
        status=status,
        progress=100,
        message=message,
        result=result,
        error=None if success_count else "批量上传全部解析失败",
    )
    return TextbookBatchUploadResponse(
        job=batch_job,
        items=items,
        errors=errors,
        total_count=total,
        success_count=success_count,
        failed_count=failed_count,
    )


def _complete_job(job_id: str, parsed: ParsedTextbook, output_path: Path, message: str) -> TextbookUploadResponse:
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
        message=message,
        result=result,
    )
    return TextbookUploadResponse(
        job=job,
        raw_file_id=parsed.raw_file.id,
        parsed_output_path=str(output_path),
        parsed_textbook=parsed,
    )


async def _save_uploaded_file(file: UploadFile) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    digest = hashlib.sha256(content).hexdigest()[:16]
    suffix = Path(file.filename or "upload.bin").suffix
    output_path = settings.upload_dir / f"upload_{digest}{suffix}"
    output_path.write_bytes(content)
    return output_path


def _find_uploaded_file(raw_file_id: str) -> Path | None:
    if not raw_file_id.startswith("raw_"):
        return None
    digest = raw_file_id.removeprefix("raw_")
    if not digest:
        return None
    matches = sorted(settings.upload_dir.glob(f"upload_{digest}.*"))
    return matches[0] if matches else None


def _existing_original_filename(raw_file_id: str) -> str | None:
    existing = load_parsed_textbook(raw_file_id)
    if existing is not None:
        return existing.raw_file.original_filename
    uploaded_path = _find_uploaded_file(raw_file_id)
    return uploaded_path.name if uploaded_path is not None else None
