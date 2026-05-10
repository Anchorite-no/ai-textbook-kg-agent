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
        style = settings.llm_api_style.lower().replace("_", "-")
        if style in {"responses", "response", "auto"}:
            try:
                response = self._post_response(_responses_payload(prompt))
                return parse_llm_json(_extract_responses_text(response.json()))
            except httpx.HTTPStatusError as exc:
                if style not in {"auto"} and exc.response.status_code not in {400, 404, 422}:
                    raise
                if style not in {"auto", "responses", "response"}:
                    raise
            except Exception:
                if style not in {"auto", "responses", "response"}:
                    raise

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

    def _post_response(self, payload: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for url in _responses_urls(settings.openai_base_url):
            try:
                response = httpx.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                if _looks_like_json_response(response):
                    return response
                last_error = ValueError(f"LLM endpoint returned non-JSON response from {url}")
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:  # noqa: BLE001 - try the next compatible endpoint.
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise ValueError("No LLM responses endpoint configured")

    def _post_chat_completion(self, payload: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for url in _chat_completion_urls(settings.openai_base_url):
            try:
                response = httpx.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                if _looks_like_json_response(response):
                    return response
                last_error = ValueError(f"LLM endpoint returned non-JSON response from {url}")
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:  # noqa: BLE001 - try the next compatible endpoint.
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise ValueError("No LLM chat completion endpoint configured")


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


def _responses_payload(prompt: str) -> dict[str, Any]:
    return {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": "你是严格输出 JSON 的教材知识图谱抽取器。"},
            {"role": "user", "content": prompt},
        ],
        "max_output_tokens": settings.llm_max_tokens,
    }


def _extract_responses_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    joined = "".join(parts).strip()
    if not joined:
        raise ValueError("Responses API output did not include text content")
    return joined


def _responses_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return [f"{base}/responses"]
    return [f"{base}/v1/responses", f"{base}/responses"]


def _chat_completion_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return [f"{base}/chat/completions"]
    return [f"{base}/v1/chat/completions", f"{base}/chat/completions"]


def _looks_like_json_response(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    text = response.text.lstrip()
    return "json" in content_type or text.startswith("{")
