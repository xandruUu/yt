from __future__ import annotations

import os

from app.config.settings import get_settings
from app.external_tools.base import CostEstimate, ProviderStatus

SUPPORTED_OPERATIONS = {
    "trim",
    "crop",
    "fit",
    "resize",
    "remove_background",
    "change_background",
    "adjust",
    "effects",
    "concat",
    "extract_thumbnail",
}


class PicsartAPIProvider:
    name = "picsart_api"
    provider_type = "api"
    requires_api_key = True
    can_cost_money = True

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_external_tools and settings.enable_picsart_api and bool(_api_key())

    def get_status(self) -> ProviderStatus:
        settings = get_settings()
        has_key = bool(_api_key())
        available = self.is_available()
        if available:
            detail = "Disponible: Picsart API configurada."
        elif not settings.enable_picsart_api:
            detail = "API desactivada. Usa el modo manual o activa ENABLE_PICSART_API=true."
        else:
            detail = "Falta PICSART_API_KEY en .env."
        return ProviderStatus(
            name=self.name,
            provider_type=self.provider_type,
            configured=settings.enable_picsart_api and has_key,
            available=available,
            requires_api_key=True,
            can_cost_money=True,
            mode="api" if settings.enable_picsart_api else "no_disponible",
            detail=detail,
            metadata={"supported_operations": sorted(SUPPORTED_OPERATIONS)},
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        return CostEstimate(
            provider_name=self.name,
            operation=str(payload.get("operation") or "asset_processing"),
            estimated_cost=None,
            currency=get_settings().cost_currency,
            units_type="operations",
            input_units=1,
            notes="Estimacion no disponible; revisar creditos de Picsart antes de ejecutar.",
        )

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        return {"provider": self.name, "pack_type": "picsart_api", "context": project_context}

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        operation = str(payload.get("operation") or "")
        if operation not in SUPPORTED_OPERATIONS:
            return {"status": "failed", "error_message": f"Operacion no soportada: {operation}"}
        if not self.is_available():
            return {"status": "failed", "error_message": self.get_status().detail}
        return {
            "status": "not_submitted",
            "detail": "Picsart API queda preparada; la llamada real se implementara en una iteracion posterior.",
            "operation": operation,
        }

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "not_available"}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "import_pending", "result": result}


def _api_key() -> str:
    return os.getenv("PICSART_API_KEY", "").strip()
