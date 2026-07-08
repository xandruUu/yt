from __future__ import annotations

from app.config.settings import get_settings
from app.external_tools.base import CostEstimate, ProviderStatus


class PicsartManualProvider:
    name = "picsart_manual"
    provider_type = "manual_handoff"
    requires_api_key = False
    can_cost_money = True

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_external_tools and settings.enable_picsart_manual

    def get_status(self) -> ProviderStatus:
        available = self.is_available()
        return ProviderStatus(
            name=self.name,
            provider_type=self.provider_type,
            configured=available,
            available=available,
            requires_api_key=False,
            can_cost_money=True,
            mode="manual" if available else "no_disponible",
            detail=(
                "Disponible: genera instrucciones manuales para procesar assets en Picsart."
                if available
                else "Desactivado por ENABLE_PICSART_MANUAL=false."
            ),
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        return CostEstimate(
            provider_name=self.name,
            operation=str(payload.get("operation") or "processing_pack"),
            estimated_cost=None,
            currency=get_settings().cost_currency,
            units_type="assets",
            input_units=float(payload.get("asset_count") or 0),
            notes="El coste depende de Picsart; ShortsFactory solo genera instrucciones.",
        )

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        return {"provider": self.name, "pack_type": "picsart", "context": project_context}

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "manual_handoff", "payload": payload}

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "manual_only"}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "import_pending", "result": result}
