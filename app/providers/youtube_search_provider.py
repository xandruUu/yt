from __future__ import annotations

import os

from app.providers.base import TrendItem


class YouTubeSearchProvider:
    name = "youtube"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("YOUTUBE_DATA_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        if not self.is_available():
            return [
                TrendItem(
                    title="YouTube Data API no configurada",
                    summary="Configura YOUTUBE_DATA_API_KEY o usa modo manual, RSS o Hacker News.",
                    source="YouTube Data API",
                    language=language,
                    market=market,
                    category=category,
                    popularity_signals={"provider_error": True, "missing_api_key": True},
                    raw_data={"query": query, "limit": limit},
                )
            ]
        return [
            TrendItem(
                title="YouTube Data API pendiente de conexión",
                summary="El proveedor está preparado, pero la llamada search.list se implementará en una iteración posterior.",
                source="YouTube Data API",
                language=language,
                market=market,
                category=category,
                popularity_signals={"provider_stub": True},
                raw_data={"query": query, "limit": limit},
            )
        ]

