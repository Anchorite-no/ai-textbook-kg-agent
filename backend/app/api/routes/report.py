from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from app.models.schemas import ReportGenerateRequest, ReportGenerateResponse
from app.services.converted_textbook_importer import stable_id
from app.services.graph_storage import load_graph
from app.services.graphrag_query import get_graphrag_status
from app.services.integration_storage import load_integration
from app.services.parsed_storage import list_parsed_textbooks
from app.services.rag_index import get_rag_index_status
from app.services.sample_dataset import get_seven_books_dataset


router = APIRouter(prefix="/report", tags=["report"])


@router.post("/generate", response_model=ReportGenerateResponse)
def generate_report(payload: ReportGenerateRequest) -> ReportGenerateResponse:
    dataset = get_seven_books_dataset()
    raw_file_ids = payload.raw_file_ids or dataset.raw_file_ids
    summaries = [item for item in list_parsed_textbooks() if not raw_file_ids or item.raw_file_id in raw_file_ids]
    raw_file_ids = raw_file_ids or [item.raw_file_id for item in summaries]
    graph_metrics = _graph_metrics(raw_file_ids) if payload.include_graph_metrics else {}
    rag_status = get_rag_index_status()
    graphrag_status = get_graphrag_status(raw_file_ids)
    integration = load_integration(raw_file_ids) if payload.include_integration and len(raw_file_ids) >= 2 else None
    title = payload.title or dataset.title or "教材知识整合报告"
    generated_at = datetime.utcnow()

    markdown = _build_markdown(
        title=title,
        generated_at=generated_at,
        raw_file_ids=raw_file_ids,
        summaries=summaries,
        graph_metrics=graph_metrics,
        rag_status=rag_status.model_dump(mode="json"),
        graphrag_status=graphrag_status.model_dump(mode="json"),
        integration=integration.model_dump(mode="json") if integration else None,
    )
    return ReportGenerateResponse(
        id=stable_id("report", "|".join(raw_file_ids), generated_at.isoformat()),
        raw_file_ids=raw_file_ids,
        title=title,
        markdown=markdown,
        generated_at=generated_at,
        metadata={
            "dataset_id": dataset.id,
            "book_count": len(summaries),
            "graph_metrics": graph_metrics,
            "rag_status": rag_status.status,
            "graphrag_status": graphrag_status.status,
            "integration_ready": integration is not None,
        },
    )


def _graph_metrics(raw_file_ids: list[str]) -> dict[str, int | float]:
    total_nodes = 0
    total_edges = 0
    total_orphans = 0
    ready_count = 0
    for raw_file_id in raw_file_ids:
        graph = load_graph(raw_file_id)
        if graph is None:
            continue
        ready_count += 1
        total_nodes += len(graph.nodes)
        total_edges += len(graph.edges)
        incident = {edge.source_node_id for edge in graph.edges} | {edge.target_node_id for edge in graph.edges}
        total_orphans += sum(1 for node in graph.nodes if node.id not in incident)
    return {
        "graph_ready_count": ready_count,
        "node_count": total_nodes,
        "edge_count": total_edges,
        "orphan_count": total_orphans,
        "orphan_ratio": round(total_orphans / max(total_nodes, 1), 4),
    }


def _build_markdown(
    *,
    title: str,
    generated_at: datetime,
    raw_file_ids: list[str],
    summaries: list[object],
    graph_metrics: dict[str, int | float],
    rag_status: dict[str, object],
    graphrag_status: dict[str, object],
    integration: dict[str, object] | None,
) -> str:
    stats = integration.get("compression_stats") if integration else None
    decisions = integration.get("decisions") if integration else []
    decisions = decisions if isinstance(decisions, list) else []
    lines = [
        f"# {title}",
        "",
        f"生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "## 数据概览",
        "",
        f"- 教材数量：{len(raw_file_ids)} 本",
        f"- 章节数量：{sum(getattr(item, 'section_count', 0) for item in summaries):,}",
        f"- Chunk 数量：{sum(getattr(item, 'chunk_count', 0) for item in summaries):,}",
        f"- KG：{graph_metrics.get('node_count', 0)} 节点 / {graph_metrics.get('edge_count', 0)} 边，孤立节点率 {float(graph_metrics.get('orphan_ratio', 0)) * 100:.1f}%",
        f"- RAG：{rag_status.get('status')}，{rag_status.get('chunk_count', 0)} chunks",
        f"- GraphRAG：{graphrag_status.get('status')}，{graphrag_status.get('node_count', 0)} 节点 / {graphrag_status.get('edge_count', 0)} 边",
        "",
        "## 教材清单",
        "",
    ]
    lines.extend(
        f"{index}. {getattr(item, 'title', '')}（{getattr(item, 'section_count', 0)} 章节，{getattr(item, 'chunk_count', 0)} chunks）"
        for index, item in enumerate(summaries, start=1)
    )
    lines.extend(["", "## 整合压缩", ""])
    if isinstance(stats, dict):
        lines.extend(
            [
                f"- 压缩率：{float(stats.get('compression_ratio', 0)) * 100:.1f}%（目标 {float(stats.get('target_compression_ratio', 0)) * 100:.0f}%）",
                f"- 节点：{stats.get('original_node_count', 0)} -> {stats.get('integrated_node_count', 0)}",
                f"- 字符：{stats.get('original_char_count', 0)} -> {stats.get('retained_char_count', 0)}",
                f"- 证据覆盖率：{float(stats.get('evidence_coverage_ratio', 0)) * 100:.1f}%",
            ]
        )
    else:
        lines.append("- 尚未读取到整合压缩结果。")
    lines.extend(["", "## 代表性整合决策", ""])
    if decisions:
        for index, decision in enumerate(decisions[:12], start=1):
            if not isinstance(decision, dict):
                continue
            lines.append(f"{index}. **{decision.get('action')}**：{decision.get('reason')}")
    else:
        lines.append("暂无可展示决策。")
    lines.extend(
        [
            "",
            "## 证据链说明",
            "",
            "所有教材结构、知识节点、RAG 引用和整合决策均保留 source_locator，可回溯到原始教材页码、章节、chunk 或办公文档位置。",
        ]
    )
    return "\n".join(lines)
