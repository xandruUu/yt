from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CostEstimate:
    provider_name: str
    operation: str
    estimated_cost: float | None
    currency: str
    units_type: str | None = None
    input_units: float | None = None
    output_units: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    provider_type: str
    configured: bool
    available: bool
    requires_api_key: bool
    can_cost_money: bool
    mode: str
    detail: str
    metadata: dict[str, object] = field(default_factory=dict)


class ExternalToolProvider(Protocol):
    name: str
    provider_type: str
    requires_api_key: bool
    can_cost_money: bool

    def is_available(self) -> bool:
        ...

    def get_status(self) -> ProviderStatus:
        ...

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        ...

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        ...

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        ...

    def poll_job(self, job_id: str) -> dict[str, object]:
        ...

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        ...
