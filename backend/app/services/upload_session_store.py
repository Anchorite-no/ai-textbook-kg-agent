from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.models.schemas import (
    UploadSessionCreateRequest,
    UploadSessionRecord,
    UploadSessionStatus,
)


SESSION_FILE = "session.json"


class UploadSessionStore:
    def create(self, payload: UploadSessionCreateRequest) -> UploadSessionRecord:
        session_id = f"upload_session_{uuid4().hex[:16]}"
        session = UploadSessionRecord(
            id=session_id,
            filename=Path(payload.filename).name,
            total_size_bytes=payload.total_size_bytes,
            total_chunks=payload.total_chunks,
            chunk_size_bytes=payload.chunk_size_bytes,
            sha256=payload.sha256,
            content_type=payload.content_type,
            parse_on_complete=payload.parse_on_complete,
            missing_chunks=list(range(payload.total_chunks)),
        )
        self.save(session)
        return session

    def get(self, session_id: str) -> UploadSessionRecord | None:
        path = self._session_file(session_id)
        if not path.exists():
            return None
        return UploadSessionRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, session: UploadSessionRecord) -> UploadSessionRecord:
        self._session_dir(session.id).mkdir(parents=True, exist_ok=True)
        updated = session.model_copy(update={"updated_at": datetime.utcnow()})
        self._session_file(session.id).write_text(
            json.dumps(updated.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated

    def write_chunk(self, session: UploadSessionRecord, chunk_index: int, content: bytes) -> UploadSessionRecord:
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise ValueError(f"chunk_index must be between 0 and {session.total_chunks - 1}")
        if not content:
            raise ValueError("chunk content is empty")
        if len(content) > session.chunk_size_bytes:
            raise ValueError("chunk content exceeds configured chunk_size_bytes")
        if chunk_index < session.total_chunks - 1 and len(content) != session.chunk_size_bytes:
            raise ValueError("non-final chunk size must equal chunk_size_bytes")

        chunk_path = self._chunk_path(session.id, chunk_index)
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_bytes(content)
        return self.refresh_progress(session.model_copy(update={"status": UploadSessionStatus.uploading, "error": None}))

    def refresh_progress(self, session: UploadSessionRecord) -> UploadSessionRecord:
        uploaded_chunks = self.uploaded_chunk_indexes(session.id)
        received_bytes = sum(self._chunk_path(session.id, index).stat().st_size for index in uploaded_chunks)
        missing_chunks = [index for index in range(session.total_chunks) if index not in set(uploaded_chunks)]
        progress = min(100, int(received_bytes / session.total_size_bytes * 100))
        if not missing_chunks and received_bytes == session.total_size_bytes:
            progress = 100
        updated = session.model_copy(
            update={
                "uploaded_chunks": uploaded_chunks,
                "missing_chunks": missing_chunks,
                "received_bytes": received_bytes,
                "upload_progress": progress,
            }
        )
        return self.save(updated)

    def uploaded_chunk_indexes(self, session_id: str) -> list[int]:
        chunks_dir = self._chunks_dir(session_id)
        if not chunks_dir.exists():
            return []
        indexes: list[int] = []
        for path in chunks_dir.glob("chunk_*.part"):
            try:
                indexes.append(int(path.stem.removeprefix("chunk_")))
            except ValueError:
                continue
        return sorted(indexes)

    def assemble(self, session: UploadSessionRecord) -> tuple[UploadSessionRecord, Path]:
        session = self.refresh_progress(session)
        if session.missing_chunks:
            raise ValueError(f"missing chunks: {session.missing_chunks}")
        if session.received_bytes != session.total_size_bytes:
            raise ValueError(f"received bytes mismatch: {session.received_bytes} != {session.total_size_bytes}")

        assembling = self.save(session.model_copy(update={"status": UploadSessionStatus.assembling, "error": None}))
        digest = hashlib.sha256()
        suffix = Path(assembling.filename).suffix
        temp_path = settings.upload_dir / f"{assembling.id}{suffix}.assembling"
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        with temp_path.open("wb") as output:
            for index in range(assembling.total_chunks):
                chunk_path = self._chunk_path(assembling.id, index)
                with chunk_path.open("rb") as chunk:
                    for block in iter(lambda: chunk.read(1024 * 1024), b""):
                        digest.update(block)
                        output.write(block)

        actual_sha256 = digest.hexdigest()
        if assembling.sha256 and actual_sha256.lower() != assembling.sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise ValueError("assembled file sha256 mismatch")

        final_path = settings.upload_dir / f"upload_{actual_sha256[:16]}{suffix}"
        if final_path.exists():
            final_path.unlink()
        shutil.move(str(temp_path), final_path)
        completed = self.save(assembling.model_copy(update={"assembled_path": str(final_path)}))
        return completed, final_path

    def fail(self, session: UploadSessionRecord, error: str) -> UploadSessionRecord:
        return self.save(session.model_copy(update={"status": UploadSessionStatus.failed, "error": error}))

    def mark_parsing(self, session: UploadSessionRecord, job_id: str) -> UploadSessionRecord:
        return self.save(session.model_copy(update={"status": UploadSessionStatus.parsing, "job_id": job_id, "parse_progress": 10}))

    def mark_completed(
        self,
        session: UploadSessionRecord,
        raw_file_id: str | None,
        parsed_output_path: str | None,
    ) -> UploadSessionRecord:
        return self.save(
            session.model_copy(
                update={
                    "status": UploadSessionStatus.completed,
                    "raw_file_id": raw_file_id,
                    "parsed_output_path": parsed_output_path,
                    "parse_progress": 100,
                    "error": None,
                }
            )
        )

    def _session_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / SESSION_FILE

    def _session_dir(self, session_id: str) -> Path:
        return settings.upload_sessions_dir / session_id

    def _chunks_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "chunks"

    def _chunk_path(self, session_id: str, chunk_index: int) -> Path:
        return self._chunks_dir(session_id) / f"chunk_{chunk_index:06d}.part"


upload_session_store = UploadSessionStore()
