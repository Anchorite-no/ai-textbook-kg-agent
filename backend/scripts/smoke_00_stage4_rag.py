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
    settings.index_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    index_path = settings.index_data_dir / "rag_index.json"
    old_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None

    try:
        with TemporaryDirectory() as tmp:
            sample = Path(tmp) / "rag_sample.md"
            sample.write_text(
                "# 第一章 膜电位\n"
                "动作电位是细胞受到刺激后膜电位快速变化的过程。"
                "静息电位是动作电位发生的基础。"
                "神经传导常依赖动作电位沿细胞膜传播。\n",
                encoding="utf-8",
            )
            parsed, _ = parse_uploaded_file(sample, sample.name)

            client = TestClient(app)
            index = client.post(
                "/api/rag/index",
                json={"raw_file_ids": [parsed.raw_file.id], "force_rebuild": True},
            )
            assert index.status_code == 200, index.text
            index_payload = index.json()
            assert index_payload["job"]["status"] == "completed", index_payload
            assert index_payload["status"]["chunk_count"] >= 1, index_payload

            status = client.get("/api/rag/status")
            assert status.status_code == 200, status.text
            assert status.json()["status"] == "ready", status.text

            query = client.post(
                "/api/rag/query",
                json={"question": "动作电位是什么", "top_k": 3, "raw_file_ids": [parsed.raw_file.id]},
            )
            assert query.status_code == 200, query.text
            query_payload = query.json()
            assert query_payload["citations"], query_payload
            assert query_payload["source_chunks"], query_payload
            assert "动作电位" in query_payload["answer"], query_payload
            assert query_payload["citations"][0]["source_locator"]["raw_file_id"] == parsed.raw_file.id

            miss = client.post("/api/rag/query", json={"question": "火星土壤采样器", "top_k": 3})
            assert miss.status_code == 200, miss.text
            assert miss.json()["answer"] == "当前知识库中未找到相关信息。", miss.text
    finally:
        for path in settings.parsed_data_dir.glob("raw_*.json"):
            if path not in before_parsed:
                path.unlink(missing_ok=True)
        if old_index is None:
            index_path.unlink(missing_ok=True)
        else:
            index_path.write_text(old_index, encoding="utf-8")

    print("00 stage4 rag smoke ok")


if __name__ == "__main__":
    main()
