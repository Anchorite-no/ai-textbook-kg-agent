from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.core.config import settings
from app.models.schemas import (
    AsyncTextbookParseResponse,
    JobRecord,
    JobStatus,
    JobType,
    PipelineStepName,
    PipelineStepRecord,
    PipelineStepStatus,
)
from app.services.converted_textbook_importer import import_converted_textbook
from app.services.job_store import job_store
from app.services.upload_session_store import upload_session_store
from app.services.uploaded_file_parser import parse_uploaded_file


PipelineSourceKind = Literal["uploaded", "converted_textbook", "upload_session"]


def create_textbook_pipeline_job(
    source_kind: PipelineSourceKind,
    file_path: Path | None = None,
    original_filename: str | None = None,
    textbook_title: str | None = None,
    upload_session_id: str | None = None,
) -> AsyncTextbookParseResponse:
    job_id = f"job_pipeline_{uuid4().hex[:16]}"
    context = {
        "job_id": job_id,
        "source_kind": source_kind,
        "file_path": str(file_path) if file_path is not None else None,
        "original_filename": original_filename,
        "textbook_title": textbook_title,
        "upload_session_id": upload_session_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    context_path = _write_context(job_id, context)
    job_store.create(job_id, JobType.textbook_pipeline, "异步解析任务已创建")
    steps = _initial_steps(include_assemble=source_kind == "upload_session")
    job = job_store.update(
        job_id,
        steps=steps,
        retryable=False,
        context_path=str(context_path),
        result={"source_kind": source_kind, "upload_session_id": upload_session_id},
    )
    if upload_session_id is not None:
        session = upload_session_store.get(upload_session_id)
        if session is not None:
            upload_session_store.save(session.model_copy(update={"job_id": job_id}))
    return AsyncTextbookParseResponse(job=job, accepted=True, upload_session_id=upload_session_id)


def run_textbook_pipeline(job_id: str) -> None:
    context = _read_context(job_id)
    source_kind = context["source_kind"]
    job_store.update(job_id, status=JobStatus.running, progress=5, message="异步解析流水线启动", retryable=False, error=None)
    current_step: PipelineStepName | None = None
    try:
        file_path: Path | None = None
        original_filename: str | None = context.get("original_filename")

        if source_kind == "upload_session":
            current_step = PipelineStepName.assemble_file
            _run_step(job_id, current_step, 10, "正在合并上传分片")
            session = upload_session_store.get(context["upload_session_id"])
            if session is None:
                raise ValueError(f"Upload session not found: {context['upload_session_id']}")
            assembled_session, assembled_path = upload_session_store.assemble(session)
            upload_session_store.mark_parsing(assembled_session, job_id)
            file_path = assembled_path
            original_filename = assembled_session.filename
            _complete_step(job_id, current_step, "上传分片已合并")
        elif source_kind == "uploaded":
            file_path = Path(context["file_path"])

        current_step = PipelineStepName.detect_format
        suffix = Path(original_filename or file_path or "converted_textbook").suffix.lower()
        _run_step(job_id, current_step, 20, f"检测文件格式 {suffix or 'converted_textbook'}")
        _complete_step(job_id, current_step, "文件格式检测完成")

        current_step = PipelineStepName.parse_elements
        _run_step(job_id, current_step, 35, "正在解析文档元素")
        if source_kind == "converted_textbook":
            parsed, output_path = import_converted_textbook(textbook_title=context.get("textbook_title"))
        else:
            if file_path is None:
                raise ValueError("Pipeline file_path is missing")
            parsed, output_path = parse_uploaded_file(file_path, original_filename=original_filename)
        _complete_step(job_id, current_step, f"已解析 {len(parsed.elements)} 个文档元素")

        current_step = PipelineStepName.build_sections
        _run_step(job_id, current_step, 65, "正在生成章节结构")
        _complete_step(job_id, current_step, f"已生成 {len(parsed.sections)} 个 section")

        current_step = PipelineStepName.chunk_sections
        _run_step(job_id, current_step, 80, "正在切分证据 chunk")
        _complete_step(job_id, current_step, f"已生成 {len(parsed.chunks)} 个 chunk")

        current_step = PipelineStepName.persist_parsed
        _run_step(job_id, current_step, 95, "正在保存统一 JSON")
        _complete_step(job_id, current_step, "统一 JSON 已保存")

        result = {
            "raw_file_id": parsed.raw_file.id,
            "title": parsed.raw_file.title,
            "parsed_output_path": str(output_path),
            "element_count": len(parsed.elements),
            "section_count": len(parsed.sections),
            "chunk_count": len(parsed.chunks),
            "source_kind": source_kind,
        }
        job_store.update(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="异步解析流水线已完成",
            result=result,
            retryable=False,
        )
        if source_kind == "upload_session":
            session = upload_session_store.get(context["upload_session_id"])
            if session is not None:
                upload_session_store.mark_completed(session, parsed.raw_file.id, str(output_path))
    except Exception as exc:  # noqa: BLE001 - pipeline errors must be visible and retryable.
        if current_step is not None:
            job_store.update_step(job_id, current_step, PipelineStepStatus.failed, 100, "步骤失败", str(exc))
        job_store.update(
            job_id,
            status=JobStatus.failed,
            progress=100,
            message="异步解析流水线失败",
            error=str(exc),
            retryable=True,
        )
        if source_kind == "upload_session":
            session = upload_session_store.get(context.get("upload_session_id") or "")
            if session is not None:
                upload_session_store.fail(session, str(exc))


def retry_textbook_pipeline(job_id: str) -> JobRecord:
    context = _read_context(job_id)
    steps = _initial_steps(include_assemble=context["source_kind"] == "upload_session")
    return job_store.update(
        job_id,
        status=JobStatus.queued,
        progress=0,
        message="异步解析任务已重新排队",
        error=None,
        retryable=False,
        steps=steps,
    )


def _run_step(job_id: str, step_name: PipelineStepName, progress: int, message: str) -> None:
    job_store.update(job_id, status=JobStatus.running, progress=progress, message=message)
    job_store.update_step(job_id, step_name, PipelineStepStatus.running, 10, message)


def _complete_step(job_id: str, step_name: PipelineStepName, message: str) -> None:
    job_store.update_step(job_id, step_name, PipelineStepStatus.completed, 100, message)


def _initial_steps(include_assemble: bool = False) -> list[PipelineStepRecord]:
    names = [
        PipelineStepName.detect_format,
        PipelineStepName.parse_elements,
        PipelineStepName.build_sections,
        PipelineStepName.chunk_sections,
        PipelineStepName.persist_parsed,
    ]
    if include_assemble:
        names.insert(0, PipelineStepName.assemble_file)
    return [PipelineStepRecord(name=name) for name in names]


def _context_path(job_id: str) -> Path:
    return settings.job_data_dir / f"{job_id}.json"


def _write_context(job_id: str, context: dict[str, object]) -> Path:
    settings.job_data_dir.mkdir(parents=True, exist_ok=True)
    path = _context_path(job_id)
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read_context(job_id: str) -> dict[str, object]:
    path = _context_path(job_id)
    if not path.exists():
        raise ValueError(f"Pipeline context not found: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))
