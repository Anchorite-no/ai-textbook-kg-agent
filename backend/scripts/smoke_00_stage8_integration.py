from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.integration_storage import integration_path  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


def main() -> None:
    for data_dir in (settings.parsed_data_dir, settings.graph_data_dir, settings.alignment_data_dir, settings.integration_data_dir):
        data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_alignments = set(settings.alignment_data_dir.glob("alignment_*.json"))
    before_integrations = set(settings.integration_data_dir.glob("integration_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            raw_file_ids = _prepare_graphs(tmp)
            client = TestClient(app)
            build = client.post(
                "/api/integration/build",
                json={
                    "raw_file_ids": raw_file_ids,
                    "force_rebuild": True,
                    "target_compression_ratio": 0.30,
                    "alignment_min_confidence": 0.55,
                    "include_keep_decisions": True,
                    "max_nodes": 1000,
                },
            )
            assert build.status_code == 200, build.text
            payload = build.json()
            assert payload["job"]["status"] == "completed", payload
            integration = payload["integration"]

            actions = {decision["action"] for decision in integration["decisions"]}
            assert {"merge", "keep", "remove"}.issubset(actions), actions
            assert "refine" in actions, actions
            assert "conflict" in actions, actions
            assert integration["integrated_concepts"], integration

            stats = integration["compression_stats"]
            assert stats["compression_ratio"] <= stats["target_compression_ratio"], stats
            assert stats["integrated_node_count"] < stats["original_node_count"], stats
            assert stats["evidence_coverage_ratio"] == 1.0, stats
            assert stats["removed_node_count"] >= 1, stats
            assert stats["merged_node_count"] >= 1, stats

            for decision in integration["decisions"]:
                assert decision["reason"], decision
                assert decision["confidence"] > 0, decision
                assert decision["evidence_chunk_ids"], decision
                assert decision["source_locators"], decision

            for concept in integration["integrated_concepts"]:
                assert concept["definition"], concept
                assert concept["source_locators"], concept
                assert concept["evidence_chunk_ids"], concept
                assert concept["decision_ids"], concept

            fetched = client.get(f"/api/integration?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["id"] == integration["id"], fetched.text

            cached = client.post("/api/integration/build", json={"raw_file_ids": raw_file_ids, "force_rebuild": False})
            assert cached.status_code == 200, cached.text
            assert cached.json()["job"]["result"]["cache_hit"] is True, cached.text
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)
        cleanup_files(settings.integration_data_dir.glob("integration_*.json"), before_integrations)
        integration_path([]).unlink(missing_ok=True)

    print("00 stage8 integration smoke ok")


def _prepare_graphs(tmp: str) -> list[str]:
    samples = {
        "book_a.md": (
            "# 第一章 白细胞\n"
            "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。"
            "白细胞的核心功能包括吞噬、递呈抗原和释放炎症介质。\n"
            "# 第二章 动作电位\n"
            "动作电位是细胞膜电位快速变化的过程。静息电位是动作电位的基础，膜电位改变推动神经传导。\n"
            "# 第三章 炎症\n"
            "炎症是机体对损伤因子产生的防御性反应。感染可以引起炎症，炎症反应包括血管扩张和白细胞聚集。\n"
            "# 第四章 毛细血管\n"
            "毛细血管是物质交换的重要结构，毛细血管网络连接小动脉和小静脉。\n"
            "# 附录 玻璃器皿\n"
            "玻璃器皿用于实验演示。玻璃器皿不是本章核心知识点，只作为课堂示例。\n"
        ),
        "book_b.md": (
            "# 第一章 白血球\n"
            "白血球又称 leukocyte，是参与免疫防御的细胞。白血球可以在炎症过程中发挥作用，并与抗原识别相关。\n"
            "# 第二章 动作电位\n"
            "动作电位是膜电位快速去极化和复极化并沿神经细胞传播的过程。动作电位依赖离子通道开放，"
            "它进一步解释神经冲动传导机制。\n"
            "# 第三章 炎症\n"
            "炎症不是感染本身，而是组织对损伤、感染或免疫刺激产生的反应。炎症可伴随红肿热痛。\n"
            "# 第四章 肌肉组织\n"
            "肌肉组织通过收缩产生运动，神经系统可以调节肌肉组织活动。\n"
            "# 附录 课堂颜色\n"
            "课堂颜色用于图示标记。课堂颜色不是医学概念，通常不进入核心知识图谱。\n"
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
    return raw_file_ids


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
