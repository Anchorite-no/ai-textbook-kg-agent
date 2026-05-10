from __future__ import annotations

import json
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


EXPECTED_CANONICALS = {
    "白细胞": {"白细胞", "白血球"},
    "动作电位": {"动作电位", "action potential"},
    "炎症": {"炎症", "inflammation"},
}
FORBIDDEN_PAIR_KEYWORDS = [
    ("抗原", "抗体"),
    ("神经系统", "肌肉"),
]


def main() -> None:
    settings.parsed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.graph_data_dir.mkdir(parents=True, exist_ok=True)
    settings.alignment_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_graphs = set(settings.graph_data_dir.glob("raw_*.json"))
    before_alignments = set(settings.alignment_data_dir.glob("alignment_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            raw_file_ids = _prepare_graphs(tmp)
            client = TestClient(app)
            started = time.perf_counter()
            build = client.post(
                "/api/alignment/build",
                json={
                    "raw_file_ids": raw_file_ids,
                    "force_rebuild": True,
                    "min_confidence": 0.62,
                    "include_singletons": False,
                },
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            assert build.status_code == 200, build.text
            alignment = build.json()["alignment"]
            report = _score_alignment(alignment, elapsed_ms)
            output_path = settings.alignment_data_dir / "stage7_alignment_benchmark_latest.json"
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: value for key, value in report.items() if key != "clusters"}, ensure_ascii=False, indent=2))
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.graph_data_dir.glob("raw_*.json"), before_graphs)
        cleanup_files(settings.alignment_data_dir.glob("alignment_*.json"), before_alignments)


def _prepare_graphs(tmp: str) -> list[str]:
    samples = {
        "book_a.md": (
            "# 第一章 白细胞\n"
            "白细胞是参与免疫防御的血细胞。白细胞能够识别抗原并参与炎症反应。\n"
            "# 第二章 动作电位\n"
            "动作电位是细胞膜电位快速变化的过程。静息电位是动作电位的基础。\n"
            "# 第三章 炎症\n"
            "炎症是机体对损伤因子产生的防御性反应。感染可以引起炎症。\n"
        ),
        "book_b.md": (
            "# 第一章 白血球\n"
            "白血球又称 leukocyte，是参与免疫防御的细胞。白血球可以在炎症过程中发挥作用。\n"
            "# 第二章 action potential\n"
            "action potential 指动作电位，是膜电位快速变化并沿神经细胞传播的过程。\n"
            "# 第三章 inflammation\n"
            "inflammation 指炎症，是组织对损伤和感染产生的防御性反应。\n"
        ),
        "book_c.md": (
            "# 第一章 抗原\n"
            "抗原能够刺激机体产生免疫应答。抗体可以特异性结合抗原。\n"
            "# 第二章 神经系统\n"
            "神经系统通过神经冲动调节肌肉收缩，但神经系统不是肌肉组织。\n"
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


def _score_alignment(alignment: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    clusters = alignment["clusters"]
    found = {name: _cluster_covers(clusters, name, aliases) for name, aliases in EXPECTED_CANONICALS.items()}
    forbidden_hits = _forbidden_hits(clusters)
    candidate_signal_completeness = 0.0
    if alignment["candidates"]:
        complete = sum(1 for candidate in alignment["candidates"] if candidate["signals"] and candidate["reason"] and candidate["evidence_chunk_ids"])
        candidate_signal_completeness = complete / len(alignment["candidates"])
    return {
        "benchmark": "00_stage7_alignment",
        "expected_cluster_count": len(EXPECTED_CANONICALS),
        "cluster_recall": _ratio(sum(1 for value in found.values() if value), len(EXPECTED_CANONICALS)),
        "forbidden_pair_hit_count": len(forbidden_hits),
        "candidate_signal_completeness": round(candidate_signal_completeness, 4),
        "average_build_ms": round(elapsed_ms, 2),
        "candidate_count": len(alignment["candidates"]),
        "cluster_count": len(clusters),
        "found": found,
        "forbidden_hits": forbidden_hits,
        "clusters": clusters,
    }


def _cluster_covers(clusters: list[dict[str, Any]], canonical_name: str, aliases: set[str]) -> bool:
    for cluster in clusters:
        names = {cluster["canonical_name"], *cluster["aliases"]}
        if canonical_name == cluster["canonical_name"] and len(names.intersection(aliases)) >= 2:
            return True
    return False


def _forbidden_hits(clusters: list[dict[str, Any]]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for cluster in clusters:
        names = {cluster["canonical_name"], *cluster["aliases"]}
        for left, right in FORBIDDEN_PAIR_KEYWORDS:
            if any(left in name for name in names) and any(right in name for name in names):
                hits.append({"cluster_id": cluster["id"], "left": left, "right": right})
    return hits


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
