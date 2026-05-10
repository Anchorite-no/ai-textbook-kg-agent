from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    client = TestClient(app)
    _assert_seven_book_dataset(client)
    _assert_upload_organize_workflow(client)
    print("frontend dataset/workflow smoke ok")


def _assert_seven_book_dataset(client: TestClient) -> None:
    response = client.get("/api/datasets/seven-books")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "seven_medical_textbooks", payload
    assert payload["book_count"] == 7, payload
    assert len(payload["raw_file_ids"]) == 7, payload
    assert payload["metrics"]["parsed_ready_count"] == 7, payload
    assert payload["metrics"]["graph_ready_count"] == 7, payload
    assert payload["rag_ready"] is True, payload
    assert payload["alignment_ready"] is True, payload
    assert payload["integration_ready"] is True, payload
    assert payload["status"] == "ready", payload
    assert payload["endpoints"]["textbooks"] == "/api/textbooks", payload
    assert payload["endpoints"]["self"] == "/api/datasets/seven-books", payload
    assert all(book["endpoints"]["textbook"].startswith("/api/textbooks/raw_") for book in payload["books"]), payload


def _assert_upload_organize_workflow(client: TestClient) -> None:
    old_paths = {
        "parsed_data_dir": settings.parsed_data_dir,
        "upload_dir": settings.upload_dir,
        "upload_sessions_dir": settings.upload_sessions_dir,
        "job_data_dir": settings.job_data_dir,
        "index_data_dir": settings.index_data_dir,
        "graph_data_dir": settings.graph_data_dir,
        "layered_graph_data_dir": settings.layered_graph_data_dir,
        "alignment_data_dir": settings.alignment_data_dir,
        "integration_data_dir": settings.integration_data_dir,
        "teacher_edit_data_dir": settings.teacher_edit_data_dir,
        "llm_cache_dir": settings.llm_cache_dir,
    }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings.parsed_data_dir = root / "parsed"
        settings.upload_dir = root / "uploads"
        settings.upload_sessions_dir = root / "uploads" / "sessions"
        settings.job_data_dir = root / "jobs"
        settings.index_data_dir = root / "indexes"
        settings.graph_data_dir = root / "graphs"
        settings.layered_graph_data_dir = root / "graphs" / "layers"
        settings.alignment_data_dir = root / "alignments"
        settings.integration_data_dir = root / "integrations"
        settings.teacher_edit_data_dir = root / "teacher_edits"
        settings.llm_cache_dir = root / "graphs" / "llm_cache"
        try:
            files = [
                (
                    "files",
                    (
                        "demo_a.md",
                        (
                            "# 第一章 白细胞\n"
                            "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。\n"
                            "# 第二章 动作电位\n"
                            "动作电位是膜电位快速变化的过程。静息电位是动作电位的基础。\n"
                        ).encode("utf-8"),
                        "text/markdown",
                    ),
                ),
                (
                    "files",
                    (
                        "demo_b.md",
                        (
                            "# 第一章 白血球\n"
                            "白血球又称 leukocyte，是参与免疫防御的细胞，可在炎症过程中发挥作用。\n"
                            "# 第二章 神经兴奋\n"
                            "静息电位是动作电位发生的基础，动作电位进一步解释神经冲动传导机制。\n"
                        ).encode("utf-8"),
                        "text/markdown",
                    ),
                ),
            ]
            response = client.post(
                "/api/workflows/organize",
                files=files,
                data={
                    "use_llm": "false",
                    "max_sections": "20",
                    "max_nodes_per_section": "10",
                    "alignment_min_confidence": "0.55",
                },
            )
            assert response.status_code == 200, response.text
            accepted = response.json()
            job_id = accepted["job"]["id"]
            job = client.get(f"/api/jobs/{job_id}")
            assert job.status_code == 200, job.text
            job_payload = job.json()
            assert job_payload["status"] == "completed", job_payload
            raw_file_ids = job_payload["result"]["raw_file_ids"]
            assert len(raw_file_ids) == 2, job_payload

            textbooks = client.get("/api/textbooks")
            assert textbooks.status_code == 200, textbooks.text
            assert len(textbooks.json()["textbooks"]) == 2, textbooks.text

            graph = client.get(f"/api/graph?raw_file_id={raw_file_ids[0]}&top_n=100")
            assert graph.status_code == 200, graph.text
            assert graph.json()["nodes"], graph.text

            rag_status = client.get("/api/rag/status")
            assert rag_status.status_code == 200, rag_status.text
            assert set(raw_file_ids).issubset(set(rag_status.json()["raw_file_ids"])), rag_status.text

            alignment = client.get(f"/api/alignment?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert alignment.status_code == 200, alignment.text
            integration = client.get(f"/api/integration?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert integration.status_code == 200, integration.text

            graphrag = client.get(f"/api/graphrag/status?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert graphrag.status_code == 200, graphrag.text
            assert graphrag.json()["status"] == "ready", graphrag.text
        finally:
            for name, value in old_paths.items():
                setattr(settings, name, value)


if __name__ == "__main__":
    main()
