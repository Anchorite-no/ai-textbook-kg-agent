from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


NO_ANSWER = "当前知识库中未找到相关信息。"
QUESTIONS = [
    {"question": "白细胞是什么？", "intent": "definition", "expected_terms": ["白细胞"], "requires": ["citations", "nodes"]},
    {"question": "白细胞出现在哪些教材？", "intent": "coverage", "expected_terms": ["book_a", "book_b"], "requires": ["citations", "nodes"]},
    {"question": "两本教材对白细胞的说法有什么差异？", "intent": "comparison", "expected_terms": ["不同教材", "book_a", "book_b"], "requires": ["citations", "nodes"]},
    {"question": "学习动作电位前要先学什么？", "intent": "prerequisite", "expected_terms": ["静息电位", "PREREQUISITE_OF"], "requires": ["citations", "nodes", "paths"]},
    {"question": "静息电位和动作电位之间是什么关系？", "intent": "relation_path", "expected_terms": ["PREREQUISITE_OF"], "requires": ["citations", "nodes", "paths"]},
    {"question": "系统为什么合并白细胞节点？", "intent": "decision_review", "expected_terms": ["merge", "白细胞"], "requires": ["citations", "nodes", "decisions"]},
    {"question": "系统为什么删除课堂颜色节点？", "intent": "decision_review", "expected_terms": ["remove"], "requires": ["citations", "nodes", "decisions"]},
    {"question": "量子隧穿显微镜的核心结构是什么？", "intent": "definition", "expected_terms": [], "expect_no_answer": True},
    {"question": "火星土壤采样器如何影响白细胞？", "intent": "hybrid", "expected_terms": [], "expect_no_answer": True},
]


def main() -> None:
    for data_dir in (settings.parsed_data_dir, settings.graph_data_dir, settings.alignment_data_dir, settings.integration_data_dir, settings.index_data_dir):
        data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_alignments = set(settings.alignment_data_dir.glob("alignment_*.json"))
    before_integrations = set(settings.integration_data_dir.glob("integration_*.json"))
    index_path = settings.index_data_dir / "rag_index.json"
    old_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None

    try:
        with TemporaryDirectory() as tmp:
            raw_file_ids = _prepare_pipeline(tmp)
            client = TestClient(app)
            results = [_run_question(client, raw_file_ids, item) for item in QUESTIONS]
            answerable = [item for item in results if not item["expect_no_answer"]]
            no_answer = [item for item in results if item["expect_no_answer"]]
            path_questions = [item for item in answerable if item["requires_paths"]]
            decision_questions = [item for item in answerable if item["requires_decisions"]]
            report = {
                "benchmark": "00_stage9_graphrag",
                "question_count": len(results),
                "answerable_count": len(answerable),
                "no_answer_count": len(no_answer),
                "intent_coverage": {intent: any(item["intent"] == intent and item["hit"] for item in results) for intent in sorted({item["intent"] for item in QUESTIONS})},
                "citation_grounding_rate": _ratio(sum(1 for item in answerable if item["citation_count"] > 0), len(answerable)),
                "node_hit_rate": _ratio(sum(1 for item in answerable if item["node_hit_count"] > 0), len(answerable)),
                "path_question_hit_rate": _ratio(sum(1 for item in path_questions if item["path_count"] > 0), len(path_questions)),
                "decision_question_hit_rate": _ratio(sum(1 for item in decision_questions if item["decision_count"] > 0), len(decision_questions)),
                "answer_term_hit_rate": _ratio(sum(1 for item in answerable if item["hit"]), len(answerable)),
                "no_answer_rejection_rate": _ratio(sum(1 for item in no_answer if item["hit"]), len(no_answer)),
                "average_response_ms": round(statistics.mean(item["elapsed_ms"] for item in results), 2),
                "retrieval": "graphrag_chunk_node_path_decision",
                "results": results,
            }
            assert report["citation_grounding_rate"] == 1.0, report
            assert report["node_hit_rate"] == 1.0, report
            assert report["path_question_hit_rate"] == 1.0, report
            assert report["decision_question_hit_rate"] == 1.0, report
            assert report["answer_term_hit_rate"] == 1.0, report
            assert report["no_answer_rejection_rate"] == 1.0, report

            output_path = settings.index_data_dir / "stage9_graphrag_benchmark_latest.json"
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)
        cleanup_files(settings.integration_data_dir.glob("integration_*.json"), before_integrations)
        if old_index is None:
            index_path.unlink(missing_ok=True)
        else:
            index_path.write_text(old_index, encoding="utf-8")


