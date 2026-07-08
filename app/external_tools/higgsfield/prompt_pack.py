from __future__ import annotations

from app.config.settings import get_settings
from app.external_tools.base import CostEstimate, ProviderStatus


class HiggsfieldManualProvider:
    name = "higgsfield_manual"
    provider_type = "manual_handoff"
    requires_api_key = False
    can_cost_money = True

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_external_tools and settings.enable_higgsfield_manual

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
                "Disponible: genera paquetes de prompts para usar Higgsfield manualmente."
                if available
                else "Desactivado por ENABLE_HIGGSFIELD_MANUAL=false."
            ),
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        return CostEstimate(
            provider_name=self.name,
            operation=str(payload.get("operation") or "prompt_pack"),
            estimated_cost=None,
            currency=get_settings().cost_currency,
            units_type="clips",
            input_units=float(payload.get("scene_count") or 0),
            notes="El coste depende de Higgsfield; ShortsFactory solo genera prompts.",
        )

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        return {"provider": self.name, "pack_type": "higgsfield", "context": project_context}

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "manual_handoff", "payload": payload}

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "manual_only"}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "import_pending", "result": result}
