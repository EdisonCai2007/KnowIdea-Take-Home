from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from ..settings import OpenRouterSettings


@dataclass(frozen=True, slots=True)
class OpenRouterCompletion:
    raw_provider_response: str
    provider_response_json: dict[str, Any] | None
    raw_model_response: str
    response_id: str | None = None
    response_model: str | None = None
    provider: str | None = None
    system_fingerprint: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    openrouter_metadata: dict[str, Any] | None = None
    http_status: int | None = None


class OpenRouterError(RuntimeError):
    """Raised when the OpenRouter API cannot produce a usable response."""

    def __init__(
        self,
        message: str,
        *,
        raw_provider_response: str | None = None,
        provider_response_json: dict[str, Any] | None = None,
        raw_model_response: str | None = None,
        response_id: str | None = None,
        response_model: str | None = None,
        provider: str | None = None,
        system_fingerprint: str | None = None,
        finish_reason: str | None = None,
        native_finish_reason: str | None = None,
        usage: dict[str, Any] | None = None,
        openrouter_metadata: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_provider_response = raw_provider_response
        self.provider_response_json = provider_response_json
        self.raw_model_response = raw_model_response
        self.response_id = response_id
        self.response_model = response_model
        self.provider = provider
        self.system_fingerprint = system_fingerprint
        self.finish_reason = finish_reason
        self.native_finish_reason = native_finish_reason
        self.usage = usage
        self.openrouter_metadata = openrouter_metadata
        self.http_status = http_status


class OpenRouterClient:
    def __init__(self, settings: OpenRouterSettings) -> None:
        self._settings = settings

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, Any],
    ) -> OpenRouterCompletion:
        if self._settings.api_key is None:
            raise OpenRouterError("OpenRouter API key is missing.")

        payload = {
            "model": self._settings.model,
            "messages": messages,
            "temperature": 0,
            "response_format": response_format,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                f"{self._settings.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc}") from exc

        raw_provider_response = response.text
        data = _try_parse_json(raw_provider_response)
        metadata = _extract_response_metadata(data)

        if response.status_code >= 400:
            snippet = response.text.strip()
            if len(snippet) > 240:
                snippet = f"{snippet[:237]}..."
            raise OpenRouterError(
                f"OpenRouter request failed with status {response.status_code}: {snippet}",
                raw_provider_response=raw_provider_response,
                provider_response_json=data,
                raw_model_response=metadata["raw_model_response"],
                response_id=metadata["response_id"],
                response_model=metadata["response_model"],
                provider=metadata["provider"],
                system_fingerprint=metadata["system_fingerprint"],
                finish_reason=metadata["finish_reason"],
                native_finish_reason=metadata["native_finish_reason"],
                usage=metadata["usage"],
                openrouter_metadata=metadata["openrouter_metadata"],
                http_status=response.status_code,
            )

        if data is None:
            raise OpenRouterError(
                "OpenRouter response was not valid JSON.",
                raw_provider_response=raw_provider_response,
                provider_response_json=None,
                http_status=response.status_code,
            )

        raw_model_response = metadata["raw_model_response"]
        if raw_model_response is None:
            raise OpenRouterError(
                "OpenRouter response did not contain a chat completion message.",
                raw_provider_response=raw_provider_response,
                provider_response_json=data,
                response_id=metadata["response_id"],
                response_model=metadata["response_model"],
                provider=metadata["provider"],
                system_fingerprint=metadata["system_fingerprint"],
                finish_reason=metadata["finish_reason"],
                native_finish_reason=metadata["native_finish_reason"],
                usage=metadata["usage"],
                openrouter_metadata=metadata["openrouter_metadata"],
                http_status=response.status_code,
            )

        return OpenRouterCompletion(
            raw_provider_response=raw_provider_response,
            provider_response_json=data,
            raw_model_response=raw_model_response,
            response_id=metadata["response_id"],
            response_model=metadata["response_model"],
            provider=metadata["provider"],
            system_fingerprint=metadata["system_fingerprint"],
            finish_reason=metadata["finish_reason"],
            native_finish_reason=metadata["native_finish_reason"],
            usage=metadata["usage"],
            openrouter_metadata=metadata["openrouter_metadata"],
            http_status=response.status_code,
        )


def _try_parse_json(raw_provider_response: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_provider_response)
    except ValueError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _extract_response_metadata(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "raw_model_response": None,
            "response_id": None,
            "response_model": None,
            "provider": None,
            "system_fingerprint": None,
            "finish_reason": None,
            "native_finish_reason": None,
            "usage": None,
            "openrouter_metadata": None,
        }

    choice: dict[str, Any] | None = None
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]

    raw_model_response: str | None = None
    if isinstance(choice, dict):
        message = choice.get("message")
        if isinstance(message, dict) and "content" in message:
            try:
                raw_model_response = _coerce_content(message["content"])
            except OpenRouterError:
                raw_model_response = None

    usage = data.get("usage")
    openrouter_metadata = data.get("openrouter_metadata")

    return {
        "raw_model_response": raw_model_response,
        "response_id": _coerce_optional_str(data.get("id")),
        "response_model": _coerce_optional_str(data.get("model")),
        "provider": _coerce_optional_str(data.get("provider")),
        "system_fingerprint": _coerce_optional_str(data.get("system_fingerprint")),
        "finish_reason": _coerce_optional_str(choice.get("finish_reason")) if choice else None,
        "native_finish_reason": _coerce_optional_str(choice.get("native_finish_reason"))
        if choice
        else None,
        "usage": usage if isinstance(usage, dict) else None,
        "openrouter_metadata": openrouter_metadata if isinstance(openrouter_metadata, dict) else None,
    }


def _coerce_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _coerce_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)

    raise OpenRouterError("OpenRouter completion content was not plain text.")
