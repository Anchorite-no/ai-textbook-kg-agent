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
from app.services.teacher_edit_storage import dialogue_path, teacher_edits_path  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


def main() -> None:
    for data_dir in (
        settings.parsed_data_dir,
        settings.graph_data_dir,
        settings.alignment_data_dir,
        settings.integration_data_dir,
        settings.teacher_edit_data_dir,
    ):
        data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_alignments = set(settings.alignment_data_dir.glob("alignment_*.json"))
    before_integrations = set(settings.integration_data_dir.glob("integration_*.json"))
    before_teacher_edits = set(settings.teacher_edit_data_dir.glob("teacher_edits_*.json"))
    before_dialogue = set(settings.teacher_edit_data_dir.glob("dialogue_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            raw_file_ids = _prepare_pipeline(tmp)
            client = TestClient(app)
            integration = _build_integration(client, raw_file_ids)
            decision = next(item for item in integration["decisions"] if item["action"] != "conflict")

            override = client.post(
                f"/api/integration/decisions/{decision['id']}/override",
                json={
                    "raw_file_ids": raw_file_ids,
                    "action": "conflict",
                    "retained_content": decision.get("retained_content") or "教师要求保留两种说法，课堂上单独说明差异。",
                    "reason": "教师认为该合并存在教学风险，需要作为冲突复核。",
                    "confidence": 1.0,
                    "created_by": "teacher_smoke",
                },
            )
            assert override.status_code == 200, override.text
            override_payload = override.json()
            assert override_payload["edit"]["operation"] == "override_decision", override_payload
            assert override_payload["decision"]["action"] == "conflict", override_payload
            assert override_payload["decision"]["metadata"]["teacher_override"] is True, override_payload
            assert override_payload["integration"]["metadata"]["updated_by_teacher"] is True, override_payload

            fetched = client.get(f"/api/integration?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert fetched.status_code == 200, fetched.text
            fetched_decision = next(item for item in fetched.json()["decisions"] if item["id"] == decision["id"])
            assert fetched_decision["action"] == "conflict", fetched_decision

            edits = client.get(f"/api/teacher-edits?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert edits.status_code == 200, edits.text
            assert edits.json()["count"] == 1, edits.text

            second_decision = next(item for item in fetched.json()["decisions"] if item["id"] != decision["id"])
            dialogue = client.post(
                "/api/dialogue/messages",
                json={
                    "raw_file_ids": raw_file_ids,
                    "message": f"请把 {second_decision['id']} 改为保留，避免误删课堂重点。",
                    "created_by": "teacher_smoke",
                    "retained_content": second_decision.get("retained_content") or "教师要求保留该知识点。",
                },
            )
            assert dialogue.status_code == 200, dialogue.text
            dialogue_payload = dialogue.json()
            assert dialogue_payload["edits"], dialogue_payload
            assert dialogue_payload["assistant_message"]["teacher_edit_ids"], dialogue_payload
            assert "覆盖" in dialogue_payload["assistant_message"]["content"], dialogue_payload

            history = client.get(f"/api/dialogue/messages?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert history.status_code == 200, history.text
            assert history.json()["count"] == 2, history.text
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)
        cleanup_files(settings.integration_data_dir.glob("integration_*.json"), before_integrations)
        cleanup_files(settings.teacher_edit_data_dir.glob("teacher_edits_*.json"), before_teacher_edits)
        cleanup_files(settings.teacher_edit_data_dir.glob("dialogue_*.json"), before_dialogue)
        integration_path([]).unlink(missing_ok=True)
        teacher_edits_path([]).unlink(missing_ok=True)
        dialogue_path([]).unlink(missing_ok=True)

    print("00 stage10 teacher edit smoke ok")


def _prepare_pipeline(tmp: str) -> list[str]:
    samples = {
        "book_a.md": (
            "# 第一章 白细胞\n"
            "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。"
            "白细胞的核心功能包括吞噬、递呈抗原和释放炎症介质。\n"
            "# 第二章 炎症\n"
            "炎症是机体对损伤因子产生的防御性反应。感染可以引起炎症，炎症反应包括血管扩张和白细胞聚集。\n"
            "# 附录 玻璃器皿\n"
            "玻璃器皿用于实验演示。玻璃器皿不是本章核心知识点，只作为课堂示例。\n"
        ),
        "book_b.md": (
            "# 第一章 白血球\n"
            "白血球又称 leukocyte，是参与免疫防御的细胞。白血球可以在炎症过程中发挥作用，并与抗原识别相关。\n"
            "# 第二章 炎症\n"
            "炎症不是感染本身，而是组织对损伤、感染或免疫刺激产生的反应。炎症可伴随红肿热痛。\n"
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


def _build_integration(client: TestClient, raw_file_ids: list[str]) -> dict:
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
    integration = build.json()["integration"]
    assert integration["decisions"], integration
    return integration


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
