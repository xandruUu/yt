from __future__ import annotations

from app.external_tools.base import ExternalToolProvider
from app.external_tools.elevenlabs.provider import ElevenLabsProvider
from app.external_tools.generic.manual_handoff import GenericManualToolProvider
from app.external_tools.higgsfield.mcp_provider import HiggsfieldMCPProvider
from app.external_tools.higgsfield.prompt_pack import HiggsfieldManualProvider
from app.external_tools.picsart.prompt_pack import PicsartManualProvider
from app.external_tools.picsart.video_provider import PicsartAPIProvider


class ExternalToolRegistry:
    def __init__(self, providers: list[ExternalToolProvider] | None = None) -> None:
        self._providers = providers or [
            ElevenLabsProvider(),
            HiggsfieldManualProvider(),
            HiggsfieldMCPProvider(),
            PicsartManualProvider(),
            PicsartAPIProvider(),
            GenericManualToolProvider(),
        ]

    def list_providers(self) -> list[ExternalToolProvider]:
        return list(self._providers)

    def get_provider(self, name: str) -> ExternalToolProvider:
        for provider in self._providers:
            if provider.name == name:
                return provider
        raise ValueError(f"Unknown external tool provider: {name}")

    def list_available(self) -> list[ExternalToolProvider]:
        return [provider for provider in self._providers if provider.is_available()]

    def status_rows(self) -> list[dict[str, object]]:
        rows = []
        for provider in self._providers:
            status = provider.get_status()
            rows.append(
                {
                    "herramienta": status.name,
                    "modo": status.mode,
                    "tipo": status.provider_type,
                    "configurada": status.configured,
                    "disponible": status.available,
                    "requiere_api_key": status.requires_api_key,
                    "coste_posible": status.can_cost_money,
                    "detalle": status.detail,
                }
            )
        return rows