def _prepare_pipeline(tmp: str) -> list[str]:
    samples = {
        "book_a.md": (
            "# 第一章 白细胞\n"
            "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。"
            "白细胞的核心功能包括吞噬和释放炎症介质。\n"
            "# 第二章 动作电位\n"
            "动作电位是细胞膜电位快速变化的过程。静息电位是动作电位的基础，膜电位改变推动神经传导。\n"
            "# 第三章 炎症\n"
            "炎症是机体对损伤因子产生的防御性反应。感染可以引起炎症。\n"
            "# 附录 课堂颜色\n"
            "课堂颜色用于图示标记。课堂颜色不是医学概念，通常不进入核心知识图谱。\n"
        ),
        "book_b.md": (
            "# 第一章 白血球\n"
            "白血球又称 leukocyte，是参与免疫防御的细胞。白血球可以在炎症过程中发挥作用，并与抗原识别相关。\n"
            "# 第二章 动作电位\n"
            "动作电位是膜电位快速去极化和复极化并沿神经细胞传播的过程。静息电位是动作电位发生的基础，"
            "它进一步解释神经冲动传导机制。\n"
            "# 第三章 炎症\n"
            "炎症不是感染本身，而是组织对损伤、感染或免疫刺激产生的反应。炎症可伴随红肿热痛。\n"
            "# 附录 玻璃器皿\n"
            "玻璃器皿用于实验演示。玻璃器皿不是本章核心知识点，只作为课堂示例。\n"
        ),
    }
    client = TestClient(app)
    raw_file_ids: list[str] = []
    for filename, text in samples.items():
        path = Path(tmp) / filename
        path.write_text(text, encoding="utf-8")
        parsed, _ = parse_uploaded_file(path, path.name)
        raw_file_ids.append(parsed.raw_file.id)
        graph = client.post(
            "/api/graph/build",
            json={
                "raw_file_id": parsed.raw_file.id,
                "force_rebuild": True,
                "max_sections": 20,
                "max_nodes_per_section": 12,
                "use_llm": False,
            },
        )
        assert graph.status_code == 200, graph.text
    index = client.post("/api/rag/index", json={"raw_file_ids": raw_file_ids, "force_rebuild": True})
    assert index.status_code == 200, index.text
    alignment = client.post("/api/alignment/build", json={"raw_file_ids": raw_file_ids, "force_rebuild": True, "min_confidence": 0.55})
    assert alignment.status_code == 200, alignment.text
    integration = client.post(
        "/api/integration/build",
        json={
            "raw_file_ids": raw_file_ids,
            "force_rebuild": True,
            "target_compression_ratio": 0.30,
            "alignment_min_confidence": 0.55,
        },
    )
    assert integration.status_code == 200, integration.text
    return raw_file_ids


def _run_question(client: TestClient, raw_file_ids: list[str], item: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.post(
        "/api/graphrag/query",
        json={"question": item["question"], "top_k": 5, "raw_file_ids": raw_file_ids, "include_decisions": True},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    payload = response.json()
    expect_no_answer = bool(item.get("expect_no_answer"))
    if expect_no_answer:
        hit = payload["answer"] == NO_ANSWER and not payload["citations"]
    else:
        combined = payload["answer"] + "\n" + "\n".join(citation["quote"] for citation in payload["citations"])
        hit = payload["intent"] == item["intent"] and all(term in combined for term in item["expected_terms"])
        for required in item.get("requires", []):
            if required == "citations":
                hit = hit and bool(payload["citations"])
            if required == "nodes":
                hit = hit and bool(payload["node_hits"])
            if required == "paths":
                hit = hit and bool(payload["paths"])
            if required == "decisions":
                hit = hit and bool(payload["decisions"])
    return {
        "question": item["question"],
        "intent": payload["intent"],
        "expected_intent": item["intent"],
        "expected_terms": item["expected_terms"],
        "expect_no_answer": expect_no_answer,
        "requires_paths": "paths" in item.get("requires", []),
        "requires_decisions": "decisions" in item.get("requires", []),
        "hit": hit,
        "citation_count": len(payload["citations"]),
        "node_hit_count": len(payload["node_hits"]),
        "path_count": len(payload["paths"]),
        "decision_count": len(payload["decisions"]),
        "elapsed_ms": round(elapsed_ms, 2),
        "answer": payload["answer"],
    }


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
