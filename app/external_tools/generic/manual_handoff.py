from __future__ import annotations

from app.external_tools.base import CostEstimate, ProviderStatus


class GenericManualToolProvider:
    name = "generic_manual"
    provider_type = "manual_handoff"
    requires_api_key = False
    can_cost_money = False

    def is_available(self) -> bool:
        return True

    def get_status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            provider_type=self.provider_type,
            configured=True,
            available=True,
            requires_api_key=False,
            can_cost_money=False,
            mode="manual",
            detail="Disponible para generar instrucciones copiables sin API.",
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        return CostEstimate(self.name, str(payload.get("operation", "manual_handoff")), 0.0, "USD")

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        return {"provider": self.name, "mode": "manual", "context": project_context}

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "manual_handoff", "payload": payload}

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "manual_only"}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "import_pending", "result": result}
