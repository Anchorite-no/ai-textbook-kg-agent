from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.models.schemas import OrganizeWorkflowAcceptedResponse
from app.services.job_store import job_store
from app.services.organize_workflow import create_organize_workflow_job, run_uploaded_organize_workflow


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/organize", response_model=OrganizeWorkflowAcceptedResponse)
async def organize_uploaded_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    build_graph: bool = Form(default=True),
    build_layered_graphs: bool = Form(default=True),
    build_rag: bool = Form(default=True),
    build_alignment_graph: bool = Form(default=True),
    build_integration_result: bool = Form(default=True),
    use_llm: bool = Form(default=False),
    max_sections: int = Form(default=300, ge=1, le=3000),
    max_nodes_per_section: int = Form(default=12, ge=1, le=80),
    alignment_min_confidence: float = Form(default=0.62, ge=0, le=1),
    alignment_max_nodes: int = Form(default=2000, ge=2, le=10000),
    integration_target_compression_ratio: float = Form(default=0.30, gt=0, le=0.80),
    integration_max_nodes: int = Form(default=2000, ge=2, le=10000),
) -> OrganizeWorkflowAcceptedResponse:
    uploaded_files = [file for file in files if file.filename]
    if not uploaded_files:
        raise HTTPException(status_code=400, detail={"message": "请至少上传一个文件", "code": "NO_UPLOAD_FILES", "detail": None})

    saved_files: list[tuple[Path, str]] = []
    for file in uploaded_files:
        saved_files.append((await _save_workflow_upload(file), file.filename or "upload.bin"))

    job_id = create_organize_workflow_job()
    background_tasks.add_task(
        run_uploaded_organize_workflow,
        job_id,
        saved_files,
        build_graph=build_graph,
        build_layered_graphs=build_layered_graphs,
        build_rag=build_rag,
        build_alignment_graph=build_alignment_graph,
        build_integration_result=build_integration_result,
        use_llm=use_llm,
        max_sections=max_sections,
        max_nodes_per_section=max_nodes_per_section,
        alignment_min_confidence=alignment_min_confidence,
        alignment_max_nodes=alignment_max_nodes,
        integration_target_compression_ratio=integration_target_compression_ratio,
        integration_max_nodes=integration_max_nodes,
    )
    job = job_store.get(job_id)
    if job is None:
        raise RuntimeError(f"Job not found after create: {job_id}")
    return OrganizeWorkflowAcceptedResponse(
        job=job,
        message=f"文件已接收，正在解析并生成统一 JSON、KG、RAG、对齐与整合结果；请轮询 /api/jobs/{job_id}",
    )


async def _save_workflow_upload(file: UploadFile) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail={"message": "上传文件为空", "code": "EMPTY_UPLOAD_FILE", "detail": file.filename},
        )
    digest = hashlib.sha256(content).hexdigest()[:16]
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    output_path = settings.upload_dir / f"workflow_{digest}{suffix}"
    output_path.write_bytes(content)
    return output_path
