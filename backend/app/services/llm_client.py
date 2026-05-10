from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings


class LlmClient:
    def is_enabled(self) -> bool:
        return settings.llm_provider.lower() == "openai" and bool(settings.openai_api_key)

    def extract_json(self, prompt: str) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None
        response = httpx.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": "你是严格输出 JSON 的教材知识图谱抽取器。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return json.loads(content)


llm_client = LlmClient()
