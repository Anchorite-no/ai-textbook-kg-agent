from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from app.models.schemas import ReportGenerateRequest, ReportGenerateResponse
from app.services.converted_textbook_importer import stable_id
from app.services.graph_storage import load_graph
from app.services.graphrag_query import get_graphrag_status
from app.services.integration_storage import load_integration
from app.services.llm_client import llm_client
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
    llm_sections, llm_metadata = _build_llm_sections(
        title=title,
        raw_file_ids=raw_file_ids,
        summaries=summaries,
        graph_metrics=graph_metrics,
        rag_status=rag_status.model_dump(mode="json"),
        graphrag_status=graphrag_status.model_dump(mode="json"),
        integration=integration.model_dump(mode="json") if integration else None,
        enabled=payload.use_llm,
    )

    markdown = _build_markdown(
        title=title,
        generated_at=generated_at,
        raw_file_ids=raw_file_ids,
        summaries=summaries,
        graph_metrics=graph_metrics,
        rag_status=rag_status.model_dump(mode="json"),
        graphrag_status=graphrag_status.model_dump(mode="json"),
        integration=integration.model_dump(mode="json") if integration else None,
        llm_sections=llm_sections,
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
            "llm": llm_metadata,
        },
    )


def _graph_metrics(raw_file_ids: list[str]) -> dict[str, Any]:
    total_nodes = 0
    total_edges = 0
    total_orphans = 0
    total_context_edges = 0
    ready_count = 0
    books: list[dict[str, Any]] = []
    for raw_file_id in raw_file_ids:
        graph = load_graph(raw_file_id)
        if graph is None:
            continue
        ready_count += 1
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        incident = {edge.source_node_id for edge in graph.edges} | {edge.target_node_id for edge in graph.edges}
        orphan_count = sum(1 for node in graph.nodes if node.id not in incident)
        context_edges = int(graph.metadata.get("context_edge_count") or 0)
        total_nodes += node_count
        total_edges += edge_count
        total_orphans += orphan_count
        total_context_edges += context_edges
        books.append(
            {
                "raw_file_id": raw_file_id,
                "title": graph.title,
                "section_count": graph.metadata.get("section_count"),
                "full_section_count": graph.metadata.get("full_section_count"),
                "node_count": node_count,
                "edge_count": edge_count,
                "orphan_count": orphan_count,
                "orphan_ratio": round(orphan_count / max(node_count, 1), 4),
                "context_edge_count": context_edges,
            }
        )
    return {
        "graph_ready_count": ready_count,
        "node_count": total_nodes,
        "edge_count": total_edges,
        "orphan_count": total_orphans,
        "orphan_ratio": round(total_orphans / max(total_nodes, 1), 4),
        "context_edge_count": total_context_edges,
        "books": books,
    }


def _build_markdown(
    *,
    title: str,
    generated_at: datetime,
    raw_file_ids: list[str],
    summaries: list[object],
    graph_metrics: dict[str, Any],
    rag_status: dict[str, object],
    graphrag_status: dict[str, object],
    integration: dict[str, object] | None,
    llm_sections: list[str],
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
        f"- 上下文弱链接：{graph_metrics.get('context_edge_count', 0)} 条",
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
    lines.extend(["", "## 图谱质量", ""])
    lines.extend(
        [
            "| 教材 | Section | 节点 | 边 | 孤立率 | 上下文边 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for book in graph_metrics.get("books", []):
        if not isinstance(book, dict):
            continue
        lines.append(
            f"| {book.get('title', '')} | {book.get('section_count', 0)} / {book.get('full_section_count', 0)} | "
            f"{book.get('node_count', 0)} | {book.get('edge_count', 0)} | "
            f"{float(book.get('orphan_ratio', 0)) * 100:.1f}% | {book.get('context_edge_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "说明：上下文弱链接来自同章节、同 chunk、相邻章节关系，用于降低零散节点并辅助教师浏览；此类边在 metadata 中标记为 contextual_edge。",
        ]
    )
    if llm_sections:
        lines.extend(["", *llm_sections])
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
            "## 推荐演示问答",
            "",
            "- 炎症反应的基本过程是什么？",
            "- 细胞损伤和细胞死亡有什么关系？",
            "- 血液循环相关知识在哪些教材中出现？",
            "- 请比较病理学和病理生理学中对疾病机制的描述差异。",
            "",
            "## 证据链说明",
            "",
            "所有教材结构、知识节点、RAG 引用和整合决策均保留 source_locator，可回溯到原始教材页码、章节、chunk 或办公文档位置。",
        ]
    )
    return "\n".join(lines)


