from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.models.schemas import (
    AlignmentBuildRequest,
    GraphBuildRequest,
    IntegrationBuildRequest,
    JobStatus,
    JobType,
    LayeredGraphBuildRequest,
    RagIndexRequest,
    SampleBookSummary,
    SampleDatasetPrepareRequest,
    SampleDatasetResponse,
)
from app.services.alignment_builder import build_alignment
from app.services.alignment_storage import load_alignment
from app.services.converted_textbook_importer import import_converted_textbook
from app.services.graph_storage import load_graph
from app.services.integration_builder import build_integration
from app.services.integration_storage import load_integration
from app.services.job_store import job_store
from app.services.knowledge_graph_builder import build_knowledge_graph
from app.services.layered_graph_builder import build_layered_graph
from app.services.layered_graph_storage import load_layered_graph
from app.services.parsed_storage import load_parsed_textbook
from app.services.rag_index import build_rag_index, get_rag_index_status


SEVEN_BOOKS_DATASET_ID = "seven_medical_textbooks"
SEVEN_BOOKS_TITLE = "7 本医学教材示例数据"


def get_seven_books_dataset() -> SampleDatasetResponse:
    manifest = _load_manifest()
    if manifest is None:
        return SampleDatasetResponse(
            id=SEVEN_BOOKS_DATASET_ID,
            title=SEVEN_BOOKS_TITLE,
            status="missing_materials",
            message=f"找不到 converted_textbooks manifest: {settings.converted_textbooks_dir / 'manifest.json'}",
            endpoints=_dataset_endpoints([]),
        )

    books = [_sample_book(record) for record in manifest.get("books", [])]
    raw_file_ids = [book.raw_file_id for book in books]
    rag_status = get_rag_index_status()
    rag_ids = set(rag_status.raw_file_ids)
    rag_ready = rag_status.status == "ready" and set(raw_file_ids).issubset(rag_ids)
    alignment_ready = load_alignment(raw_file_ids) is not None if raw_file_ids else False
    integration_ready = load_integration(raw_file_ids) is not None if raw_file_ids else False

    prepared_count = sum(1 for book in books if book.parsed_ready)
    graph_ready = bool(books) and all(book.graph_ready for book in books)
    status = "not_prepared"
    if prepared_count == len(books) and graph_ready and rag_ready and alignment_ready and integration_ready:
        status = "ready"
    elif prepared_count > 0 or graph_ready or rag_ready or alignment_ready or integration_ready:
        status = "partial"
    metrics = _metrics_from_books(books)
    metrics.update(
        {
            "rag_chunk_count": rag_status.chunk_count if rag_ready else 0,
            "alignment_ready": alignment_ready,
            "integration_ready": integration_ready,
        }
    )
    return SampleDatasetResponse(
        id=SEVEN_BOOKS_DATASET_ID,
        title=SEVEN_BOOKS_TITLE,
        status=status,  # type: ignore[arg-type]
        book_count=len(books),
        books=books,
        raw_file_ids=raw_file_ids,
        rag_ready=rag_ready,
        alignment_ready=alignment_ready,
        integration_ready=integration_ready,
        graphrag_ready=rag_ready and all(book.graph_ready for book in books),
        metrics=metrics,
        endpoints=_dataset_endpoints(raw_file_ids),
    )


def create_prepare_seven_books_job(request: SampleDatasetPrepareRequest) -> str:
    job_id = f"job_dataset_prepare_{SEVEN_BOOKS_DATASET_ID}"
    job_store.create(job_id, JobType.dataset_prepare, "七本书数据集准备任务已创建")
    job_store.update(job_id, result={"dataset_id": SEVEN_BOOKS_DATASET_ID, "request": request.model_dump(mode="json")})
    return job_id


