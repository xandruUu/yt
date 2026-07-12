from __future__ import annotations

import importlib
import json

from app.config.settings import get_settings
from app.core import enums
from app.ui.dashboard import PAGES, build_pages


def test_dashboard_pages_import_without_missing_symbols() -> None:
    imported_modules = []

    for page in PAGES:
        if page.module == "home":
            continue
        module = importlib.import_module(f"app.ui.pages.{page.module}")
        imported_modules.append(page.module)
        assert callable(getattr(module, "render", None))

    assert "09_trend_research" in imported_modules
    assert "18_production" in imported_modules
    assert "08_settings" in imported_modules


def test_legacy_pages_can_be_enabled() -> None:
    labels = [page.label for page in build_pages(show_legacy_modules=True)]

    assert "Crear Short paso a paso" in labels
    assert "Voces" in labels
    assert "Herramientas externas" in labels


def test_build_pages_without_legacy_excludes_legacy() -> None:
    labels = [page.label for page in build_pages(show_legacy_modules=False)]

    assert "Produccion" in labels
    assert "Herramientas externas" not in labels
    assert "Storyboard Nero" not in labels


def test_build_pages_with_legacy_includes_legacy() -> None:
    labels = [page.label for page in build_pages(show_legacy_modules=True)]

    assert "Herramientas externas" in labels
    assert "Storyboard Nero" in labels


def test_required_stabilization_enums_exist() -> None:
    assert enums.GeneratedIdeaStatus.SUGGESTED.value == "suggested"
    assert enums.VoiceoverJobStatus.PENDING.value == "pending"
    assert enums.ExternalToolJobStatus.CONFIRMATION_REQUIRED.value == "confirmation_required"
    assert enums.ExternalToolJobStatus.CANCELLED.value == "cancelled"
    assert enums.PromptPackStatus.DRAFT.value == "draft"
    assert enums.ExternalAssetStatus.USED_IN_RENDER.value == "used_in_render"
    assert enums.LicenseReviewStatus.NEEDS_CHANGES.value == "needs_changes"
    assert enums.CostEventStatus.ESTIMATED.value == "estimated"


def test_settings_safe_defaults_without_optional_env(monkeypatch) -> None:
    optional_env_keys = [
        "DEFAULT_LLM_PROVIDER",
        "SHOW_LEGACY_MODULES",
        "DATABASE_SCHEMA",
        "DEFAULT_TTS_PROVIDER",
        "ENABLE_AUTO_LLM",
        "ENABLE_OPENAI_LLM",
        "ENABLE_OPENAI_TTS",
        "ENABLE_OLLAMA",
        "ENABLE_LOCAL_TTS",
        "ENABLE_ELEVENLABS_TTS",
        "ENABLE_EXTERNAL_TOOLS",
        "DEFAULT_EXTERNAL_MODE",
        "ENABLE_ELEVENLABS",
        "ENABLE_HIGGSFIELD_MANUAL",
        "ENABLE_HIGGSFIELD_MCP",
        "ENABLE_PICSART_MANUAL",
        "ENABLE_PICSART_API",
        "REQUIRE_CONFIRMATION_FOR_PAID_TOOLS",
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
        "PICSART_API_KEY",
        "HIGGSFIELD_API_KEY",
    ]
    for key in optional_env_keys:
        monkeypatch.delenv(key, raising=False)

    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.default_llm_provider == "manual"
        assert settings.show_legacy_modules is False
        assert settings.database_schema == ""
        assert settings.default_tts_provider == "manual"
        assert settings.enable_external_tools is True
        assert settings.default_external_mode == "manual"
        assert settings.enable_elevenlabs is False
        assert settings.require_confirmation_for_paid_tools is True
    finally:
        get_settings.cache_clear()


def test_settings_page_masks_api_keys() -> None:
    settings_page = importlib.import_module("app.ui.pages.08_settings")
    secret = "sk-test-secret-value"
    masked_payload = {
        "long": settings_page._mask_secret(secret),
        "short": settings_page._mask_secret("abc123"),
        "missing": settings_page._mask_secret(None),
    }

    dumped = json.dumps(masked_payload)
    assert secret not in dumped
    assert masked_payload["long"] == "sk-t...alue"
    assert masked_payload["short"] == "***"
    assert masked_payload["missing"] == "no configurada"
