from __future__ import annotations

import hashlib
import sys
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    settings.parsed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.job_data_dir.mkdir(parents=True, exist_ok=True)
    before_parsed = set(settings.parsed_data_dir.glob("raw_*.json"))
    before_uploads = set(settings.upload_dir.glob("upload_*"))
    before_sessions = set(settings.upload_sessions_dir.glob("upload_session_*"))
    before_jobs = set(settings.job_data_dir.glob("job_pipeline_*.json"))

    try:
        with TemporaryDirectory() as tmp:
            sample_dir = Path(tmp)
            client = TestClient(app)
            run_async_upload_smoke(client, sample_dir)
            run_async_retry_smoke(client, sample_dir)
            run_chunk_complete_async_smoke(client)
    finally:
        cleanup_files(settings.parsed_data_dir.glob("raw_*.json"), before_parsed)
        cleanup_files(settings.upload_dir.glob("upload_*"), before_uploads)
        cleanup_dirs(settings.upload_sessions_dir.glob("upload_session_*"), before_sessions)
        cleanup_files(settings.job_data_dir.glob("job_pipeline_*.json"), before_jobs)

    print("00 stage3 async smoke ok")


def run_async_upload_smoke(client: TestClient, sample_dir: Path) -> None:
    sample = sample_dir / "async_sample.md"
    sample.write_text("# 第一章 异步解析\n动作电位是静息电位的基础应用示例。", encoding="utf-8")
    with sample.open("rb") as handle:
        response = client.post(
            "/api/textbooks/upload-async",
            files={"file": ("async_sample.md", handle, "text/markdown")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    job = payload["job"]
    job_id = job["id"]
    assert job["job_type"] == "textbook_pipeline", job

    job_response = client.get(f"/api/jobs/{job_id}")
    assert job_response.status_code == 200, job_response.text
    completed = job_response.json()
    assert completed["status"] == "completed", completed
    assert completed["result"]["raw_file_id"].startswith("raw_"), completed
    assert [step["name"] for step in completed["steps"]] == [
        "detect_format",
        "parse_elements",
        "build_sections",
        "chunk_sections",
        "persist_parsed",
    ]
    assert all(step["status"] == "completed" for step in completed["steps"]), completed


def run_async_retry_smoke(client: TestClient, sample_dir: Path) -> None:
    unsupported = sample_dir / "legacy.doc"
    unsupported.write_text("legacy office placeholder", encoding="utf-8")
    with unsupported.open("rb") as handle:
        response = client.post(
            "/api/textbooks/upload-async",
            files={"file": ("legacy.doc", handle, "application/msword")},
        )
    assert response.status_code == 200, response.text
    job_id = response.json()["job"]["id"]

    failed = client.get(f"/api/jobs/{job_id}")
    assert failed.status_code == 200, failed.text
    failed_payload = failed.json()
    assert failed_payload["status"] == "failed", failed_payload
    assert failed_payload["retryable"] is True, failed_payload
    assert any(step["status"] == "failed" for step in failed_payload["steps"]), failed_payload

    retry = client.post(f"/api/jobs/{job_id}/retry")
    assert retry.status_code == 200, retry.text
    retried = client.get(f"/api/jobs/{job_id}")
    assert retried.status_code == 200, retried.text
    retried_payload = retried.json()
    assert retried_payload["status"] == "failed", retried_payload
    assert retried_payload["retryable"] is True, retried_payload


def run_chunk_complete_async_smoke(client: TestClient) -> None:
    content = "# 第一章 分片异步\n静息电位是动作电位的基础。\n".encode("utf-8")
    chunk_size = 16
    chunks = [content[index : index + chunk_size] for index in range(0, len(content), chunk_size)]
    create = client.post(
        "/api/uploads/sessions",
        json={
            "filename": "chunk_async.md",
            "total_size_bytes": len(content),
            "total_chunks": len(chunks),
            "chunk_size_bytes": chunk_size,
            "sha256": hashlib.sha256(content).hexdigest(),
            "content_type": "text/markdown",
            "parse_on_complete": True,
        },
    )
    assert create.status_code == 200, create.text
    session_id = create.json()["id"]
    for index, chunk in enumerate(chunks):
        uploaded = client.put(
            f"/api/uploads/sessions/{session_id}/chunks/{index}",
            files={"file": (f"chunk_{index}.part", chunk, "application/octet-stream")},
        )
        assert uploaded.status_code == 200, uploaded.text

    complete = client.post(f"/api/uploads/sessions/{session_id}/complete-async")
    assert complete.status_code == 200, complete.text
    job_id = complete.json()["job"]["id"]

    job = client.get(f"/api/jobs/{job_id}")
    assert job.status_code == 200, job.text
    job_payload = job.json()
    assert job_payload["status"] == "completed", job_payload
    assert job_payload["steps"][0]["name"] == "assemble_file", job_payload

    session = client.get(f"/api/uploads/sessions/{session_id}")
    assert session.status_code == 200, session.text
    session_payload = session.json()
    assert session_payload["status"] == "completed", session_payload
    assert session_payload["raw_file_id"] == job_payload["result"]["raw_file_id"], session_payload


def cleanup_files(paths: Iterable[Path], before: set[Path]) -> None:
    for path in paths:
        if path in before:
            continue
        path.unlink(missing_ok=True)


def cleanup_dirs(paths: Iterable[Path], before: set[Path]) -> None:
    import shutil

    for path in paths:
        if path in before:
            continue
        shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()