def run_prepare_seven_books(job_id: str, request: SampleDatasetPrepareRequest) -> None:
    try:
        manifest = _load_manifest()
        if manifest is None:
            raise FileNotFoundError(f"Converted textbook manifest not found: {settings.converted_textbooks_dir / 'manifest.json'}")

        records = manifest.get("books", [])
        raw_file_ids: list[str] = []
        job_store.update(job_id, status=JobStatus.running, progress=5, message="正在导入七本书统一 JSON")
        for index, record in enumerate(records, start=1):
            parsed, _path = import_converted_textbook(textbook_title=record["title"])
            raw_file_ids.append(parsed.raw_file.id)
            progress = 5 + int(index / max(len(records), 1) * 25)
            job_store.update(job_id, status=JobStatus.running, progress=progress, message=f"已导入 {index}/{len(records)}：{parsed.raw_file.title}")

        _build_assets_for_raw_files(job_id, raw_file_ids, request)
        dataset = get_seven_books_dataset()
        job_store.update(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="七本书示例数据已准备完成",
            result={
                "dataset": dataset.model_dump(mode="json"),
                "raw_file_ids": raw_file_ids,
                "endpoints": dataset.endpoints,
            },
        )
    except Exception as exc:  # noqa: BLE001 - dataset preparation should surface failures through the job.
        job_store.update(job_id, status=JobStatus.failed, progress=100, message="七本书示例数据准备失败", error=str(exc), retryable=True)


def build_assets_for_uploaded_raw_files(
    job_id: str,
    raw_file_ids: list[str],
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
) -> dict[str, Any]:
    request = SampleDatasetPrepareRequest(
        force_rebuild=True,
        build_graph=build_graph,
        build_layered_graph=build_layered_graphs,
        build_rag=build_rag,
        build_alignment=build_alignment_graph,
        build_integration=build_integration_result,
        use_llm=use_llm,
        max_sections=max_sections,
        max_nodes_per_section=max_nodes_per_section,
        alignment_min_confidence=alignment_min_confidence,
        alignment_max_nodes=alignment_max_nodes,
        integration_target_compression_ratio=integration_target_compression_ratio,
        integration_max_nodes=integration_max_nodes,
    )
    return _build_assets_for_raw_files(job_id, raw_file_ids, request)


def _build_assets_for_raw_files(job_id: str, raw_file_ids: list[str], request: SampleDatasetPrepareRequest) -> dict[str, Any]:
    result: dict[str, Any] = {"raw_file_ids": raw_file_ids}
    if request.build_graph:
        job_store.update(job_id, status=JobStatus.running, progress=35, message="正在构建知识图谱")
        graph_counts: dict[str, dict[str, int]] = {}
        for index, raw_file_id in enumerate(raw_file_ids, start=1):
            graph, _path, _cache_hit = build_knowledge_graph(
                GraphBuildRequest(
                    raw_file_id=raw_file_id,
                    force_rebuild=request.force_rebuild,
                    max_sections=request.max_sections,
                    max_nodes_per_section=request.max_nodes_per_section,
                    use_llm=request.use_llm,
                )
            )
            graph_counts[raw_file_id] = {"nodes": len(graph.nodes), "edges": len(graph.edges)}
            progress = 35 + int(index / max(len(raw_file_ids), 1) * 25)
            job_store.update(job_id, status=JobStatus.running, progress=progress, message=f"已构建 KG {index}/{len(raw_file_ids)}")
        result["graphs"] = graph_counts

    if request.build_layered_graph:
        job_store.update(job_id, status=JobStatus.running, progress=62, message="正在构建多层 KG")
        for raw_file_id in raw_file_ids:
            build_layered_graph(
                LayeredGraphBuildRequest(
                    raw_file_id=raw_file_id,
                    force_rebuild=request.force_rebuild,
                    build_missing_concept_graph=True,
                    max_sections=request.max_sections,
                    max_nodes_per_section=request.max_nodes_per_section,
                    use_llm=request.use_llm,
                )
            )

    if request.build_rag:
        job_store.update(job_id, status=JobStatus.running, progress=68, message="正在建立 RAG 证据索引")
        job = job_store.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        status = build_rag_index(RagIndexRequest(raw_file_ids=raw_file_ids, force_rebuild=True), job)
        result["rag"] = status.model_dump(mode="json")

    if request.build_alignment and len(raw_file_ids) >= 2:
        job_store.update(job_id, status=JobStatus.running, progress=78, message="正在构建术语对齐")
        alignment, _path, _cache_hit = build_alignment(
            AlignmentBuildRequest(
                raw_file_ids=raw_file_ids,
                force_rebuild=request.force_rebuild,
                min_confidence=request.alignment_min_confidence,
                max_nodes=request.alignment_max_nodes,
            )
        )
        result["alignment"] = {
            "id": alignment.id,
            "cluster_count": len(alignment.clusters),
            "candidate_count": len(alignment.candidates),
        }

    if request.build_integration and len(raw_file_ids) >= 2:
        job_store.update(job_id, status=JobStatus.running, progress=88, message="正在生成整合压缩决策")
        integration, _path, _cache_hit = build_integration(
            IntegrationBuildRequest(
                raw_file_ids=raw_file_ids,
                force_rebuild=request.force_rebuild,
                target_compression_ratio=request.integration_target_compression_ratio,
                alignment_min_confidence=request.alignment_min_confidence,
                max_nodes=request.integration_max_nodes,
            )
        )
        result["integration"] = {
            "id": integration.id,
            "decision_count": len(integration.decisions),
            "compression_ratio": integration.compression_stats.compression_ratio,
        }
    return result


