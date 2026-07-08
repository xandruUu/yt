from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.repositories import create_cost_event
from app.external_tools.registry import ExternalToolRegistry


@dataclass(frozen=True)
class CostSummary:
    estimated_total: float
    actual_total: float
    currency: str
    event_count: int


def estimate_cost(provider_name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
    provider = ExternalToolRegistry().get_provider(provider_name)
    estimate = provider.estimate_cost({"operation": operation, **payload})
    return {
        "provider_name": estimate.provider_name,
        "operation": estimate.operation,
        "estimated_cost": estimate.estimated_cost,
        "currency": estimate.currency,
        "units_type": estimate.units_type,
        "input_units": estimate.input_units,
        "output_units": estimate.output_units,
        "notes": estimate.notes,
    }


def record_cost_event(
    session: Session,
    *,
    provider_name: str,
    operation: str,
    model: str | None = None,
    estimated_cost: float | None = None,
    actual_cost: float | None = None,
    currency: str | None = None,
    units_type: str | None = None,
    input_units: float | None = None,
    output_units: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.CostEvent:
    return create_cost_event(
        session,
        provider_name=provider_name,
        operation=operation,
        model=model,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        currency=currency or get_settings().cost_currency,
        units_type=units_type,
        input_units=input_units,
        output_units=output_units,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )


def cost_summary(session: Session) -> CostSummary:
    estimated = session.scalar(select(func.sum(models.CostEvent.estimated_cost))) or 0.0
    actual = session.scalar(select(func.sum(models.CostEvent.actual_cost))) or 0.0
    count = session.scalar(select(func.count(models.CostEvent.id))) or 0
    return CostSummary(
        estimated_total=float(estimated),
        actual_total=float(actual),
        currency=get_settings().cost_currency,
        event_count=int(count),
    )
