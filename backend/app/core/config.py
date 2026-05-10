from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "学科知识整合智能体"
    api_prefix: str = "/api"
    converted_textbooks_dir: Path = PROJECT_ROOT / "materials" / "converted_textbooks"
    parsed_data_dir: Path = PROJECT_ROOT / "data" / "parsed"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    upload_sessions_dir: Path = PROJECT_ROOT / "data" / "uploads" / "sessions"
    job_data_dir: Path = PROJECT_ROOT / "data" / "jobs"
    graph_data_dir: Path = PROJECT_ROOT / "data" / "graphs"
    llm_cache_dir: Path = PROJECT_ROOT / "data" / "graphs" / "llm_cache"
    llm_provider: str = "none"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def resolve_paths(self) -> "Settings":
        self.converted_textbooks_dir = self._resolve_path(self.converted_textbooks_dir)
        self.parsed_data_dir = self._resolve_path(self.parsed_data_dir)
        self.upload_dir = self._resolve_path(self.upload_dir)
        self.upload_sessions_dir = self._resolve_path(self.upload_sessions_dir)
        self.job_data_dir = self._resolve_path(self.job_data_dir)
        self.graph_data_dir = self._resolve_path(self.graph_data_dir)
        self.llm_cache_dir = self._resolve_path(self.llm_cache_dir)
        return self

    @staticmethod
    def _resolve_path(path: Path) -> Path:
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path


settings = Settings().resolve_paths()
