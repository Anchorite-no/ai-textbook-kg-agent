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


def main() -> None:
    settings.parsed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.graph_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            sample = Path(tmp) / "kg_sample.md"
            sample.write_text(
                "# 第一章 膜电位\n"
                "静息电位是动作电位的基础。"
                "动作电位是一种膜电位变化。"
                "细胞膜结构组成神经细胞。"
                "动作电位用于神经传导。"
                "膜电位变化导致神经传导过程。"
                "动作电位与静息电位不同。"
                "动作电位和静息电位都是膜电位。\n",
                encoding="utf-8",
            )
            parsed, _output_path = parse_uploaded_file(sample, sample.name)

            client = TestClient(app)
            build = client.post(
                "/api/graph/build",
                json={
                    "raw_file_id": parsed.raw_file.id,
                    "force_rebuild": True,
                    "max_sections": 5,
                    "max_nodes_per_section": 8,
                    "use_llm": False,
                },
            )
            assert build.status_code == 200, build.text
            payload = build.json()
            assert payload["job"]["status"] == "completed", payload
            assert len(payload["graph"]["nodes"]) >= 2, payload
            assert len(payload["graph"]["edges"]) >= 1, payload
            relation_types = {edge["relation_type"] for edge in payload["graph"]["edges"]}
            assert "PREREQUISITE_OF" in relation_types, relation_types
            assert "CONTAINS" in relation_types, relation_types
            assert "IS_A" in relation_types or "PART_OF" in relation_types, relation_types
            assert "CONTRASTS_WITH" in relation_types, relation_types
            assert "CAUSES" in relation_types or "APPLIES_TO" in relation_types, relation_types
            for node in payload["graph"]["nodes"]:
                assert node["source_locator"]["raw_file_id"] == parsed.raw_file.id
                assert node["evidence_chunk_ids"], node
                assert node["metadata"]["source_quote"], node
                assert node["metadata"]["source_quote_verified"] is True, node
                assert node["metadata"]["evidence_strategy"], node
                assert node["metadata"]["chapter"], node
            for edge in payload["graph"]["edges"]:
                assert edge["source_locator"]["raw_file_id"] == parsed.raw_file.id
                assert edge["evidence_chunk_ids"], edge
                assert edge["metadata"]["source_quote"], edge
                assert edge["metadata"]["source_quote_verified"] is True, edge
                assert edge["metadata"]["evidence_strategy"], edge

            graph = client.get(f"/api/graph?raw_file_id={parsed.raw_file.id}&top_n=200")
            assert graph.status_code == 200, graph.text
            assert graph.json()["raw_file_id"] == parsed.raw_file.id

            node_id = payload["graph"]["nodes"][0]["id"]
            detail = client.get(f"/api/graph/nodes/{node_id}")
            assert detail.status_code == 200, detail.text
            detail_payload = detail.json()
            assert detail_payload["node"]["id"] == node_id
            assert detail_payload["evidence_chunks"], detail_payload

            cached = client.post("/api/graph/build", json={"raw_file_id": parsed.raw_file.id, "force_rebuild": False})
            assert cached.status_code == 200, cached.text
            assert cached.json()["job"]["result"]["cache_hit"] is True
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)

    print("phase3 smoke ok")


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
