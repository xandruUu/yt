from __future__ import annotations

from app.config.settings import get_settings
from app.llm.base import LLMProvider, LLMProviderStatus
from app.llm.manual_llm import ManualLLMProvider
from app.llm.ollama_llm import OllamaLLMProvider
from app.llm.openai_llm import OpenAILLMProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    settings = get_settings()
    selected = (provider_name or settings.default_llm_provider or "manual").lower()
    providers = _provider_registry()
    return providers.get(selected, providers["manual"])


def list_llm_provider_statuses() -> list[LLMProviderStatus]:
    return [provider.status() for provider in _provider_registry().values()]


def _provider_registry() -> dict[str, LLMProvider]:
    settings = get_settings()
    return {
        "manual": ManualLLMProvider(),
        "openai": OpenAILLMProvider(
            model=settings.openai_text_model,
            enabled=settings.enable_openai_llm,
        ),
        "ollama": OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            enabled=settings.enable_ollama,
        ),
    }
