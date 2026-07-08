from __future__ import annotations

import pytest

from app.llm.base import LLMProviderUnavailable
from app.llm.manual_llm import ManualLLMProvider
from app.llm.ollama_llm import OllamaLLMProvider
from app.llm.openai_llm import OpenAILLMProvider


def test_manual_llm_provider_is_always_available() -> None:
    provider = ManualLLMProvider()

    assert provider.is_available()
    assert provider.status().available
    assert "# Sistema" in provider.generate_text("Sistema", "Usuario")


def test_manual_llm_generate_json_returns_copy_prompt() -> None:
    provider = ManualLLMProvider()
    payload = provider.generate_json("Sistema", "Usuario", schema_name="hooks")

    assert payload["provider"] == "manual"
    assert payload["schema_name"] == "hooks"
    assert "Usuario" in str(payload["prompt"])


def test_openai_provider_degrades_without_api_key() -> None:
    provider = OpenAILLMProvider(api_key="", enabled=True)

    assert not provider.is_available()
    assert "OPENAI_API_KEY" in provider.status().detail
    with pytest.raises(LLMProviderUnavailable):
        provider.generate_text("Sistema", "Usuario")


def test_ollama_provider_degrades_when_disabled() -> None:
    provider = OllamaLLMProvider(enabled=False)

    assert not provider.is_available()
    assert "ENABLE_OLLAMA" in provider.status().detail