def _load_manifest() -> dict[str, Any] | None:
    path = settings.converted_textbooks_dir / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sample_book(record: dict[str, Any]) -> SampleBookSummary:
    sha = record.get("source_sha256_16")
    raw_file_id = f"raw_{sha}"
    parsed = load_parsed_textbook(raw_file_id)
    graph = load_graph(raw_file_id)
    layered = load_layered_graph(raw_file_id)
    endpoints = {
        "textbook": f"/api/textbooks/{raw_file_id}",
        "graph": f"/api/graph?raw_file_id={raw_file_id}&top_n=200",
        "layered_graph": f"/api/kg/layers?raw_file_id={raw_file_id}",
    }
    return SampleBookSummary(
        title=record.get("title") or raw_file_id,
        raw_file_id=raw_file_id,
        source_sha256_16=sha,
        page_count=record.get("pages"),
        text_char_count=record.get("text_chars"),
        parsed_ready=parsed is not None,
        graph_ready=graph is not None,
        layered_graph_ready=layered is not None,
        chunk_count=len(parsed.chunks) if parsed else 0,
        section_count=len(parsed.sections) if parsed else 0,
        node_count=len(graph.nodes) if graph else 0,
        edge_count=len(graph.edges) if graph else 0,
        endpoints=endpoints,
    )


def _metrics_from_books(books: list[SampleBookSummary]) -> dict[str, Any]:
    return {
        "page_count": sum(book.page_count or 0 for book in books),
        "text_char_count": sum(book.text_char_count or 0 for book in books),
        "section_count": sum(book.section_count for book in books),
        "chunk_count": sum(book.chunk_count for book in books),
        "node_count": sum(book.node_count for book in books),
        "edge_count": sum(book.edge_count for book in books),
        "parsed_ready_count": sum(1 for book in books if book.parsed_ready),
        "graph_ready_count": sum(1 for book in books if book.graph_ready),
    }


def _dataset_endpoints(raw_file_ids: list[str]) -> dict[str, str]:
    joined = ",".join(raw_file_ids)
    endpoints = {
        "self": "/api/datasets/seven-books",
        "prepare": "/api/datasets/seven-books/prepare",
        "textbooks": "/api/textbooks",
        "rag_status": "/api/rag/status",
    }
    if raw_file_ids:
        endpoints.update(
            {
                "alignment": f"/api/alignment?raw_file_ids={joined}",
                "integration": f"/api/integration?raw_file_ids={joined}",
                "graphrag_status": f"/api/graphrag/status?raw_file_ids={joined}",
            }
        )
    return endpoints
