from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    title: str
    summary: str | None = None
    source: str
    source_url: str | None = None
    language: str | None = None
    market: str | None = None
    category: str | None = None
    published_at: datetime | None = None
    popularity_signals: dict[str, Any] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrendProvider(Protocol):
    name: str

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        ...


def normalize_title(value: str) -> str:
    return " ".join(value.lower().strip().split())