def _build_llm_sections(
    *,
    title: str,
    raw_file_ids: list[str],
    summaries: list[object],
    graph_metrics: dict[str, Any],
    rag_status: dict[str, object],
    graphrag_status: dict[str, object],
    integration: dict[str, object] | None,
    enabled: bool,
) -> tuple[list[str], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "requested": enabled,
        "enabled": llm_client.is_enabled(),
        "used": False,
    }
    if not enabled or not llm_client.is_enabled():
        return [], metadata

    stats = integration.get("compression_stats") if integration else None
    decisions = integration.get("decisions") if integration else []
    decisions = decisions if isinstance(decisions, list) else []
    facts = {
        "title": title,
        "book_count": len(raw_file_ids),
        "books": [
            {
                "title": getattr(item, "title", ""),
                "sections": getattr(item, "section_count", 0),
                "chunks": getattr(item, "chunk_count", 0),
            }
            for item in summaries[:12]
        ],
        "graph": {
            "node_count": graph_metrics.get("node_count", 0),
            "edge_count": graph_metrics.get("edge_count", 0),
            "orphan_ratio": graph_metrics.get("orphan_ratio", 0),
            "context_edge_count": graph_metrics.get("context_edge_count", 0),
            "books": graph_metrics.get("books", [])[:12],
        },
        "rag": rag_status,
        "graphrag": graphrag_status,
        "integration_stats": stats if isinstance(stats, dict) else None,
        "decision_samples": [
            {
                "action": item.get("action"),
                "reason": item.get("reason"),
                "confidence": item.get("confidence"),
            }
            for item in decisions[:10]
            if isinstance(item, dict)
        ],
    }
    prompt = (
        "你是学科教材知识图谱与教学整合评审助手。请只基于给定事实生成 JSON，不要编造不存在的数据。"
        "输出字段必须是：summary(string), single_book_focus(list[string]), graph_cleanup(list[string]), "
        "teaching_integrity(string), risks(list[string]), next_steps(list[string])。"
        "要求：中文，短句，面向黑客松评委；重点说明单本书图谱如何精简但保留合理链接，"
        "以及跨教材整合是否仍能保持教学完整性。每个列表最多 4 条。"
        f"\n事实数据：{json.dumps(facts, ensure_ascii=False)}"
    )
    try:
        payload = llm_client.extract_json(prompt) or {}
    except Exception as exc:  # noqa: BLE001 - report generation must keep deterministic fallback.
        metadata["error"] = str(exc)
        return [], metadata

    metadata["used"] = True
    metadata["model"] = "configured"
    lines = [
        "## LLM 分析摘要",
        "",
        _as_text(payload.get("summary"), "LLM 已基于当前图谱、RAG 和整合指标生成分析。"),
        "",
        "### 单本书图谱精简建议",
        "",
        *_as_bullets(payload.get("single_book_focus")),
        "",
        "### 链接与可视化整理",
        "",
        *_as_bullets(payload.get("graph_cleanup")),
        "",
        "### 教学完整性判断",
        "",
        _as_text(payload.get("teaching_integrity"), "当前证据链保留 source_locator，可继续通过教师反馈修正整合决策。"),
        "",
        "### 风险与下一步",
        "",
        *_as_bullets([*_as_list(payload.get("risks")), *_as_list(payload.get("next_steps"))][:6]),
    ]
    return lines, metadata


def _as_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_bullets(value: object) -> list[str]:
    items = _as_list(value)
    if not items:
        return ["- 暂无额外建议。"]
    return [f"- {item}" for item in items[:4]]
