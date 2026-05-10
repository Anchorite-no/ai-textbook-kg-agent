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
    settings.layered_graph_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_layered = set(settings.layered_graph_data_dir.glob("raw_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            sample = Path(tmp) / "layered_kg_sample.md"
            sample.write_text(
                "# 第一章 神经调节\n"
                "静息电位是动作电位的基础。"
                "动作电位用于神经传导。"
                "膜电位变化导致神经传导过程。"
                "动作电位和静息电位都是膜电位。\n",
                encoding="utf-8",
            )
            parsed, _output_path = parse_uploaded_file(sample, sample.name)
            client = TestClient(app)

            graph_build = client.post(
                "/api/graph/build",
                json={
                    "raw_file_id": parsed.raw_file.id,
                    "force_rebuild": True,
                    "max_sections": 5,
                    "max_nodes_per_section": 8,
                    "use_llm": False,
                },
            )
            assert graph_build.status_code == 200, graph_build.text

            layer_build = client.post(
                "/api/kg/layers/build",
                json={
                    "raw_file_id": parsed.raw_file.id,
                    "force_rebuild": True,
                    "build_missing_concept_graph": False,
                    "use_llm": False,
                },
            )
            assert layer_build.status_code == 200, layer_build.text
            payload = layer_build.json()
            assert payload["job"]["status"] == "completed", payload
            layered = payload["layered_graph"]
            assert layered["raw_file_id"] == parsed.raw_file.id

            layers = {layer["layer_type"]: layer for layer in layered["layers"]}
            assert layers["document_tree"]["status"] == "ready", layers
            assert layers["concept_kg"]["status"] == "ready", layers
            assert layers["evidence_graph"]["status"] == "ready", layers
            assert layers["alias_alignment"]["status"] == "reserved", layers
            assert layers["integration_decision"]["status"] == "reserved", layers
            assert layers["teacher_edit"]["status"] == "reserved", layers
            assert layers["graphrag_retrieval"]["status"] == "reserved", layers
            assert layers["document_tree"]["node_count"] >= len(parsed.sections) + len(parsed.chunks) + 1, layers
            assert layers["concept_kg"]["node_count"] >= 2, layers
            assert layers["evidence_graph"]["edge_count"] >= 1, layers

            for node in layered["nodes"]:
                assert node["source_locator"]["raw_file_id"] == parsed.raw_file.id, node
                if node["node_type"] == "Chunk":
                    assert node["evidence_chunk_ids"], node
            for edge in layered["edges"]:
                assert edge["source_locator"]["raw_file_id"] == parsed.raw_file.id, edge
                if edge["relation_type"] in {"HAS_CHUNK", "EVIDENCED_BY"}:
                    assert edge["evidence_chunk_ids"], edge

            document_edges = {edge["relation_type"] for edge in layered["edges"] if edge["layer_type"] == "document_tree"}
            concept_edges = {edge["relation_type"] for edge in layered["edges"] if edge["layer_type"] == "concept_kg"}
            evidence_edges = {edge["relation_type"] for edge in layered["edges"] if edge["layer_type"] == "evidence_graph"}
            assert {"CONTAINS", "HAS_CHUNK"}.issubset(document_edges), document_edges
            assert "PREREQUISITE_OF" in concept_edges, concept_edges
            assert "EVIDENCED_BY" in evidence_edges, evidence_edges

            fetched = client.get(f"/api/kg/layers?raw_file_id={parsed.raw_file.id}")
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["id"] == layered["id"]

            cached = client.post("/api/kg/layers/build", json={"raw_file_id": parsed.raw_file.id, "force_rebuild": False})
            assert cached.status_code == 200, cached.text
            assert cached.json()["job"]["result"]["cache_hit"] is True
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.layered_graph_data_dir.glob("raw_*.json"), before_layered)

    print("00 stage6 layered kg smoke ok")


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
