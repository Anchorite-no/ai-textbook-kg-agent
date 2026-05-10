from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.uploaded_file_parser import parse_uploaded_file  # noqa: E402


NO_ANSWER = "当前知识库中未找到相关信息。"
QUESTIONS = [
    {"question": "动作电位是什么？", "expected_terms": ["动作电位", "膜电位"]},
    {"question": "静息电位对动作电位有什么作用？", "expected_terms": ["静息电位", "基础"]},
    {"question": "神经传导依赖什么？", "expected_terms": ["神经传导", "动作电位"]},
    {"question": "炎症的基本定义是什么？", "expected_terms": ["炎症", "防御性反应"]},
    {"question": "白细胞有什么作用？", "expected_terms": ["白细胞", "免疫"]},
    {"question": "抗原是什么？", "expected_terms": ["抗原", "免疫"]},
    {"question": "细胞膜结构有什么功能？", "expected_terms": ["细胞膜", "选择通透性"]},
    {"question": "酶反应受什么影响？", "expected_terms": ["酶反应", "温度"]},
    {"question": "血管收缩会导致什么？", "expected_terms": ["血管收缩", "血压"]},
    {"question": "淋巴系统包含什么？", "expected_terms": ["淋巴系统", "淋巴结"]},
    {"question": "动作电位和静息电位有什么关系？", "expected_terms": ["动作电位", "静息电位"]},
    {"question": "炎症和感染有什么关系？", "expected_terms": ["感染", "炎症"]},
    {"question": "抗原和抗体有什么关系？", "expected_terms": ["抗原", "抗体"]},
    {"question": "细胞和组织是什么关系？", "expected_terms": ["细胞", "组织"]},
    {"question": "神经系统和肌肉有什么关系？", "expected_terms": ["神经系统", "肌肉"]},
    {"question": "为什么膜电位变化会影响传导？", "expected_terms": ["膜电位", "神经传导"]},
    {"question": "为什么感染会引起炎症？", "expected_terms": ["感染", "炎症"]},
    {"question": "学习动作电位前要先学什么？", "expected_terms": ["静息电位", "基础"]},
    {"question": "火星土壤采样器是什么？", "expected_terms": [], "expect_no_answer": True},
    {"question": "量子芯片退火温度是多少？", "expected_terms": [], "expect_no_answer": True},
]


def main() -> None:
    settings.parsed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.index_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    index_path = settings.index_data_dir / "rag_index.json"
    old_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None

    try:
        with TemporaryDirectory() as tmp:
            sample = Path(tmp) / "stage4_benchmark.md"
            sample.write_text(_benchmark_text(), encoding="utf-8")
            parsed, _ = parse_uploaded_file(sample, sample.name)

            client = TestClient(app)
            index = client.post("/api/rag/index", json={"raw_file_ids": [parsed.raw_file.id], "force_rebuild": True})
            assert index.status_code == 200, index.text

            results = [_run_question(client, parsed.raw_file.id, item) for item in QUESTIONS]
            answerable = [item for item in results if not item["expect_no_answer"]]
            no_answer = [item for item in results if item["expect_no_answer"]]
            report = {
                "benchmark": "00_stage4_rag",
                "question_count": len(results),
                "answerable_count": len(answerable),
                "no_answer_count": len(no_answer),
                "top5_term_hit_rate": _ratio(sum(1 for item in answerable if item["hit"]), len(answerable)),
                "no_answer_rejection_rate": _ratio(sum(1 for item in no_answer if item["hit"]), len(no_answer)),
                "average_response_ms": round(statistics.mean(item["elapsed_ms"] for item in results), 2),
                "retrieval": results[0]["retrieval"] if results else None,
                "results": results,
            }
            output_path = settings.index_data_dir / "stage4_rag_benchmark_latest.json"
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    finally:
        for path in settings.parsed_data_dir.glob("raw_*.json"):
            if path not in before_parsed:
                path.unlink(missing_ok=True)
        if old_index is None:
            index_path.unlink(missing_ok=True)
        else:
            index_path.write_text(old_index, encoding="utf-8")


def _run_question(client: TestClient, raw_file_id: str, item: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.post(
        "/api/rag/query",
        json={"question": item["question"], "top_k": 5, "raw_file_ids": [raw_file_id]},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    payload = response.json()
    answer = payload["answer"]
    expect_no_answer = bool(item.get("expect_no_answer"))
    if expect_no_answer:
        hit = answer == NO_ANSWER
    else:
        combined = answer + "\n" + "\n".join(citation["quote"] for citation in payload["citations"])
        hit = all(term in combined for term in item["expected_terms"])
    return {
        "question": item["question"],
        "expected_terms": item["expected_terms"],
        "expect_no_answer": expect_no_answer,
        "hit": hit,
        "citation_count": len(payload["citations"]),
        "elapsed_ms": round(elapsed_ms, 2),
        "answer": answer,
        "retrieval": payload.get("metadata", {}).get("retrieval"),
    }


def _benchmark_text() -> str:
    return """# 第一章 神经调节
动作电位是细胞受到刺激后膜电位快速变化的过程。静息电位是动作电位发生的基础。神经传导常依赖动作电位沿细胞膜传播。膜电位变化会影响神经传导速度。

# 第二章 炎症与免疫
炎症是机体对损伤因子产生的防御性反应。感染可以引起炎症，炎症过程中白细胞参与免疫防御。抗原能够刺激机体产生免疫应答，抗体可以特异性结合抗原。

# 第三章 细胞与组织
细胞膜结构具有选择通透性，能够维持细胞内外环境差异。多个形态和功能相似的细胞以及细胞间质构成组织。神经系统可以通过神经冲动调节肌肉收缩。

# 第四章 生理调节
酶反应受温度、pH 和底物浓度影响。血管收缩可使外周阻力增加并升高血压。淋巴系统由淋巴管、淋巴结和淋巴器官组成，参与体液回流和免疫防御。
"""


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


if __name__ == "__main__":
    main()
