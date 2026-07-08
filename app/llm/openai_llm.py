from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from app.llm.base import LLMProviderStatus, LLMProviderUnavailable


class OpenAILLMProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: int = 45,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_TEXT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.enabled = enabled if enabled is not None else _env_bool("ENABLE_OPENAI_LLM", False)
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.enabled and self.api_key)

    def status(self) -> LLMProviderStatus:
        if not self.enabled:
            return LLMProviderStatus(self.name, False, "Desactivado por ENABLE_OPENAI_LLM=false.", paid=True)
        if not self.api_key:
            return LLMProviderStatus(self.name, False, "Falta OPENAI_API_KEY.", paid=True)
        return LLMProviderStatus(self.name, True, f"Listo con modelo {self.model}.", paid=True)

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        payload = self._request(system_prompt, user_prompt)
        return _extract_text(payload)

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str | None = None,
    ) -> dict[str, object] | list[object]:
        text = self.generate_text(
            system_prompt,
            f"{user_prompt}\n\nDevuelve JSON valido para el esquema: {schema_name or 'json'}.",
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI devolvio texto que no es JSON valido.") from exc

    def _request(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.is_available():
            raise LLMProviderUnavailable(self.status().detail)

        body = json.dumps(
            {
                "model": self.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        ).encode("utf-8")
        req = request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError) as exc:
            raise LLMProviderUnavailable(f"No se pudo conectar con OpenAI: {exc}") from exc


def _extract_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    if chunks:
        return "\n".join(chunks)
    raise ValueError("OpenAI no devolvio texto utilizable.")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
