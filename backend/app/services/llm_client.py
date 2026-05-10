from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings


class LlmClient:
    def is_enabled(self) -> bool:
        return settings.llm_provider.lower() in {"openai", "openai-compatible", "openai_compatible", "deepseek", "qwen"} and bool(
            settings.openai_api_key
        )

    def extract_json(self, prompt: str) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None
        request_payload: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": "你是严格输出 JSON 的教材知识图谱抽取器。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": settings.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._post_chat_completion(request_payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {400, 404, 422}:
                raise
            # Some OpenAI-compatible providers still reject response_format. Retry once
            # without it while keeping the prompt-side JSON constraint.
            request_payload.pop("response_format", None)
            response = self._post_chat_completion(request_payload)
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return parse_llm_json(content)

    def _post_chat_completion(self, payload: dict[str, Any]) -> httpx.Response:
        response = httpx.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response


def parse_llm_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM output must be a JSON object")
    return payload


llm_client = LlmClient()
