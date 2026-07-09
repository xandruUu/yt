from __future__ import annotations

from pydantic import BaseModel

from app.ai.ollama_client import OllamaClient, OllamaResult
from app.config.settings import get_settings


class LLMGateway:
    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        self.settings = get_settings()
        self.ollama_client = ollama_client or OllamaClient()

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        temperature: float,
    ) -> OllamaResult:
        if self.settings.enable_ollama or self.settings.default_llm_provider == "ollama":
            return self.ollama_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                temperature=temperature,
            )
        return OllamaResult(ok=False, error_message="LLM automatico desactivado; usando fallback local.")

