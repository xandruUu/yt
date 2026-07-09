from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config.settings import get_settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class OllamaResult:
    ok: bool
    data: BaseModel | None = None
    raw_response: str = ""
    error_message: str | None = None


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout_seconds = settings.ollama_timeout_seconds
        self.num_ctx = settings.ollama_num_ctx

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        temperature: float,
    ) -> OllamaResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as exc:
            return OllamaResult(ok=False, error_message=f"Ollama no disponible: {exc}")

        try:
            decoded = json.loads(raw)
            content = decoded.get("message", {}).get("content") or raw
            data = schema.model_validate_json(content)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            return OllamaResult(ok=False, raw_response=raw, error_message=f"JSON invalido de Ollama: {exc}")

        return OllamaResult(ok=True, data=data, raw_response=raw)


def compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

