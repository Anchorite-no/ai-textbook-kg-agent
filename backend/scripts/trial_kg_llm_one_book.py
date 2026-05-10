from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.models.schemas import GraphBuildRequest, GraphResponse  # noqa: E402
from app.services.converted_textbook_importer import import_converted_textbook  # noqa: E402
from app.services.knowledge_graph_builder import build_knowledge_graph  # noqa: E402
from app.services.llm_client import llm_client  # noqa: E402
from app.services.parsed_storage import list_parsed_textbooks, load_parsed_textbook  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a one-book KG build with LLM enabled when configured.")
    parser.add_argument("--title", default=None, help="Converted textbook title, e.g. 05_病理学.")
    parser.add_argument("--raw-file-id", default=None, help="Parsed raw_file_id to reuse.")
    parser.add_argument("--max-sections", type=int, default=12)
    parser.add_argument("--max-nodes-per-section", type=int, default=10)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "experiments" / "kg_llm_trial"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    graph_dir = output_dir / "graphs"
    cache_dir = output_dir / "llm_cache"
    report_path = output_dir / "latest_report.json"
    graph_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    settings.graph_data_dir = graph_dir
    settings.llm_cache_dir = cache_dir

    raw_file_id = _resolve_raw_file_id(args.raw_file_id, args.title)
    parsed = load_parsed_textbook(raw_file_id)
    if parsed is None:
        raise SystemExit(f"Parsed textbook not found: {raw_file_id}")

    started = time.perf_counter()
    graph, graph_output_path, _cache_hit = build_knowledge_graph(
        GraphBuildRequest(
            raw_file_id=raw_file_id,
            force_rebuild=True,
            max_sections=args.max_sections,
            max_nodes_per_section=args.max_nodes_per_section,
            use_llm=True,
        )
    )
    elapsed = time.perf_counter() - started
    report = _build_report(graph, graph_output_path, elapsed)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(_console_summary(report), ensure_ascii=False, indent=2))


def _resolve_raw_file_id(raw_file_id: str | None, title: str | None) -> str:
    if raw_file_id:
        return raw_file_id

    if title:
        parsed, _path = import_converted_textbook(textbook_title=title)
        return parsed.raw_file.id

    summaries = list_parsed_textbooks()
    if summaries:
        return summaries[0].raw_file_id

    parsed, _path = import_converted_textbook(textbook_title="01_局部解剖学")
    return parsed.raw_file.id


def _build_report(graph: GraphResponse, graph_output_path: str, elapsed_seconds: float) -> dict[str, Any]:
    node_count = len(graph.nodes)
    edge_count = len(graph.edges)
    verified_nodes = sum(1 for node in graph.nodes if node.metadata.get("source_quote_verified") is True)
    verified_edges = sum(1 for edge in graph.edges if edge.metadata.get("source_quote_verified") is True)
    node_methods = Counter(str(node.metadata.get("extraction_method") or "unknown") for node in graph.nodes)
    edge_methods = Counter(str(edge.metadata.get("extraction_method") or "unknown") for edge in graph.edges)
    relation_types = Counter(edge.relation_type.value for edge in graph.edges)
    node_name_by_id = {node.id: node.name for node in graph.nodes}

    report: dict[str, Any] = {
        "experiment": "kg_llm_one_book",
        "title": graph.title,
        "raw_file_id": graph.raw_file_id,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "graph_output_path": graph_output_path,
        "llm": {
            "enabled": llm_client.is_enabled(),
            "provider": settings.llm_provider,
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
            "calls": graph.metadata.get("llm_calls", 0),
            "cache_hits": graph.metadata.get("llm_cache_hits", 0),
            "errors": graph.metadata.get("llm_errors", 0),
            "sections": graph.metadata.get("llm_sections", 0),
            "grounded_sections": graph.metadata.get("llm_grounded_sections", 0),
            "fallback_sections": graph.metadata.get("fallback_sections", 0),
            "supplemented_sections": graph.metadata.get("supplemented_sections", 0),
        },
        "quality": {
            "section_count": graph.metadata.get("section_count", 0),
            "node_count": node_count,
            "edge_count": edge_count,
            "node_evidence_coverage": _ratio(verified_nodes, node_count),
            "edge_evidence_coverage": _ratio(verified_edges, edge_count),
            "relation_type_count": len(relation_types),
            "relation_types": dict(relation_types),
            "node_extraction_methods": dict(node_methods),
            "edge_extraction_methods": dict(edge_methods),
        },
        "samples": {
            "nodes": [
                {
                    "name": node.name,
                    "type": node.node_type.value,
                    "confidence": node.confidence,
                    "method": node.metadata.get("extraction_method"),
                    "quote": node.metadata.get("source_quote"),
                    "page": node.source_locator.page_start,
                }
                for node in graph.nodes[:12]
            ],
            "edges": [
                {
                    "source": node_name_by_id.get(edge.source_node_id, edge.source_node_id),
                    "target": node_name_by_id.get(edge.target_node_id, edge.target_node_id),
                    "relation_type": edge.relation_type.value,
                    "confidence": edge.confidence,
                    "method": edge.metadata.get("extraction_method"),
                    "quote": edge.metadata.get("source_quote"),
                    "page": edge.source_locator.page_start,
                }
                for edge in graph.edges[:12]
            ],
        },
    }
    if not llm_client.is_enabled():
        report["warning"] = "LLM is not enabled. Set LLM_PROVIDER=openai-compatible and OPENAI_API_KEY to run real LLM extraction."
    return report


def _console_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment": report["experiment"],
        "title": report["title"],
        "raw_file_id": report["raw_file_id"],
        "elapsed_seconds": report["elapsed_seconds"],
        "graph_output_path": report["graph_output_path"],
        "llm": report["llm"],
        "quality": report["quality"],
        "warning": report.get("warning"),
    }


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


if __name__ == "__main__":
    main()
