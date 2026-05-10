from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.alignment_storage import alignment_path  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


def main() -> None:
    settings.parsed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.graph_data_dir.mkdir(parents=True, exist_ok=True)
    settings.alignment_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_alignments = set(settings.alignment_data_dir.glob("alignment_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            book_a = Path(tmp) / "book_a.md"
            book_b = Path(tmp) / "book_b.md"
            book_a.write_text(
                "# 第一章 白细胞\n"
                "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。\n"
                "# 第二章 动作电位\n"
                "动作电位是细胞膜电位快速变化的过程。静息电位是动作电位的基础。\n",
                encoding="utf-8",
            )
            book_b.write_text(
                "# 第一章 白血球\n"
                "白血球又称 leukocyte，是参与免疫防御的细胞。白血球可以在炎症过程中发挥作用。\n"
                "# 第二章 action potential\n"
                "action potential 指动作电位，是膜电位快速变化并沿神经细胞传播的过程。\n",
                encoding="utf-8",
            )
            parsed_a, _ = parse_uploaded_file(book_a, book_a.name)
            parsed_b, _ = parse_uploaded_file(book_b, book_b.name)
            raw_file_ids = [parsed_a.raw_file.id, parsed_b.raw_file.id]

            client = TestClient(app)
            for raw_file_id in raw_file_ids:
                graph = client.post(
                    "/api/graph/build",
                    json={
                        "raw_file_id": raw_file_id,
                        "force_rebuild": True,
                        "max_sections": 20,
                        "max_nodes_per_section": 12,
                        "use_llm": False,
                    },
                )
                assert graph.status_code == 200, graph.text
                assert graph.json()["graph"]["nodes"], graph.text

            build = client.post(
                "/api/alignment/build",
                json={
                    "raw_file_ids": raw_file_ids,
                    "force_rebuild": True,
                    "min_confidence": 0.55,
                    "include_singletons": False,
                },
            )
            assert build.status_code == 200, build.text
            payload = build.json()
            assert payload["job"]["status"] == "completed", payload
            alignment = payload["alignment"]
            assert alignment["clusters"], alignment
            assert alignment["canonical_concepts"], alignment
            assert alignment["candidates"], alignment

            cluster_by_name = {cluster["canonical_name"]: cluster for cluster in alignment["clusters"]}
            assert "白细胞" in cluster_by_name, cluster_by_name
            assert len(cluster_by_name["白细胞"]["member_node_ids"]) >= 2, cluster_by_name["白细胞"]
            assert cluster_by_name["白细胞"]["confidence"] >= 0.55, cluster_by_name["白细胞"]
            assert cluster_by_name["白细胞"]["evidence_chunk_ids"], cluster_by_name["白细胞"]

            aliases = {(item["canonical_name"], item["alias"]) for item in alignment["aliases"]}
            assert any(canonical == "白细胞" and alias in {"白血球", "白血球又称leukocyte", "leukocyte"} for canonical, alias in aliases), aliases

            relation_types = {candidate["relation_type"] for candidate in alignment["candidates"]}
            assert "ALIAS_OF" in relation_types or "SAME_AS" in relation_types, relation_types

            for candidate in alignment["candidates"]:
                assert candidate["confidence"] >= 0.55, candidate
                assert candidate["signals"], candidate
                assert candidate["reason"], candidate
                assert candidate["evidence_chunk_ids"], candidate
                assert len(candidate["source_locators"]) == 2, candidate
                signal_names = {signal["name"] for signal in candidate["signals"]}
                assert {"normalized_name", "alias_table", "definition_similarity", "hash_embedding"}.issubset(signal_names), signal_names

            fetched = client.get(f"/api/alignment?raw_file_ids={raw_file_ids[0]},{raw_file_ids[1]}")
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["id"] == alignment["id"], fetched.text

            cached = client.post("/api/alignment/build", json={"raw_file_ids": raw_file_ids, "force_rebuild": False})
            assert cached.status_code == 200, cached.text
            assert cached.json()["job"]["result"]["cache_hit"] is True, cached.text
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)
        alignment_path([]).unlink(missing_ok=True)

    print("00 stage7 alignment smoke ok")


def cleanup_files(paths: object, before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
