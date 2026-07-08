from __future__ import annotations

from app.config.settings import get_settings
from app.external_tools.base import CostEstimate, ProviderStatus


class HiggsfieldMCPProvider:
    name = "higgsfield_mcp"
    provider_type = "mcp"
    requires_api_key = False
    can_cost_money = True

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_external_tools and settings.enable_higgsfield_mcp

    def get_status(self) -> ProviderStatus:
        settings = get_settings()
        available = self.is_available()
        return ProviderStatus(
            name=self.name,
            provider_type=self.provider_type,
            configured=settings.enable_higgsfield_mcp,
            available=available,
            requires_api_key=False,
            can_cost_money=True,
            mode="mcp" if available else "no_disponible",
            detail=(
                f"MCP configurado en {settings.higgsfield_mcp_url}."
                if available
                else "Placeholder seguro: no ejecuta MCP hasta ENABLE_HIGGSFIELD_MCP=true."
            ),
            metadata={"mcp_url": settings.higgsfield_mcp_url if settings.enable_higgsfield_mcp else ""},
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        return CostEstimate(self.name, str(payload.get("operation") or "video_generation"), None, get_settings().cost_currency)

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        return {"provider": self.name, "status": "placeholder", "context": project_context}

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "not_submitted",
            "detail": "Higgsfield MCP provider esta preparado como placeholder seguro.",
            "payload": payload,
        }

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "not_available"}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "import_pending", "result": result}
