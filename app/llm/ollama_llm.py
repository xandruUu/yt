from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from app.llm.base import LLMProviderStatus, LLMProviderUnavailable


class OllamaLLMProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: int = 45,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.enabled = enabled if enabled is not None else _env_bool("ENABLE_OLLAMA", False)
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            with request.urlopen(f"{self.base_url}/api/tags", timeout=1):
                return True
        except (error.URLError, TimeoutError):
            return False

    def status(self) -> LLMProviderStatus:
        if not self.enabled:
            return LLMProviderStatus(self.name, False, "Desactivado por ENABLE_OLLAMA=false.")
        if not self.is_available():
            return LLMProviderStatus(self.name, False, "Ollama no responde en OLLAMA_BASE_URL.")
        return LLMProviderStatus(self.name, True, f"Listo con modelo local {self.model}.")

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.is_available():
            raise LLMProviderUnavailable(self.status().detail)
        body = json.dumps(
            {
                "model": self.model,
                "prompt": f"{system_prompt.strip()}\n\n{user_prompt.strip()}",
                "stream": False,
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError) as exc:
            raise LLMProviderUnavailable(f"No se pudo conectar con Ollama: {exc}") from exc
        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Ollama no devolvio texto utilizable.")
        return text.strip()

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str | None = None,
    ) -> dict[str, object] | list[object]:
        text = self.generate_text(
            system_prompt,
            f"{user_prompt}\n\nDevuelve solo JSON valido para el esquema: {schema_name or 'json'}.",
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama devolvio texto que no es JSON valido.") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
