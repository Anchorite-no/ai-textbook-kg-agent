from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


NO_ANSWER = "当前知识库中未找到相关信息。"


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

            status = client.get(f"/api/graphrag/status?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert status.status_code == 200, status.text
            status_payload = status.json()
            assert status_payload["status"] == "ready", status_payload
            assert status_payload["graph_count"] == 2, status_payload
            assert status_payload["alignment_available"] is True, status_payload
            assert status_payload["integration_available"] is True, status_payload

            cases = [
                ("白细胞是什么？", "definition", ["白细胞"]),
                ("白细胞出现在哪些教材？", "coverage", ["book_a", "book_b"]),
                ("两本教材对白细胞的说法有什么差异？", "comparison", ["不同教材"]),
                ("学习动作电位前要先学什么？", "prerequisite", ["PREREQUISITE_OF"]),
                ("静息电位和动作电位之间是什么关系？", "relation_path", ["PREREQUISITE_OF"]),
                ("系统为什么合并白细胞节点？", "decision_review", ["merge", "白细胞"]),
            ]
            for question, intent, expected_terms in cases:
                response = client.post(
                    "/api/graphrag/query",
                    json={"question": question, "top_k": 5, "raw_file_ids": raw_file_ids, "include_decisions": True},
                )
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload["intent"] == intent, payload
                assert payload["answer"] != NO_ANSWER, payload
                assert payload["citations"], payload
                assert payload["source_chunks"], payload
                assert payload["node_hits"], payload
                assert payload["metadata"]["retrieval"] == "graphrag_chunk_node_path_decision", payload
                combined = payload["answer"] + "\n" + "\n".join(citation["quote"] for citation in payload["citations"])
                assert all(term in combined for term in expected_terms), payload
                if intent in {"prerequisite", "relation_path"}:
                    assert payload["paths"], payload
                    assert payload["paths"][0]["steps"], payload
                if intent == "decision_review":
                    assert payload["decisions"], payload

            miss = client.post(
                "/api/graphrag/query",
                json={"question": "量子隧穿显微镜的核心结构是什么？", "top_k": 5, "raw_file_ids": raw_file_ids},
            )
            assert miss.status_code == 200, miss.text
            miss_payload = miss.json()
            assert miss_payload["answer"] == NO_ANSWER, miss_payload
            assert not miss_payload["citations"], miss_payload
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)
        cleanup_files(settings.integration_data_dir.glob("integration_*.json"), before_integrations)
        if old_index is None:
            index_path.unlink(missing_ok=True)
        else:
            index_path.write_text(old_index, encoding="utf-8")

    print("00 stage9 graphrag smoke ok")


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


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
