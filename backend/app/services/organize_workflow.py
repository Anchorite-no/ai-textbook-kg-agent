from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models.schemas import JobStatus, JobType
from app.services.job_store import job_store
from app.services.sample_dataset import build_assets_for_uploaded_raw_files
from app.services.uploaded_file_parser import parse_uploaded_file


def create_organize_workflow_job() -> str:
    job_id = f"job_organize_{uuid4().hex[:16]}"
    job_store.create(job_id, JobType.organize_workflow, "文件整理生成任务已创建")
    return job_id


def run_uploaded_organize_workflow(
    job_id: str,
    uploaded_files: list[tuple[Path, str]],
    *,
    build_graph: bool,
    build_layered_graphs: bool,
    build_rag: bool,
    build_alignment_graph: bool,
    build_integration_result: bool,
    use_llm: bool,
    max_sections: int,
    max_nodes_per_section: int,
    alignment_min_confidence: float,
    alignment_max_nodes: int,
    integration_target_compression_ratio: float,
    integration_max_nodes: int,
) -> None:
    try:
        if not uploaded_files:
            raise ValueError("No uploaded files to organize.")

        raw_file_ids: list[str] = []
        parsed_items: list[dict[str, object]] = []
        job_store.update(job_id, status=JobStatus.running, progress=5, message="正在解析上传文件")
        for index, (path, original_filename) in enumerate(uploaded_files, start=1):
            parsed, output_path = parse_uploaded_file(path, original_filename=original_filename)
            raw_file_ids.append(parsed.raw_file.id)
            parsed_items.append(
                {
                    "raw_file_id": parsed.raw_file.id,
                    "title": parsed.raw_file.title,
                    "parsed_output_path": str(output_path),
                    "section_count": len(parsed.sections),
                    "chunk_count": len(parsed.chunks),
                }
            )
            progress = 5 + int(index / len(uploaded_files) * 25)
            job_store.update(job_id, status=JobStatus.running, progress=progress, message=f"已解析 {index}/{len(uploaded_files)}")

        asset_result = build_assets_for_uploaded_raw_files(
            job_id,
            raw_file_ids,
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
        endpoints = _workflow_endpoints(raw_file_ids)
        job_store.update(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="文件已整理生成，可由前端读取",
            result={
                "raw_file_ids": raw_file_ids,
                "parsed_items": parsed_items,
                "assets": asset_result,
                "endpoints": endpoints,
            },
        )
    except Exception as exc:  # noqa: BLE001 - workflow failures should stay visible to the frontend.
        job_store.update(job_id, status=JobStatus.failed, progress=100, message="文件整理生成失败", error=str(exc), retryable=False)


def _workflow_endpoints(raw_file_ids: list[str]) -> dict[str, str]:
    joined = ",".join(raw_file_ids)
    endpoints = {
        "textbooks": "/api/textbooks",
    }
    if raw_file_ids:
        endpoints["first_textbook"] = f"/api/textbooks/{raw_file_ids[0]}"
        endpoints["first_graph"] = f"/api/graph?raw_file_id={raw_file_ids[0]}&top_n=1000"
        endpoints["rag_status"] = "/api/rag/status"
        endpoints["graphrag_status"] = f"/api/graphrag/status?raw_file_ids={joined}"
    if len(raw_file_ids) >= 2:
        endpoints["alignment"] = f"/api/alignment?raw_file_ids={joined}"
        endpoints["integration"] = f"/api/integration?raw_file_ids={joined}"
    return endpoints
